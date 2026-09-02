from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.integrations.gmail.client import get_gmail_message, list_gmail_message_ids, refresh_gmail_access_token
from app.integrations.gmail.mapper import NormalizedGmailMessage, normalize_gmail_message
from app.models.gmail_connection import GmailConnection
from app.models.job_run import JobRun, JobRunStatus
from app.models.mail_import_rule import MailImportRule
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus, TicketTriageStatus
from app.models.ticket_attachment import TicketAttachment
from app.services.gmail_token_service import refresh_connection_access_token
from app.services.operations_service import ensure_job_defaults, mark_job_failed, mark_job_running, mark_job_succeeded
from app.services.pilot_control_service import ensure_sync_enabled
from app.services.rbac_service import require_membership
from app.services.routing_rule_service import apply_routing_rules
from app.services.sla_service import initialize_ticket_sla
from app.services.support_relevance_service import decide_ticket_auto_triage
from app.services.ticket_service import get_or_create_customer, write_ticket_event
from app.services.workspace_settings_service import get_or_create_workspace_settings


def _active_connection_or_404(db: Session, organization_id: str, connection_id: str) -> GmailConnection:
    connection = db.get(GmailConnection, connection_id)
    if connection is None or connection.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail connection not found")
    if connection.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail connection is not active")
    return connection


def _import_rule_for_connection(db: Session, organization_id: str, connection_id: str) -> MailImportRule:
    rule = db.scalar(
        select(MailImportRule).where(
            MailImportRule.organization_id == organization_id,
            MailImportRule.gmail_connection_id == connection_id,
        )
    )
    if rule is None:
        rule = MailImportRule(organization_id=organization_id, gmail_connection_id=connection_id)
        db.add(rule)
        db.flush()
    return rule


def _ticket_exists(db: Session, organization_id: str, gmail_message_id: str) -> bool:
    return (
        db.scalar(
            select(Ticket.id).where(
                Ticket.organization_id == organization_id,
                Ticket.gmail_message_id == gmail_message_id,
            )
        )
        is not None
    )


GMAIL_IMPORT_STALE_AFTER_MINUTES = 5
ACTIVE_IMPORT_STATUSES = {JobRunStatus.QUEUED.value, JobRunStatus.RUNNING.value}


def _mark_stale_import_job(job: JobRun) -> None:
    mark_job_failed(job, TimeoutError("Gmail import job timed out before completion."))
    job.error_code = "stale_running_import"
    job.error_message = "Gmail import was left running and was marked stale. Start a new import to retry."
    job.retryable = True


def cleanup_stale_gmail_import_jobs(db: Session, organization_id: str, connection_id: str | None = None) -> int:
    stale_cutoff = datetime.now(UTC) - timedelta(minutes=GMAIL_IMPORT_STALE_AFTER_MINUTES)
    conditions = [
        JobRun.organization_id == organization_id,
        JobRun.job_type == "gmail_import",
        JobRun.status.in_(ACTIVE_IMPORT_STATUSES),
    ]
    if connection_id is not None:
        conditions.append(JobRun.related_resource_id == connection_id)
    active_jobs = list(db.scalars(select(JobRun).where(*conditions).order_by(JobRun.created_at.desc())))
    stale_count = 0
    for job in active_jobs:
        reference_time = job.started_at or job.created_at
        if reference_time is not None and reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)
        if reference_time is not None and reference_time < stale_cutoff:
            _mark_stale_import_job(job)
            stale_count += 1
    db.flush()
    return stale_count


def get_active_gmail_import_job(db: Session, organization_id: str, connection_id: str) -> JobRun | None:
    cleanup_stale_gmail_import_jobs(db, organization_id, connection_id)
    return db.scalar(
        select(JobRun)
        .where(
            JobRun.organization_id == organization_id,
            JobRun.job_type == "gmail_import",
            JobRun.related_resource_id == connection_id,
            JobRun.status.in_(ACTIVE_IMPORT_STATUSES),
        )
        .order_by(JobRun.created_at.desc())
    )


