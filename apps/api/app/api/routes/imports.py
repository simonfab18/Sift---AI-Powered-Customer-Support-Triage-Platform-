from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DbSession
from app.api.rate_limits import limit_gmail_sync
from app.core.config import settings
from app.schemas.imports import GmailSyncRequest, JobRunRead
from app.services.email_import_service import get_job_run, list_recent_imports, sync_gmail_connection
from app.services.job_queue_service import enqueue_gmail_import

router = APIRouter(tags=["imports"])


@router.post(
    "/orgs/{organization_id}/gmail/connections/{connection_id}/sync",
    response_model=JobRunRead,
    dependencies=[Depends(limit_gmail_sync)],
)
async def sync_connection(
    organization_id: str,
    connection_id: str,
    payload: GmailSyncRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    if settings.normalized_task_queue_backend == "pubsub":
        return enqueue_gmail_import(
            db,
            organization_id,
            connection_id,
            current_user,
            max_results=payload.max_results,
        )
    return await sync_gmail_connection(
        db,
        organization_id,
        connection_id,
        current_user,
        max_results=payload.max_results,
    )


@router.post(
    "/orgs/{organization_id}/gmail/connections/{connection_id}/sync/queue",
    response_model=JobRunRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_gmail_sync)],
)
def queue_sync_connection(
    organization_id: str,
    connection_id: str,
    payload: GmailSyncRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    return enqueue_gmail_import(
        db,
        organization_id,
        connection_id,
        current_user,
        max_results=payload.max_results,
    )


@router.get("/orgs/{organization_id}/imports/recent", response_model=list[JobRunRead])
def read_recent_imports(organization_id: str, db: DbSession, current_user: CurrentUser):
    return list_recent_imports(db, organization_id, current_user)


@router.get("/orgs/{organization_id}/jobs/{job_id}", response_model=JobRunRead)
def read_job_run(organization_id: str, job_id: str, db: DbSession, current_user: CurrentUser):
    return get_job_run(db, organization_id, job_id, current_user)
