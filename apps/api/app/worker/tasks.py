"""Legacy task compatibility wrappers.

The deployed staging/production architecture uses Google Pub/Sub push subscriptions and
Cloud Run task routes. These wrappers remain only so older local imports do not reintroduce
Celery or Redis as runtime dependencies.
"""

from app.services.task_runner_service import (
    run_ai_triage_task,
    run_fallback_sync_scheduler_task,
    run_gmail_history_sync_task,
    run_gmail_import_task,
    run_watch_renewal_task,
)


class _TaskWrapper:
    def __init__(self, func):
        self.func = func

    def delay(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)


def _sync_gmail_connection_task(
    job_id: str,
    organization_id: str,
    connection_id: str,
    actor_id: str,
    actor_email: str | None,
    max_results: int,
) -> str:
    return run_gmail_import_task(
        job_id=job_id,
        organization_id=organization_id,
        connection_id=connection_id,
        actor_id=actor_id,
        actor_email=actor_email,
        max_results=max_results,
    )


def _history_sync_gmail_connection_task(
    organization_id: str,
    connection_id: str,
    event_id: str,
    notification_history_id: str | None = None,
    trigger_type: str = "history_sync",
) -> str:
    return run_gmail_history_sync_task(
        organization_id=organization_id,
        connection_id=connection_id,
        event_id=event_id,
        notification_history_id=notification_history_id,
        trigger_type=trigger_type,
    )


def _renew_gmail_watch_task(organization_id: str, connection_id: str) -> str:
    return run_watch_renewal_task(organization_id=organization_id, connection_id=connection_id)


def _triage_ticket_task(job_id: str) -> str:
    return run_ai_triage_task(job_id=job_id)


sync_gmail_connection_task = _TaskWrapper(_sync_gmail_connection_task)
history_sync_gmail_connection_task = _TaskWrapper(_history_sync_gmail_connection_task)
renew_gmail_watch_task = _TaskWrapper(_renew_gmail_watch_task)
enqueue_fallback_syncs_task = _TaskWrapper(run_fallback_sync_scheduler_task)
triage_ticket_task = _TaskWrapper(_triage_ticket_task)