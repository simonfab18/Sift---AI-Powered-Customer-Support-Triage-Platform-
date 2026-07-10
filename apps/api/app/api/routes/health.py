from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine

router = APIRouter(tags=["health"])


def check_database() -> tuple[bool, str | None]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


def check_task_queue_config() -> tuple[bool, str | None]:
    if settings.normalized_task_queue_backend == "local":
        return True, "local dispatcher"
    missing = [
        name
        for name, value in {
            "GOOGLE_CLOUD_PROJECT_ID": settings.google_cloud_project_id,
            "TASK_PUBSUB_GMAIL_IMPORT_TOPIC": settings.task_pubsub_gmail_import_topic,
            "TASK_PUBSUB_GMAIL_HISTORY_SYNC_TOPIC": settings.task_pubsub_gmail_history_sync_topic,
            "TASK_PUBSUB_AI_TRIAGE_TOPIC": settings.task_pubsub_ai_triage_topic,
            "TASK_PUBSUB_WATCH_RENEWAL_TOPIC": settings.task_pubsub_watch_renewal_topic,
        }.items()
        if not value
    ]
    if missing:
        return False, "Missing task queue settings: " + ", ".join(missing)
    return True, "pubsub configured"


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live")
def liveness_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness_check(response: Response) -> dict:
    database_ok, database_error = check_database()
    task_queue_ok, task_queue_detail = check_task_queue_config()
    ready = database_ok and task_queue_ok
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "unready",
        "dependencies": {
            "database": {"status": "ok" if database_ok else "error", "detail": database_error},
            "task_queue": {"status": "ok" if task_queue_ok else "error", "detail": task_queue_detail},
        },
        "environment": settings.app_env,
        "release_version": settings.release_version,
    }