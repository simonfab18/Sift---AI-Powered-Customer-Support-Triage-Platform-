from datetime import UTC, datetime, timedelta
from time import perf_counter

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.core.config import settings
from app.integrations.gemini.client import GeminiQuotaExceededError, classify_ticket_with_gemini
from app.integrations.gemini.prompts import build_triage_prompt
from app.models.ai_triage_result import AITriageResult
from app.models.gmail_connection import GmailConnection
from app.models.job_run import JobRun
from app.models.member import MemberRole
from app.models.reply_approval import ReplyApproval
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus, TicketTriageStatus
from app.schemas.ai import AITriageInboxUsageRead, AITriageUsageRead, TriageOutput
from app.services.knowledge_service import record_knowledge_usage, retrieve_knowledge_sources
from app.services.operations_service import ensure_job_defaults, mark_job_failed, mark_job_running, mark_job_succeeded
from app.services.pilot_control_service import ensure_organization_pilot_allowed
from app.services.rbac_service import require_role
from app.services.reply_suggestion_service import create_ai_reply_suggestion_from_triage
from app.services.ticket_service import get_ticket_or_404, write_ticket_event
from app.services.ticket_lifecycle_service import transition_ticket_status

PROMPT_VERSION = "triage-v2"
SCHEMA_VERSION = "triage-output-v1"
SYSTEM_TRIAGE_ACTOR = AuthenticatedUser(id="system:ai-triage", email=None)

REVIEW_REQUIRED_CATEGORIES = {
    TicketCategory.REFUND.value,
    TicketCategory.RETURN.value,
    TicketCategory.DAMAGED_ITEM.value,
    TicketCategory.BILLING.value,
    TicketCategory.ACCOUNT_ACCESS.value,
    TicketCategory.COMPLAINT.value,
}


PRIORITY_RANK = {
    TicketPriority.LOW.value: 0,
    TicketPriority.MEDIUM.value: 1,
    TicketPriority.HIGH.value: 2,
    TicketPriority.CRITICAL.value: 3,
}


def _set_min_priority(output: TriageOutput, minimum: TicketPriority) -> bool:
    if PRIORITY_RANK[output.priority.value] >= PRIORITY_RANK[minimum.value]:
        return False
    output.priority = minimum
    return True


def apply_triage_policy_guardrails(output: TriageOutput, subject: str, message: str) -> list[str]:
    text = f"{subject} {message}".lower()
    adjustments: list[str] = []
    money_signal = any(term in text for term in ["refund", "double charged", "charged twice", "duplicate charge", "overcharge", "billing", "payment", "chargeback"])
    access_signal = any(term in text for term in ["locked account", "account locked", "cannot log in", "can't log in", "cant log in", "unable to log in", "account access", "password reset"])
    damage_signal = any(term in text for term in ["broken", "damaged", "defective", "not working", "missing part"])
    legal_or_fraud_signal = any(term in text for term in ["fraud", "legal", "lawyer", "attorney", "lawsuit", "chargeback", "stolen", "unauthorized"])
    urgent_signal = any(term in text for term in ["urgent", "immediately", "asap", "right now", "now"])

    if money_signal and output.category == TicketCategory.OTHER:
        output.category = TicketCategory.REFUND if "refund" in text else TicketCategory.BILLING
        adjustments.append("category set from support-policy money signal")
    if access_signal and output.category == TicketCategory.OTHER:
        output.category = TicketCategory.ACCOUNT_ACCESS
        adjustments.append("category set from support-policy account-access signal")
    if damage_signal and output.category == TicketCategory.OTHER:
        output.category = TicketCategory.DAMAGED_ITEM
        adjustments.append("category set from support-policy damaged-item signal")

    if money_signal and access_signal and urgent_signal:
        if _set_min_priority(output, TicketPriority.CRITICAL):
            adjustments.append("priority raised to critical for urgent money plus account-access risk")
    elif legal_or_fraud_signal:
        if _set_min_priority(output, TicketPriority.CRITICAL):
            adjustments.append("priority raised to critical for legal/fraud signal")
    elif money_signal or damage_signal:
        if _set_min_priority(output, TicketPriority.HIGH):
            adjustments.append("priority raised to high for money/damage signal")
    elif access_signal:
        if _set_min_priority(output, TicketPriority.HIGH if urgent_signal else TicketPriority.MEDIUM):
            adjustments.append("priority raised for account-access signal")

    if output.priority in {TicketPriority.CRITICAL, TicketPriority.HIGH} and not output.requires_human_review:
        output.requires_human_review = True
        adjustments.append("human review required for high/critical priority")
    return adjustments

