from datetime import UTC, datetime
from time import perf_counter

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.integrations.gemini.client import classify_ticket_with_gemini
from app.integrations.gemini.prompts import build_triage_prompt
from app.models.ai_triage_result import AITriageResult
from app.models.job_run import JobRun
from app.models.reply_approval import ReplyApproval
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus, TicketTriageStatus
from app.schemas.ai import TriageOutput
from app.services.knowledge_service import record_knowledge_usage, retrieve_knowledge_sources
from app.services.operations_service import ensure_job_defaults, mark_job_failed, mark_job_running, mark_job_succeeded
from app.services.pilot_control_service import ensure_organization_pilot_allowed
from app.services.reply_suggestion_service import create_ai_reply_suggestion_from_triage
from app.services.ticket_service import get_ticket_or_404, write_ticket_event
from app.services.ticket_lifecycle_service import transition_ticket_status

PROMPT_VERSION = "triage-v1"
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
    try:
        output, raw_output = await classify_ticket_with_gemini(prompt)
        latency_ms = int((perf_counter() - timer) * 1000)
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
    return await _execute_ticket_triage(db, ticket, actor)


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


