from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.ai_triage_result import AITriageResult
from app.models.gmail_sync_event import GmailSyncEvent
from app.models.job_run import JobRun, JobRunStatus
from app.models.ticket import Ticket, TicketTriageStatus
from app.services.ai_triage_service import PROMPT_VERSION, SCHEMA_VERSION
from app.services.email_import_service import create_gmail_import_job
from app.services.gmail_history_sync_service import create_history_sync_event, list_stale_connections
from app.services.operations_service import mark_job_failed
from app.services.pilot_control_service import ensure_auto_triage_enabled, ensure_sync_enabled, is_auto_triage_enabled
from app.services.task_dispatcher_service import (
    TaskDispatchError,
    publish_ai_triage_task,
    publish_gmail_history_sync_task,
    publish_gmail_import_task,
    publish_watch_renewal_task,
)


def enqueue_gmail_import(
    db: Session,
    organization_id: str,
    connection_id: str,
    actor: AuthenticatedUser,
    max_results: int = 20,
) -> JobRun:
    ensure_sync_enabled(db, organization_id)
    job = create_gmail_import_job(db, organization_id, connection_id, actor, max_results=max_results)
    try:
        dispatched = publish_gmail_import_task(
            job_id=job.id,
            organization_id=organization_id,
            connection_id=connection_id,
            actor_id=actor.id,
            actor_email=actor.email,
            max_results=max_results,
        )
        job.job_metadata = {**(job.job_metadata or {}), "dispatch_message_id": dispatched.message_id, "dispatch_topic": dispatched.topic}
        db.commit()
        db.refresh(job)
    except Exception as exc:
        mark_job_failed(job, RuntimeError(f"Could not enqueue Gmail import job: {exc}"))
        db.commit()
        db.refresh(job)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not enqueue Gmail import job. Is Pub/Sub task dispatch configured?",
        ) from exc
    return job


def enqueue_ticket_triage(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
    *,
    force: bool = False,
    respect_workspace_setting: bool = True,
    raise_on_enqueue_error: bool = True,
) -> JobRun | None:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    if respect_workspace_setting and not is_auto_triage_enabled(db, organization_id):
        ticket.triage_status = TicketTriageStatus.NOT_QUEUED.value
        db.commit()
        return None
    if not respect_workspace_setting:
        ensure_auto_triage_enabled(db, organization_id)

    if not force and ticket.active_triage_job_id:
        active_job = db.get(JobRun, ticket.active_triage_job_id)
        if active_job is not None and active_job.status in {JobRunStatus.QUEUED.value, JobRunStatus.RUNNING.value}:
            return active_job

    if not force and ticket.triage_status == TicketTriageStatus.TRIAGED.value:
        has_result = db.scalar(
            select(AITriageResult.id).where(
                AITriageResult.organization_id == organization_id,
                AITriageResult.ticket_id == ticket_id,
            )
        )
        if has_result:
            return None

    job = JobRun(
        organization_id=organization_id,
        job_type="ai_triage",
        queue_name="ai_triage",
        status=JobRunStatus.QUEUED.value,
        correlation_id=f"ai-triage-{ticket_id}",
        related_resource_type="ticket",
        related_resource_id=ticket_id,
        job_metadata={
            "ticket_id": ticket_id,
            "requested_by_user_id": actor.id,
            "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "manual_retry": force,
        },
    )
    db.add(job)
    db.flush()
    ticket.triage_status = TicketTriageStatus.QUEUED.value
    ticket.active_triage_job_id = job.id
    ticket.triage_error_message = None
    db.commit()
    db.refresh(job)

    try:
        dispatched = publish_ai_triage_task(job_id=job.id)
        job.job_metadata = {**(job.job_metadata or {}), "dispatch_message_id": dispatched.message_id, "dispatch_topic": dispatched.topic}
        db.commit()
        db.refresh(job)
    except Exception as exc:
        mark_job_failed(job, RuntimeError(f"Could not enqueue AI triage job: {exc}"))
        ticket.triage_status = TicketTriageStatus.FAILED.value
        ticket.active_triage_job_id = None
        ticket.triage_error_message = job.error_message
        db.commit()
        db.refresh(job)
        if raise_on_enqueue_error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not enqueue AI triage job. Is Pub/Sub task dispatch configured?",
            ) from exc
    return job


def enqueue_gmail_history_sync(
    db: Session,
    organization_id: str,
    connection_id: str,
    *,
    trigger_type: str = "manual_history_sync",
    pubsub_message_id: str | None = None,
    notification_history_id: str | None = None,
    metadata: dict | None = None,
) -> GmailSyncEvent:
    from app.models.gmail_connection import GmailConnection

    connection = db.get(GmailConnection, connection_id)
    if connection is None or connection.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail connection not found")
    if connection.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail connection is not active")
    ensure_sync_enabled(db, organization_id)

    event = create_history_sync_event(
        db,
        connection,
        trigger_type=trigger_type,
        pubsub_message_id=pubsub_message_id,
        notification_history_id=notification_history_id,
        metadata=metadata,
    )
    db.commit()
    db.refresh(event)
    try:
        dispatched = publish_gmail_history_sync_task(
            organization_id=organization_id,
            connection_id=connection_id,
            event_id=event.id,
            notification_history_id=notification_history_id,
            trigger_type=trigger_type,
        )
        event.sync_metadata = {**(event.sync_metadata or {}), "dispatch_message_id": dispatched.message_id, "dispatch_topic": dispatched.topic}
        db.commit()
        db.refresh(event)
    except Exception as exc:
        event.status = "failed"
        event.error_code = "enqueue_failed"
        event.error_message = f"Could not enqueue Gmail history sync job: {exc}"
        db.commit()
        db.refresh(event)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not enqueue Gmail history sync job. Is Pub/Sub task dispatch configured?",
        ) from exc
    return event


def enqueue_fallback_syncs(db: Session) -> list[GmailSyncEvent]:
    events: list[GmailSyncEvent] = []
    for connection in list_stale_connections(db):
        try:
            event = enqueue_gmail_history_sync(
                db,
                connection.organization_id,
                connection.id,
                trigger_type="fallback_sync",
                metadata={"reason": "stale_connection_scan"},
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                continue
            raise
        events.append(event)
    return events


def enqueue_due_watch_renewals(db: Session) -> list[str]:
    from datetime import UTC, datetime, timedelta

    from app.models.gmail_connection import GmailConnection

    renewal_cutoff = datetime.now(UTC) + timedelta(days=1)
    connection_ids: list[str] = []
    connections = db.scalars(
        select(GmailConnection).where(
            GmailConnection.status == "active",
            GmailConnection.watch_status.in_(["active", "error"]),
            (GmailConnection.watch_expires_at.is_(None) | (GmailConnection.watch_expires_at <= renewal_cutoff)),
        )
    )
    for connection in connections:
        try:
            publish_watch_renewal_task(organization_id=connection.organization_id, connection_id=connection.id)
        except TaskDispatchError:
            raise
        connection_ids.append(connection.id)
    return connection_ids