def _create_ticket_from_gmail(
    db: Session,
    organization_id: str,
    connection_id: str,
    actor: AuthenticatedUser,
    normalized: NormalizedGmailMessage,
) -> Ticket:
    customer = get_or_create_customer(
        db,
        organization_id,
        normalized.customer_email,
        normalized.customer_name,
    )
    ticket = Ticket(
        organization_id=organization_id,
        customer_id=customer.id,
        gmail_connection_id=connection_id,
        gmail_message_id=normalized.gmail_message_id,
        gmail_thread_id=normalized.gmail_thread_id,
        subject=normalized.subject,
        message_text=normalized.message_text,
        message_html=normalized.message_html,
        received_at=normalized.received_at,
    )
    db.add(ticket)
    db.flush()
    for attachment in normalized.attachments:
        db.add(
            TicketAttachment(
                organization_id=organization_id,
                ticket_id=ticket.id,
                gmail_connection_id=connection_id,
                gmail_message_id=normalized.gmail_message_id,
                gmail_attachment_id=attachment.gmail_attachment_id,
                filename=attachment.filename,
                mime_type=attachment.mime_type,
                size_bytes=attachment.size_bytes,
                content_disposition=attachment.content_disposition,
                is_inline=attachment.is_inline,
                policy_status=attachment.policy_status,
                notes=attachment.notes,
            )
        )
    settings = get_or_create_workspace_settings(db, organization_id)
    initialize_ticket_sla(ticket, settings)
    decision = decide_ticket_auto_triage(ticket, normalized.label_ids)
    if not decision.should_auto_triage:
        ticket.triage_status = TicketTriageStatus.NOT_QUEUED.value
        ticket.triage_error_message = f"Auto-triage skipped: {decision.reason}"
        if decision.is_spam:
            ticket.status = TicketStatus.SPAM.value
            ticket.category = TicketCategory.SPAM.value
            ticket.priority = TicketPriority.LOW.value
    apply_routing_rules(db, ticket)
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.imported_from_gmail",
        {
            "gmail_message_id": normalized.gmail_message_id,
            "gmail_thread_id": normalized.gmail_thread_id,
            "gmail_connection_id": connection_id,
            "gmail_label_ids": normalized.label_ids,
            "auto_triage_candidate": decision.should_auto_triage,
            "auto_triage_skip_reason": None if decision.should_auto_triage else decision.reason,
        },
    )
    if not decision.should_auto_triage:
        write_ticket_event(
            db,
            ticket,
            actor,
            "ticket.ai_triage_skipped",
            {"reason": decision.reason, "is_spam": decision.is_spam, "quota_saved": True, "source": "gmail_import"},
        )
    return ticket


def import_gmail_message_if_new(
    db: Session,
    organization_id: str,
    connection_id: str,
    actor: AuthenticatedUser,
    normalized: NormalizedGmailMessage,
) -> tuple[Ticket | None, bool]:
    if not normalized.gmail_message_id:
        return None, False
    if _ticket_exists(db, organization_id, normalized.gmail_message_id):
        return None, False
    ticket = _create_ticket_from_gmail(db, organization_id, connection_id, actor, normalized)
    return ticket, True


