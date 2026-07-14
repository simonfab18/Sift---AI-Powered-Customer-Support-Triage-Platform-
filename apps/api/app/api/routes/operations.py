from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.api.rate_limits import limit_retry
from app.core.config import settings
from app.core.error_tracking import capture_exception
from app.schemas.operations import (
    OperationsFailureListRead,
    OperationsJobRead,
    OperationsRetryRead,
    SyncHealthRead,
)
from app.services.pubsub_verification_service import verify_scheduler_oidc_token
from app.services.operations_service import (
    get_operations_job,
    get_sync_health,
    list_system_failures,
    list_workspace_failures,
    retry_failed_job,
)

router = APIRouter(tags=["operations"])


def require_internal_operations_token(token: str | None) -> None:
    if not settings.operations_internal_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if token != settings.operations_internal_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operations access denied")


@router.get(
    "/orgs/{organization_id}/operations/failures",
    response_model=OperationsFailureListRead,
)
def read_workspace_failures(
    organization_id: str,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = 50,
):
    bounded_limit = min(max(limit, 1), 100)
    return OperationsFailureListRead(
        jobs=list_workspace_failures(db, organization_id, current_user, limit=bounded_limit)
    )


@router.get(
    "/orgs/{organization_id}/operations/jobs/{job_id}",
    response_model=OperationsJobRead,
)
def read_operations_job(
    organization_id: str,
    job_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return get_operations_job(db, organization_id, job_id, current_user)


@router.post(
    "/orgs/{organization_id}/operations/jobs/{job_id}/retry",
    response_model=OperationsRetryRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_retry)],
)
def retry_operations_job(
    organization_id: str,
    job_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    original, retry_job = retry_failed_job(db, organization_id, job_id, current_user)
    return OperationsRetryRead(original_job=original, retry_job=retry_job)


@router.get(
    "/orgs/{organization_id}/operations/sync-health",
    response_model=SyncHealthRead,
)
def read_sync_health(
    organization_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return get_sync_health(db, organization_id, current_user)


@router.get("/operations/failures", response_model=OperationsFailureListRead)
def read_system_failures(
    db: DbSession,
    x_operations_token: Annotated[str | None, Header()] = None,
    limit: int = 100,
):
    require_internal_operations_token(x_operations_token)
    bounded_limit = min(max(limit, 1), 200)
    return OperationsFailureListRead(jobs=list_system_failures(db, limit=bounded_limit))
@router.post("/operations/error-reporting-test", include_in_schema=False)
def report_error_tracking_test(
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    verify_scheduler_oidc_token(authorization)
    capture_exception(
        RuntimeError("sift controlled error reporting test"),
        event_name="operations.error_reporting_test",
        task_type="error_reporting_test",
    )
    return {"status": "reported"}
