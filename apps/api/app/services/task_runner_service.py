import asyncio
import logging

from app.api.deps import AuthenticatedUser
from app.core.error_tracking import capture_exception
from app.core.logging import job_id_var
from app.integrations.gemini.client import GeminiQuotaExceededError
from app.db.session import SessionLocal
from app.services.ai_triage_service import run_ticket_triage_job
from app.services.email_import_service import run_gmail_import_job
from app.services.gmail_history_sync_service import run_gmail_history_sync
from app.services.gmail_watch_service import renew_gmail_watch

logger = logging.getLogger(__name__)


def _set_job_context(job_id: str | None):
    return job_id_var.set(job_id)


def _reset_job_context(token) -> None:
    job_id_var.reset(token)


def run_gmail_import_task(
    *,
    job_id: str,
    organization_id: str,
    connection_id: str,
    actor_id: str,
    actor_email: str | None,
    max_results: int,
) -> str:
    token = _set_job_context(job_id)
    actor = AuthenticatedUser(id=actor_id, email=actor_email)
    db = SessionLocal()
    try:
        logger.info(
            "Task job started",
            extra={
                "event_name": "task.job_started",
                "job_id": job_id,
                "organization_id": organization_id,
                "connection_id": connection_id,
                "task_type": "gmail_import",
            },
        )
        job = asyncio.run(
            run_gmail_import_job(
                db,
                job_id,
                organization_id,
                connection_id,
                actor,
                max_results=max_results,
            )
        )
        return job.id
    except Exception as exc:
        capture_exception(
            exc,
            event_name="task.job_failed",
            job_id=job_id,
            organization_id=organization_id,
            connection_id=connection_id,
            task_type="gmail_import",
        )
        logger.exception(
            "Task job failed",
            extra={
                "event_name": "task.job_failed",
                "job_id": job_id,
                "organization_id": organization_id,
                "connection_id": connection_id,
                "task_type": "gmail_import",
                "sanitized_error": exc,
            },
        )
        raise
    finally:
        db.close()
        _reset_job_context(token)


def run_gmail_history_sync_task(
    *,
    organization_id: str,
    connection_id: str,
    event_id: str,
    notification_history_id: str | None = None,
    trigger_type: str = "history_sync",
) -> str:
    token = _set_job_context(event_id)
    db = SessionLocal()
    try:
        event = asyncio.run(
            run_gmail_history_sync(
                db,
                organization_id,
                connection_id,
                event_id=event_id,
                notification_history_id=notification_history_id,
                trigger_type=trigger_type,
            )
        )
        return event.id
    except Exception as exc:
        capture_exception(
            exc,
            event_name="task.sync_event_failed",
            job_id=event_id,
            organization_id=organization_id,
            connection_id=connection_id,
            task_type="gmail_history_sync",
        )
        logger.exception(
            "Task sync event failed",
            extra={
                "event_name": "task.sync_event_failed",
                "job_id": event_id,
                "organization_id": organization_id,
                "connection_id": connection_id,
                "task_type": "gmail_history_sync",
                "sanitized_error": exc,
            },
        )
        raise
    finally:
        db.close()
        _reset_job_context(token)


def run_watch_renewal_task(*, organization_id: str, connection_id: str) -> str:
    db = SessionLocal()
    try:
        connection, event = asyncio.run(
            renew_gmail_watch(
                db,
                organization_id,
                connection_id,
                actor=None,
            )
        )
        return event.id or connection.id
    finally:
        db.close()


def run_ai_triage_task(*, job_id: str) -> tuple[str, str]:
    token = _set_job_context(job_id)
    db = SessionLocal()
    try:
        logger.info(
            "Task job started",
            extra={"event_name": "task.job_started", "job_id": job_id, "task_type": "ai_triage"},
        )
        result = asyncio.run(run_ticket_triage_job(db, job_id))
        return "completed", result.id
    except GeminiQuotaExceededError as exc:
        logger.warning(
            "Task job deferred by Gemini quota",
            extra={
                "event_name": "task.job_deferred",
                "job_id": job_id,
                "task_type": "ai_triage",
                "retry_after_seconds": exc.retry_after_seconds,
            },
        )
        return "deferred", job_id
    except Exception as exc:
        capture_exception(exc, event_name="task.job_failed", job_id=job_id, task_type="ai_triage")
        logger.exception(
            "Task job failed",
            extra={"event_name": "task.job_failed", "job_id": job_id, "task_type": "ai_triage", "sanitized_error": exc},
        )
        raise
    finally:
        db.close()
        _reset_job_context(token)


def run_fallback_sync_scheduler_task() -> list[str]:
    db = SessionLocal()
    try:
        from app.services.job_queue_service import enqueue_fallback_syncs

        events = enqueue_fallback_syncs(db)
        return [event.id for event in events]
    finally:
        db.close()


def run_watch_renewals_scheduler_task() -> list[str]:
    db = SessionLocal()
    try:
        from app.services.job_queue_service import enqueue_due_watch_renewals

        return enqueue_due_watch_renewals(db)
    finally:
        db.close()