REVIEW_KEYWORDS = {
    "refund",
    "replacement",
    "cancel",
    "cancellation",
    "credit",
    "compensation",
    "chargeback",
    "fraud",
    "legal",
    "privacy",
    "unsafe",
    "injury",
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def enforce_human_review(output: TriageOutput, subject: str, message: str) -> bool:
    if output.requires_human_review:
        return True
    if output.priority in {TicketPriority.CRITICAL, TicketPriority.HIGH}:
        return True
    if output.category.value in REVIEW_REQUIRED_CATEGORIES:
        return True

    text = f"{subject} {message}".lower()
    return any(keyword in text for keyword in REVIEW_KEYWORDS)


def _get_ticket_for_job(db: Session, organization_id: str, ticket_id: str) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc)


def _seconds_until_next_utc_day(now: datetime) -> int:
    next_day = (now + timedelta(days=1)).date()
    next_midnight = datetime.combine(next_day, datetime.min.time(), tzinfo=UTC)
    return max(1, int((next_midnight - now).total_seconds()))


def _triage_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


def _started_ai_triage_job_count(
    db: Session,
    day_start: datetime,
    day_end: datetime,
    *,
    organization_id: str | None = None,
    exclude_job_id: str | None = None,
) -> int:
    statement = (
        select(func.count())
        .select_from(JobRun)
        .where(
            JobRun.job_type == "ai_triage",
            JobRun.started_at >= day_start,
            JobRun.started_at < day_end,
        )
    )
    if organization_id is not None:
        statement = statement.where(JobRun.organization_id == organization_id)
    if exclude_job_id is not None:
        statement = statement.where(JobRun.id != exclude_job_id)
    return db.scalar(statement) or 0


def _manual_ai_triage_result_count(
    db: Session,
    day_start: datetime,
    day_end: datetime,
    *,
    organization_id: str | None = None,
) -> int:
    statement = select(func.count()).select_from(AITriageResult).where(
        AITriageResult.job_run_id.is_(None),
        AITriageResult.created_at >= day_start,
        AITriageResult.created_at < day_end,
    )
    if organization_id is not None:
        statement = statement.where(AITriageResult.organization_id == organization_id)
    return db.scalar(statement) or 0


def _ai_triage_usage_count(
    db: Session,
    day_start: datetime,
    day_end: datetime,
    *,
    organization_id: str | None = None,
    exclude_job_id: str | None = None,
) -> int:
    return _started_ai_triage_job_count(
        db,
        day_start,
        day_end,
        organization_id=organization_id,
        exclude_job_id=exclude_job_id,
    ) + _manual_ai_triage_result_count(db, day_start, day_end, organization_id=organization_id)


def enforce_free_tier_gemini_limit(db: Session, organization_id: str, job: JobRun | None) -> None:
    limit = settings.ai_triage_daily_gemini_limit
    now = utc_now()
    day_start, day_end = _triage_day_bounds(now)
    if limit > 0:
        used_today = _ai_triage_usage_count(
            db,
            day_start,
            day_end,
            exclude_job_id=job.id if job is not None else None,
        )
        if used_today >= limit:
            retry_after = _seconds_until_next_utc_day(now)
            raise GeminiQuotaExceededError(
                "AI triage is paused for today because the free Gemini daily limit was reached; retry after the next UTC day.",
                retry_after_seconds=retry_after,
            )

    org_limit = settings.ai_triage_daily_gemini_org_limit
    if org_limit <= 0:
        return
    org_used_today = _ai_triage_usage_count(
        db,
        day_start,
        day_end,
        organization_id=organization_id,
        exclude_job_id=job.id if job is not None else None,
    )
    if org_used_today >= org_limit:
        retry_after = _seconds_until_next_utc_day(now)
        raise GeminiQuotaExceededError(
            "AI triage is paused for today because this workspace reached its daily free Gemini limit; retry after the next UTC day.",
            retry_after_seconds=retry_after,
        )


