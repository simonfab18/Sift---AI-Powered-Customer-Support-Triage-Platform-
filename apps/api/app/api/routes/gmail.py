from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.rate_limits import limit_gmail_sync, limit_gmail_watch, oauth_callback_rate_limit, oauth_start_rate_limit
from app.core.config import settings
from app.models.gmail_sync_event import GmailSyncEvent
from app.models.member import MemberRole
from app.schemas.gmail import (
    GmailConnectionRead,
    GmailHistorySyncQueueRead,
    GmailOAuthStartRead,
    GmailSyncEventRead,
    GmailSyncStatusRead,
    GmailWatchActionRead,
    MailImportRuleRead,
    MailImportRuleUpdate,
)
from app.services.gmail_connection_service import (
    complete_gmail_oauth,
    list_gmail_connections,
    list_import_rules,
    revoke_gmail_connection,
    start_gmail_oauth,
    update_import_rule,
)
from app.services.gmail_watch_service import list_sync_events, register_gmail_watch, renew_gmail_watch
from app.services.job_queue_service import enqueue_gmail_history_sync
from app.services.rbac_service import require_role

router = APIRouter(tags=["gmail"])


@router.get(
    "/orgs/{organization_id}/gmail/oauth/start",
    response_model=GmailOAuthStartRead,
    dependencies=[Depends(oauth_start_rate_limit)],
)
def start_oauth(organization_id: str, db: DbSession, current_user: CurrentUser):
    auth_url, state = start_gmail_oauth(db, organization_id, current_user)
    return GmailOAuthStartRead(auth_url=auth_url, state=state)


def _gmail_oauth_success_url(connection_id: str) -> str | None:
    if not settings.frontend_origin:
        return None

    query = urlencode({"gmail": "connected", "connection_id": connection_id})
    return f"{settings.frontend_origin.rstrip('/')}/dashboard/settings/gmail?{query}"


@router.get("/gmail/oauth/callback", dependencies=[Depends(oauth_callback_rate_limit)])
async def oauth_callback(state: str, code: str, request: Request, db: DbSession):
    connection = await complete_gmail_oauth(
        db,
        state,
        code,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    redirect_url = _gmail_oauth_success_url(connection.id)
    if redirect_url:
        return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)

    return {
        "connection_id": connection.id,
        "gmail_email": connection.gmail_email,
        "status": connection.status,
    }


@router.get(
    "/orgs/{organization_id}/gmail/connections",
    response_model=list[GmailConnectionRead],
)
def read_connections(organization_id: str, db: DbSession, current_user: CurrentUser):
    return list_gmail_connections(db, organization_id, current_user)


@router.delete(
    "/orgs/{organization_id}/gmail/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_connection(
    organization_id: str,
    connection_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    revoke_gmail_connection(db, organization_id, connection_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/orgs/{organization_id}/gmail/connections/{connection_id}/watch/register",
    response_model=GmailWatchActionRead,
    dependencies=[Depends(limit_gmail_watch)],
)
async def register_watch(
    organization_id: str,
    connection_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    connection, event = await register_gmail_watch(db, organization_id, connection_id, current_user)
    return GmailWatchActionRead(connection=connection, event=event)


@router.post(
    "/orgs/{organization_id}/gmail/connections/{connection_id}/watch/renew",
    response_model=GmailWatchActionRead,
    dependencies=[Depends(limit_gmail_watch)],
)
async def renew_watch(
    organization_id: str,
    connection_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    connection, event = await renew_gmail_watch(db, organization_id, connection_id, current_user)
    return GmailWatchActionRead(connection=connection, event=event)


@router.get(
    "/orgs/{organization_id}/gmail/connections/{connection_id}/sync-status",
    response_model=GmailSyncStatusRead,
)
def read_sync_status(
    organization_id: str,
    connection_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    connections = list_gmail_connections(db, organization_id, current_user)
    connection = next((item for item in connections if item.id == connection_id), None)
    if connection is None:
        raise HTTPException(status_code=404, detail="Gmail connection not found")
    recent_events = list(
        db.scalars(
            select(GmailSyncEvent)
            .where(
                GmailSyncEvent.organization_id == organization_id,
                GmailSyncEvent.gmail_connection_id == connection_id,
            )
            .order_by(GmailSyncEvent.created_at.desc())
            .limit(10)
        )
    )
    return GmailSyncStatusRead(connection=connection, recent_events=recent_events)


@router.post(
    "/orgs/{organization_id}/gmail/connections/{connection_id}/history-sync/queue",
    response_model=GmailHistorySyncQueueRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(limit_gmail_sync)],
)
def queue_history_sync(
    organization_id: str,
    connection_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    require_role(db, organization_id, current_user, {MemberRole.OWNER, MemberRole.ADMIN})
    event = enqueue_gmail_history_sync(
        db,
        organization_id,
        connection_id,
        trigger_type="manual_history_sync",
        metadata={"requested_by_user_id": current_user.id},
    )
    return GmailHistorySyncQueueRead(event=event)


@router.get(
    "/orgs/{organization_id}/gmail/sync-events",
    response_model=list[GmailSyncEventRead],
)
def read_sync_events(organization_id: str, db: DbSession, current_user: CurrentUser):
    return list_sync_events(db, organization_id, current_user)


@router.get(
    "/orgs/{organization_id}/gmail/import-rules",
    response_model=list[MailImportRuleRead],
)
def read_import_rules(organization_id: str, db: DbSession, current_user: CurrentUser):
    return list_import_rules(db, organization_id, current_user)


@router.patch(
    "/orgs/{organization_id}/gmail/import-rules/{rule_id}",
    response_model=MailImportRuleRead,
)
def patch_import_rule(
    organization_id: str,
    rule_id: str,
    payload: MailImportRuleUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return update_import_rule(db, organization_id, rule_id, current_user, payload)

