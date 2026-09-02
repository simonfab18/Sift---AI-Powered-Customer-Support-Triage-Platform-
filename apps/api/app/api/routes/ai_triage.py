from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DbSession
from app.api.rate_limits import limit_retry, limit_triage
from app.schemas.ai import AITriageJobRead, AITriageResultRead, AITriageUsageRead
from app.services.ai_triage_service import get_ai_triage_usage, list_ticket_triage_results, run_ticket_triage
from app.services.job_queue_service import enqueue_ticket_triage

router = APIRouter(tags=["ai-triage"])


@router.post(
    "/orgs/{organization_id}/tickets/{ticket_id}/triage",
    response_model=AITriageResultRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_triage)],
)
async def triage_ticket(
    organization_id: str,
    ticket_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return await run_ticket_triage(db, organization_id, ticket_id, current_user)


@router.post(
    "/orgs/{organization_id}/tickets/{ticket_id}/triage/retry",
    response_model=AITriageJobRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_retry)],
)
def retry_ticket_triage(
    organization_id: str,
    ticket_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return enqueue_ticket_triage(db, organization_id, ticket_id, current_user, force=True, respect_workspace_setting=False)



@router.get("/orgs/{organization_id}/ai/usage", response_model=AITriageUsageRead)
def read_ai_triage_usage(
    organization_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return get_ai_triage_usage(db, organization_id, current_user)

@router.get("/orgs/{organization_id}/tickets/{ticket_id}/triage", response_model=list[AITriageResultRead])
def read_ticket_triage_results(
    organization_id: str,
    ticket_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return list_ticket_triage_results(db, organization_id, ticket_id, current_user)


@router.get("/orgs/{organization_id}/tickets/{ticket_id}/triage-results", response_model=list[AITriageResultRead])
def read_ticket_triage_results_alias(
    organization_id: str,
    ticket_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return list_ticket_triage_results(db, organization_id, ticket_id, current_user)