def create_gmail_import_job(
    db: Session,
    organization_id: str,
    connection_id: str,
    actor: AuthenticatedUser,
    max_results: int = 20,
    status_value: JobRunStatus = JobRunStatus.QUEUED,
) -> JobRun:
    require_membership(db, organization_id, actor)
    ensure_sync_enabled(db, organization_id)
    _active_connection_or_404(db, organization_id, connection_id)
    rule = _import_rule_for_connection(db, organization_id, connection_id)
    if not rule.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Import rule is not active")

    active_job = get_active_gmail_import_job(db, organization_id, connection_id)
    if active_job is not None:
        db.commit()
        db.refresh(active_job)
        return active_job

    now = datetime.now(UTC)
    job = JobRun(
        organization_id=organization_id,
        job_type="gmail_import",
        queue_name="gmail_sync",
        status=status_value.value,
        started_at=now if status_value == JobRunStatus.RUNNING else None,
        correlation_id=f"gmail-import-{connection_id}-{int(now.timestamp())}",
        related_resource_type="gmail_connection",
        related_resource_id=connection_id,
        job_metadata={
            "gmail_connection_id": connection_id,
            "max_results": max_results,
            "requested_by_user_id": actor.id,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


async def run_gmail_import_job(
    db: Session,
    job_id: str,
    organization_id: str,
    connection_id: str,
    actor: AuthenticatedUser,
    max_results: int = 20,
) -> JobRun:
    require_membership(db, organization_id, actor)
    ensure_sync_enabled(db, organization_id)
    connection = _active_connection_or_404(db, organization_id, connection_id)
    rule = _import_rule_for_connection(db, organization_id, connection_id)
    if not rule.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Import rule is not active")

    job = db.get(JobRun, job_id)
    if job is None or job.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job run not found")
    if job.status in {JobRunStatus.SUCCEEDED.value, JobRunStatus.FAILED.value, JobRunStatus.CANCELED.value}:
        return job

    ensure_job_defaults(
        job,
        queue_name="gmail_sync",
        related_resource_type="gmail_connection",
        related_resource_id=connection_id,
    )
    mark_job_running(job)
    db.commit()

    imported_count = 0
    skipped_count = 0
    message_ids: list[str] = []
    created_ticket_ids: list[str] = []
    message_errors: list[dict[str, str]] = []
    try:
        access_token, _ = await refresh_connection_access_token(db, connection, refresh_func=refresh_gmail_access_token)

        label_ids = [rule.support_label_id] if rule.support_label_id else []
        message_ids = await list_gmail_message_ids(
            access_token,
            label_ids=label_ids,
            unread_only=rule.import_unread_only,
            max_results=max_results,
        )

        for message_id in message_ids:
            if _ticket_exists(db, organization_id, message_id):
                skipped_count += 1
                continue
            try:
                raw_message = await get_gmail_message(access_token, message_id)
            except HTTPException as exc:
                skipped_count += 1
                message_errors.append({"message_id": message_id, "error": str(exc.detail)[:300]})
                continue
            normalized = normalize_gmail_message(raw_message)
            if not normalized.gmail_message_id:
                skipped_count += 1
                continue
            ticket, created = import_gmail_message_if_new(db, organization_id, connection_id, actor, normalized)
            if created and ticket is not None:
                imported_count += 1
                created_ticket_ids.append(ticket.id)
            else:
                skipped_count += 1

        connection.last_sync_at = datetime.now(UTC)
        mark_job_succeeded(job)
        job.job_metadata = {
            "gmail_connection_id": connection_id,
            "max_results": max_results,
            "requested_by_user_id": actor.id,
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "seen_count": len(message_ids),
            "message_errors": message_errors[:10],
        }
        db.commit()
        for ticket_id in created_ticket_ids:
            try:
                from app.services.job_queue_service import enqueue_ticket_triage

                enqueue_ticket_triage(db, organization_id, ticket_id, actor, raise_on_enqueue_error=False)
            except Exception:
                continue
    except Exception as exc:
        mark_job_failed(job, exc)
        job.job_metadata = {
            "gmail_connection_id": connection_id,
            "max_results": max_results,
            "requested_by_user_id": actor.id,
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "seen_count": len(message_ids),
            "message_errors": message_errors[:10],
        }
        db.commit()
        raise

    db.refresh(job)
    return job


async def sync_gmail_connection(
    db: Session,
    organization_id: str,
    connection_id: str,
    actor: AuthenticatedUser,
    max_results: int = 20,
) -> JobRun:
    active_job = get_active_gmail_import_job(db, organization_id, connection_id)
    if active_job is not None:
        db.commit()
        db.refresh(active_job)
        return active_job

    job = create_gmail_import_job(
        db,
        organization_id,
        connection_id,
        actor,
        max_results=max_results,
        status_value=JobRunStatus.RUNNING,
    )
    return await run_gmail_import_job(db, job.id, organization_id, connection_id, actor, max_results=max_results)


def list_recent_imports(db: Session, organization_id: str, actor: AuthenticatedUser) -> list[JobRun]:
    require_membership(db, organization_id, actor)
    if cleanup_stale_gmail_import_jobs(db, organization_id):
        db.commit()
    return list(
        db.scalars(
            select(JobRun)
            .where(JobRun.organization_id == organization_id, JobRun.job_type == "gmail_import")
            .order_by(JobRun.created_at.desc())
            .limit(20)
        )
    )


def get_job_run(db: Session, organization_id: str, job_id: str, actor: AuthenticatedUser) -> JobRun:
    require_membership(db, organization_id, actor)
    job = db.get(JobRun, job_id)
    if job is None or job.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job run not found")
    return job