def get_ai_triage_usage(db: Session, organization_id: str, actor: AuthenticatedUser) -> AITriageUsageRead:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    now = utc_now()
    day_start, day_end = _triage_day_bounds(now)
    limit = settings.ai_triage_daily_gemini_org_limit
    global_limit = settings.ai_triage_daily_gemini_limit
    used = _ai_triage_usage_count(db, day_start, day_end, organization_id=organization_id)
    global_used = _ai_triage_usage_count(db, day_start, day_end)
    per_inbox_rows = db.execute(
        select(Ticket.gmail_connection_id, GmailConnection.gmail_email, func.count(JobRun.id))
        .select_from(JobRun)
        .join(Ticket, JobRun.related_resource_id == Ticket.id)
        .outerjoin(GmailConnection, Ticket.gmail_connection_id == GmailConnection.id)
        .where(
            JobRun.organization_id == organization_id,
            JobRun.job_type == "ai_triage",
            JobRun.started_at >= day_start,
            JobRun.started_at < day_end,
        )
        .group_by(Ticket.gmail_connection_id, GmailConnection.gmail_email)
        .order_by(GmailConnection.gmail_email.asc())
    ).all()
    per_inbox = [
        AITriageInboxUsageRead(gmail_connection_id=row[0], gmail_email=row[1], used=row[2])
        for row in per_inbox_rows
    ]
    remaining = None if limit <= 0 else max(0, limit - used)
    global_remaining = None if global_limit <= 0 else max(0, global_limit - global_used)
    return AITriageUsageRead(
        date=now.date().isoformat(),
        daily_limit=limit,
        used=used,
        remaining=remaining,
        paused_for_today=limit > 0 and used >= limit,
        global_daily_limit=global_limit,
        global_used=global_used,
        global_remaining=global_remaining,
        global_paused_for_today=global_limit > 0 and global_used >= global_limit,
        resets_at=day_end,
        per_inbox=per_inbox,
    )


def _quota_http_exception(exc: GeminiQuotaExceededError) -> HTTPException:
    headers = {"Retry-After": str(exc.retry_after_seconds)} if exc.retry_after_seconds else None
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=str(exc),
        headers=headers,
    )


