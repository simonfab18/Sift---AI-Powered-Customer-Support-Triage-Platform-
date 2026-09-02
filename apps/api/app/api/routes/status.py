from fastapi import APIRouter

from app.api.routes.health import check_database, check_task_queue_config
from app.core.config import settings
from app.schemas.operations import ServiceStatusRead, StatusDependencyRead

router = APIRouter(tags=["status"])


@router.get("/status", response_model=ServiceStatusRead)
def status() -> ServiceStatusRead:
    database_ok, database_error = check_database()
    task_queue_ok, task_queue_detail = check_task_queue_config()
    service_ok = database_ok and task_queue_ok
    return ServiceStatusRead(
        service=settings.app_name,
        environment=settings.app_env,
        release_version=settings.release_version,
        status="ok" if service_ok else "degraded",
        dependencies={
            "database": StatusDependencyRead(status="ok" if database_ok else "error", detail=database_error),
            "task_queue": StatusDependencyRead(status="ok" if task_queue_ok else "error", detail=task_queue_detail),
        },
    )