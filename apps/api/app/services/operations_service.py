from datetime import UTC, datetime, timedelta
import re
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.core.config import settings
from app.core.logging import redact_value
from app.integrations.gemini.client import GeminiQuotaExceededError
from app.models.gmail_connection import GmailConnection
from app.models.job_run import JobRun, JobRunStatus
from app.models.member import MemberRole
from app.services.rbac_service import require_role

RETRYABLE_PATTERNS = (
    "timeout",
    "timed out",
    "429",
    "rate limit",
    "too many requests",
    "500",
    "502",
    "503",
    "504",
    "pubsub",
    "pub/sub",
    "database",
    "connection reset",
    "temporarily unavailable",
)
TERMINAL_PATTERNS = (
    "token revoked",
    "invalid_grant",
    "scope",
    "permission",
    "pub/sub authentication",
    "user-disconnected",
    "gmail connection is not active",
)
SECRET_REDACTIONS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s,]+"),
    re.compile(r"(?i)(access[_-]?token[\"'=:\s]+)[^\s,}\"]+"),
    re.compile(r"(?i)(refresh[_-]?token[\"'=:\s]+)[^\s,}\"]+"),
    re.compile(r"(?i)(api[_-]?key[\"'=:\s]+)[^\s,}\"]+"),
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def runbook_url(slug: str) -> str | None:
    if not settings.operations_runbook_base_url:
        return None
    return f"{settings.operations_runbook_base_url.rstrip('/')}/{slug}"


def sanitize_error(value: object) -> str:
    message = str(value)
    for pattern in SECRET_REDACTIONS:
        message = pattern.sub(r"\1[REDACTED]", message)
    message = redact_value(message)
    if len(message) > 1000:
        return f"{message[:1000]}..."
    return message


def classify_error(value: object) -> tuple[str, str, bool]:
    message = sanitize_error(value)
    lowered = message.lower()
    error_class = value.__class__.__name__ if isinstance(value, Exception) else "OperationalError"
    if isinstance(value, GeminiQuotaExceededError):
        return error_class, "quota_exceeded", True
    if any(pattern in lowered for pattern in TERMINAL_PATTERNS):
        return error_class, "terminal_error", False
    if any(pattern in lowered for pattern in RETRYABLE_PATTERNS):
        return error_class, "retryable_error", True
    return error_class, "unknown_error", False


def create_correlation_id(prefix: str = "job") -> str:
    return f"{prefix}-{uuid4()}"


def job_duration_ms(job: JobRun) -> int | None:
    if job.started_at is None or job.finished_at is None:
        return None
    started = job.started_at if job.started_at.tzinfo else job.started_at.replace(tzinfo=UTC)
    finished = job.finished_at if job.finished_at.tzinfo else job.finished_at.replace(tzinfo=UTC)
    return max(0, int((finished - started).total_seconds() * 1000))


def mark_job_running(job: JobRun) -> None:
    now = utc_now()
    job.status = JobRunStatus.RUNNING.value
    job.started_at = job.started_at or now
    job.attempts += 1
    job.error_message = None
    job.error_class = None
    job.error_code = None
    job.retryable = False
    job.next_retry_at = None


def mark_job_succeeded(job: JobRun) -> None:
    job.status = JobRunStatus.SUCCEEDED.value
    job.finished_at = utc_now()
    job.error_message = None
    job.error_class = None
    job.error_code = None
    job.retryable = False
    job.next_retry_at = None
    job.duration_ms = job_duration_ms(job)


def mark_job_failed(job: JobRun, exc: object) -> None:
    error_class, error_code, retryable = classify_error(exc)
    job.status = JobRunStatus.FAILED.value
    job.error_class = error_class
    job.error_code = error_code
    job.error_message = sanitize_error(exc)
    job.retryable = retryable and job.attempts < job.max_attempts
    job.finished_at = utc_now()
    job.duration_ms = job_duration_ms(job)
    job.alert_owner = settings.operations_alert_owner
    job.runbook_url = runbook_url(job.job_type.replace("_", "-"))
    if job.retryable:
        provider_retry_after = getattr(exc, "retry_after_seconds", None)
        delay_seconds = provider_retry_after or min(300, 30 * (2 ** max(job.attempts - 1, 0)))
        job.next_retry_at = utc_now() + timedelta(seconds=delay_seconds)
    else:
        job.next_retry_at = None


