from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.audit_log import AuditLogRead
from app.services.audit_log_service import list_audit_logs

router = APIRouter(tags=["audit-logs"])


@router.get("/orgs/{organization_id}/audit-logs", response_model=list[AuditLogRead])
def read_audit_logs(
    organization_id: str,
    db: DbSession,
    current_user: CurrentUser,
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return list_audit_logs(
        db,
        organization_id,
        current_user,
        action=action,
        resource_type=resource_type,
        actor_user_id=actor_user_id,
        search=search,
        limit=limit,
        offset=offset,
    )