async def _execute_ticket_triage(
    db: Session,
    ticket: Ticket,
    actor: AuthenticatedUser,
    *,
    job: JobRun | None = None,
) -> AITriageResult:
    started_at = utc_now()
    ticket.triage_status = TicketTriageStatus.TRIAGING.value
    ticket.triage_error_message = None
    ticket.triage_attempts += 1
    ticket.last_triage_started_at = started_at
    if job is not None:
        ensure_job_defaults(
            job,
            queue_name="ai_triage",
            related_resource_type="ticket",
            related_resource_id=ticket.id,
        )
        mark_job_running(job)
        ticket.active_triage_job_id = job.id
    db.commit()

    try:
        enforce_free_tier_gemini_limit(db, ticket.organization_id, job)

        retrieved_knowledge = retrieve_knowledge_sources(
            db,
            ticket.organization_id,
            f"{ticket.subject} {ticket.message_text}",
        )
        knowledge_references = [item.as_reference() for item in retrieved_knowledge]
        prompt = build_triage_prompt(
            customer_name=ticket.customer.name,
            customer_email=ticket.customer.email,
            subject=ticket.subject,
            message=ticket.message_text,
            knowledge_sources=knowledge_references,
        )
        timer = perf_counter()
        output, raw_output = await classify_ticket_with_gemini(prompt)
        latency_ms = int((perf_counter() - timer) * 1000)
        previous_priority = ticket.priority
        previous_category = ticket.category
        policy_adjustments = apply_triage_policy_guardrails(output, ticket.subject, ticket.message_text)
        requires_human_review = enforce_human_review(output, ticket.subject, ticket.message_text)

        ticket.category = output.category.value
        ticket.priority = output.priority.value
        ticket.sentiment = output.sentiment.value
        if ticket.status in {TicketStatus.NEW.value, TicketStatus.OPEN.value, TicketStatus.PENDING.value}:
            transition_ticket_status(ticket, TicketStatus.AWAITING_APPROVAL.value)
        ticket.triage_status = TicketTriageStatus.TRIAGED.value
        ticket.triage_error_message = None
        ticket.active_triage_job_id = None
        ticket.last_triage_completed_at = utc_now()

        validated_output = output.model_dump(mode="json")
        validated_output["requires_human_review"] = requires_human_review

        result = AITriageResult(
            organization_id=ticket.organization_id,
            ticket_id=ticket.id,
            model_name=raw_output.get("model") or "gemini",
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            latency_ms=latency_ms,
            job_run_id=job.id if job is not None else None,
            raw_input={"prompt": prompt, "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION, "knowledge_sources": knowledge_references},
            raw_output=raw_output,
            validated_output=validated_output,
            category=output.category.value,
            priority=output.priority.value,
            sentiment=output.sentiment.value,
            summary=output.summary,
            suggested_action=output.suggested_action,
            draft_reply=output.draft_reply,
            confidence_score=output.confidence_score,
            reasoning=output.reasoning,
            requires_human_review=requires_human_review,
            validation_status="valid",
            knowledge_sources=knowledge_references,
        )
        db.add(result)
        db.flush()
        record_knowledge_usage(db, ticket.id, result.id, PROMPT_VERSION, retrieved_knowledge)
        create_ai_reply_suggestion_from_triage(db, ticket.id, result, ticket.gmail_connection_id)
        db.add(
            ReplyApproval(
                organization_id=ticket.organization_id,
                ticket_id=ticket.id,
                ai_triage_result_id=result.id,
                gmail_connection_id=ticket.gmail_connection_id,
                suggested_reply=result.draft_reply,
                final_reply=result.draft_reply,
            )
        )
        db.flush()

        if job is not None:
            mark_job_succeeded(job)
            job.job_metadata = {
                **(job.job_metadata or {}),
                "ai_triage_result_id": result.id,
                "prompt_version": PROMPT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "latency_ms": latency_ms,
                "policy_adjustments": policy_adjustments,
                "previous_priority": previous_priority,
                "previous_category": previous_category,
                "new_priority": result.priority,
                "new_category": result.category,
            }

        write_ticket_event(
            db,
            ticket,
            actor,
            "ticket.ai_triaged",
            {
                "ai_triage_result_id": result.id,
                "ai_triage_job_id": job.id if job is not None else None,
                "model_provider": result.model_provider,
                "model_name": result.model_name,
                "prompt_version": PROMPT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "priority": result.priority,
                "category": result.category,
                "requires_human_review": result.requires_human_review,
                "confidence_score": result.confidence_score,
                "previous_priority": previous_priority,
                "previous_category": previous_category,
                "new_priority": result.priority,
                "new_category": result.category,
                "policy_adjustments": policy_adjustments,
                "changed": previous_priority != result.priority or previous_category != result.category,
                "knowledge_source_ids": [source["id"] for source in knowledge_references],
            },
        )
        db.commit()
        db.refresh(result)
        return result
    except Exception as exc:
        error_message = _safe_error(exc)
        ticket.triage_status = TicketTriageStatus.FAILED.value
        ticket.triage_error_message = error_message
        ticket.active_triage_job_id = None
        ticket.last_triage_completed_at = utc_now()
        if job is not None:
            mark_job_failed(job, exc)
            job.job_metadata = {
                **(job.job_metadata or {}),
                "prompt_version": PROMPT_VERSION,
                "schema_version": SCHEMA_VERSION,
            }
        write_ticket_event(
            db,
            ticket,
            actor,
            "ticket.ai_triage_failed",
            {"ai_triage_job_id": job.id if job is not None else None, "error_message": error_message},
        )
        db.commit()
        raise


async def run_ticket_triage(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
) -> AITriageResult:
    ensure_organization_pilot_allowed(organization_id)
    ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
    try:
        return await _execute_ticket_triage(db, ticket, actor)
    except GeminiQuotaExceededError as exc:
        raise _quota_http_exception(exc) from exc


async def run_ticket_triage_job(db: Session, job_id: str) -> AITriageResult:
    job = db.get(JobRun, job_id)
    if job is None or job.job_type != "ai_triage":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI triage job not found")
    ticket_id = (job.job_metadata or {}).get("ticket_id")
    if not ticket_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI triage job is missing a ticket")
    ticket = _get_ticket_for_job(db, job.organization_id, ticket_id)
    return await _execute_ticket_triage(db, ticket, SYSTEM_TRIAGE_ACTOR, job=job)


def list_ticket_triage_results(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
) -> list[AITriageResult]:
    get_ticket_or_404(db, organization_id, ticket_id, actor)
    return list(
        db.scalars(
            select(AITriageResult)
            .where(
                AITriageResult.organization_id == organization_id,
                AITriageResult.ticket_id == ticket_id,
            )
            .order_by(AITriageResult.created_at.desc())
        )
    )