def ensure_job_defaults(job: JobRun, *, queue_name: str, related_resource_type: str, related_resource_id: str) -> None:
    job.queue_name = job.queue_name or queue_name
    job.correlation_id = job.correlation_id or create_correlation_id(job.job_type)
    job.related_resource_type = job.related_resource_type or related_resource_type
    job.related_resource_id = job.related_resource_id or related_resource_id
    job.alert_owner = job.alert_owner or settings.operations_alert_owner
    job.runbook_url = job.runbook_url or runbook_url(job.job_type.replace("_", "-"))


def list_workspace_failures(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    *,
    limit: int = 50,
) -> list[JobRun]:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    return list(
        db.scalars(
            select(JobRun)
            .where(JobRun.organization_id == organization_id, JobRun.status == JobRunStatus.FAILED.value)
            .order_by(JobRun.created_at.desc())
            .limit(limit)
        )
    )


def list_system_failures(db: Session, *, limit: int = 100) -> list[JobRun]:
    return list(
        db.scalars(
            select(JobRun)
            .where(JobRun.status == JobRunStatus.FAILED.value)
            .order_by(JobRun.created_at.desc())
            .limit(limit)
        )
    )


def get_operations_job(db: Session, organization_id: str, job_id: str, actor: AuthenticatedUser) -> JobRun:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    job = db.get(JobRun, job_id)
    if job is None or job.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job run not found")
    return job


def retry_failed_job(db: Session, organization_id: str, job_id: str, actor: AuthenticatedUser) -> tuple[JobRun, JobRun]:
    original = get_operations_job(db, organization_id, job_id, actor)
    if original.status != JobRunStatus.FAILED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed jobs can be retried")
    if not original.retryable:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job is not retryable")

    metadata = original.job_metadata or {}
    if original.job_type == "gmail_import":
        connection_id = metadata.get("gmail_connection_id") or original.related_resource_id
        if not connection_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job is missing Gmail connection")
        from app.services.job_queue_service import enqueue_gmail_import

        retry_job = enqueue_gmail_import(
            db,
            organization_id,
            connection_id,
            actor,
            max_results=int(metadata.get("max_results") or 20),
        )
    elif original.job_type == "ai_triage":
        ticket_id = metadata.get("ticket_id") or original.related_resource_id
        if not ticket_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job is missing ticket")
        from app.services.job_queue_service import enqueue_ticket_triage

        retry_job = enqueue_ticket_triage(
            db,
            organization_id,
            ticket_id,
            actor,
            force=True,
            respect_workspace_setting=False,
        )
        if retry_job is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not retry triage job")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job type cannot be replayed safely")

    original.job_metadata = {
        **metadata,
        "last_manual_retry_job_id": retry_job.id,
        "last_manual_retry_requested_by_user_id": actor.id,
        "last_manual_retry_requested_at": utc_now().isoformat(),
    }
    db.commit()
    db.refresh(original)
    db.refresh(retry_job)
    return original, retry_job


def get_sync_health(db: Session, organization_id: str, actor: AuthenticatedUser) -> dict:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    connections = list(
        db.scalars(
            select(GmailConnection)
            .where(GmailConnection.organization_id == organization_id)
            .order_by(GmailConnection.created_at.desc())
        )
    )
    stale_cutoff = utc_now() - timedelta(minutes=settings.sync_fallback_interval_minutes)
    rows = []
    stale_connections = 0
    for connection in connections:
        last_success = connection.last_successful_sync_at
        if last_success is not None and last_success.tzinfo is None:
            last_success = last_success.replace(tzinfo=UTC)
        stale = connection.status == "active" and (last_success is None or last_success < stale_cutoff)
        if stale:
            stale_connections += 1
        degraded = (
            connection.status != "active"
            or connection.sync_status == "degraded"
            or connection.watch_status == "degraded"
            or connection.consecutive_sync_failures > 0
            or stale
        )
        rows.append(
            {
                "connection_id": connection.id,
                "gmail_email": connection.gmail_email,
                "status": connection.status,
                "sync_status": connection.sync_status,
                "watch_status": connection.watch_status,
                "consecutive_sync_failures": connection.consecutive_sync_failures,
                "last_successful_sync_at": connection.last_successful_sync_at,
                "last_sync_started_at": connection.last_sync_started_at,
                "sync_error_code": connection.sync_error_code,
                "sync_error_message": sanitize_error(connection.sync_error_message or "") or None,
                "degraded": degraded,
            }
        )
    return {
        "active_connections": sum(1 for item in connections if item.status == "active"),
        "degraded_connections": sum(1 for item in rows if item["degraded"]),
        "disconnected_connections": sum(1 for item in connections if item.status != "active"),
        "stale_connections": stale_connections,
        "connections": rows,
    }
