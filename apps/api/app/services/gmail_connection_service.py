from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from fastapi import HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.core.config import settings
from app.core.encryption import encrypt_secret
from app.integrations.gmail.oauth import (
    build_oauth_url,
    exchange_oauth_code,
    fetch_google_userinfo,
    token_expiry_from_seconds,
)
from app.models.gmail_connection import GmailConnection
from app.models.gmail_sync_event import GmailSyncEvent
from app.models.gmail_oauth_state import GmailOAuthState
from app.models.mail_import_rule import MailImportRule
from app.models.member import MemberRole
from app.schemas.gmail import GmailConnectionUpdate, MailImportRuleUpdate
from app.services.audit_log_service import create_audit_log
from app.services.gmail_watch_service import mark_connection_disconnected_for_sync, register_gmail_watch_for_connection
from app.services.pilot_control_service import ensure_organization_pilot_allowed
from app.services.rbac_service import require_membership, require_role

OAUTH_STATE_TTL_MINUTES = 10
SHARED_SOURCE_TYPES = {"google_group", "shared_mailbox"}


def start_gmail_oauth(db: Session, organization_id: str, actor: AuthenticatedUser) -> tuple[str, str]:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    ensure_organization_pilot_allowed(organization_id)
    state = token_urlsafe(32)
    db.add(
        GmailOAuthState(
            state=state,
            organization_id=organization_id,
            user_id=actor.id,
            expires_at=datetime.now(UTC) + timedelta(minutes=OAUTH_STATE_TTL_MINUTES),
        )
    )
    db.commit()
    return build_oauth_url(state), state


async def complete_gmail_oauth(
    db: Session,
    state: str,
    code: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> GmailConnection:
    oauth_state = db.scalar(select(GmailOAuthState).where(GmailOAuthState.state == state))
    if oauth_state is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    if oauth_state.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        db.delete(oauth_state)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired")

    token_response = await exchange_oauth_code(code)
    refresh_token = token_response.get("refresh_token")
    access_token = token_response.get("access_token")
    if not refresh_token or not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return required OAuth tokens",
        )

    userinfo = await fetch_google_userinfo(access_token)
    gmail_email = userinfo.get("email")
    google_account_id = userinfo.get("sub")
    if not gmail_email or not google_account_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account data is incomplete")

    scopes = token_response.get("scope") or ""
    existing = db.scalar(
        select(GmailConnection).where(
            GmailConnection.organization_id == oauth_state.organization_id,
            GmailConnection.google_account_id == google_account_id,
        )
    )

    if existing is None:
        connection = GmailConnection(
            organization_id=oauth_state.organization_id,
            connected_by_user_id=oauth_state.user_id,
            gmail_email=gmail_email,
            display_name=gmail_email,
            google_account_id=google_account_id,
            encrypted_refresh_token=encrypt_secret(refresh_token),
            token_key_version=settings.encryption_key_version,
            access_token_expires_at=token_expiry_from_seconds(token_response.get("expires_in")),
            scopes=scopes,
            status="active",
            sync_status="connecting",
            watch_status="connecting",
            reauthorization_required_at=None,
            reauthorization_reason=None,
            last_token_error_at=None,
        )
        db.add(connection)
        db.flush()
        db.add(
            MailImportRule(
                organization_id=oauth_state.organization_id,
                gmail_connection_id=connection.id,
                import_unread_only=True,
                is_active=True,
            )
        )
        db.flush()
    else:
        connection = existing
        connection.connected_by_user_id = oauth_state.user_id
        connection.gmail_email = gmail_email
        if not connection.display_name:
            connection.display_name = gmail_email
        connection.encrypted_refresh_token = encrypt_secret(refresh_token)
        connection.token_key_version = settings.encryption_key_version
        connection.access_token_expires_at = token_expiry_from_seconds(token_response.get("expires_in"))
        connection.scopes = scopes
        connection.status = "active"
        connection.sync_status = "connecting"
        connection.watch_status = "connecting"
        connection.watch_error = None
        connection.disconnected_at = None
        connection.reauthorization_required_at = None
        connection.reauthorization_reason = None
        connection.last_token_error_at = None
        db.flush()

    create_audit_log(
        db,
        organization_id=oauth_state.organization_id,
        actor_user_id=oauth_state.user_id,
        action="gmail.connection.connected",
        resource_type="gmail_connection",
        resource_id=connection.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "gmail_email": gmail_email,
            "google_account_id": google_account_id,
            "scopes": scopes,
        },
    )
    await register_gmail_watch_for_connection(
        db,
        connection,
        access_token,
        actor_user_id=oauth_state.user_id,
        trigger_type="watch_register",
        commit=False,
    )
    db.delete(oauth_state)
    db.commit()
    db.refresh(connection)
    return connection



def cleanup_stale_connection_sync_locks(db: Session, organization_id: str) -> int:
    connections = list(
        db.scalars(
            select(GmailConnection).where(
                GmailConnection.organization_id == organization_id,
                GmailConnection.sync_lock_id.is_not(None),
            )
        )
    )
    cleared = 0
    for connection in connections:
        has_running_event = db.scalar(
            select(
                exists().where(
                    GmailSyncEvent.gmail_connection_id == connection.id,
                    GmailSyncEvent.status == "running",
                )
            )
        )
        if has_running_event:
            continue
        connection.sync_lock_id = None
        connection.sync_lock_expires_at = None
        if connection.sync_status == "syncing":
            connection.sync_status = "degraded" if connection.sync_error_code else "active"
        cleared += 1
    db.flush()
    return cleared


def list_gmail_connections(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
) -> list[GmailConnection]:
    require_membership(db, organization_id, actor)
    if cleanup_stale_connection_sync_locks(db, organization_id):
        db.commit()
    return list(
        db.scalars(
            select(GmailConnection)
            .where(GmailConnection.organization_id == organization_id)
            .order_by(GmailConnection.created_at.desc())
        )
    )



def update_gmail_connection(
    db: Session,
    organization_id: str,
    connection_id: str,
    actor: AuthenticatedUser,
    payload: GmailConnectionUpdate,
) -> GmailConnection:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    connection = db.get(GmailConnection, connection_id)
    if connection is None or connection.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail connection not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "display_name" in update_data:
        next_name = update_data["display_name"]
        connection.display_name = next_name.strip() if isinstance(next_name, str) and next_name.strip() else None
    if "inbox_type" in update_data and update_data["inbox_type"] is not None:
        connection.inbox_type = update_data["inbox_type"]
    if "shared_address" in update_data:
        next_address = update_data["shared_address"]
        connection.shared_address = str(next_address).strip().lower() if next_address else None
    if "channel_notes" in update_data:
        next_notes = update_data["channel_notes"]
        connection.channel_notes = next_notes.strip() if isinstance(next_notes, str) and next_notes.strip() else None
    if connection.inbox_type == "individual":
        connection.shared_address = None
    elif connection.inbox_type in SHARED_SOURCE_TYPES and not connection.shared_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shared Gmail source address is required for Google Group or shared mailbox sources",
        )

    create_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="gmail.connection.updated",
        resource_type="gmail_connection",
        resource_id=connection.id,
        metadata={"display_name": connection.display_name, "gmail_email": connection.gmail_email, "inbox_type": connection.inbox_type, "shared_address": connection.shared_address},
    )
    db.commit()
    db.refresh(connection)
    return connection
def revoke_gmail_connection(
    db: Session,
    organization_id: str,
    connection_id: str,
    actor: AuthenticatedUser,
) -> None:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    connection = db.get(GmailConnection, connection_id)
    if connection is None or connection.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail connection not found")
    mark_connection_disconnected_for_sync(connection)
    create_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="gmail.connection.disconnected",
        resource_type="gmail_connection",
        resource_id=connection.id,
        metadata={"gmail_email": connection.gmail_email},
    )
    db.commit()


def list_import_rules(db: Session, organization_id: str, actor: AuthenticatedUser) -> list[MailImportRule]:
    require_membership(db, organization_id, actor)
    return list(
        db.scalars(
            select(MailImportRule)
            .where(MailImportRule.organization_id == organization_id)
            .order_by(MailImportRule.created_at.asc())
        )
    )


def update_import_rule(
    db: Session,
    organization_id: str,
    rule_id: str,
    actor: AuthenticatedUser,
    payload: MailImportRuleUpdate,
) -> MailImportRule:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    rule = db.get(MailImportRule, rule_id)
    if rule is None or rule.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import rule not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)

    create_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="gmail.import_rule.updated",
        resource_type="mail_import_rule",
        resource_id=rule.id,
        metadata={
            "gmail_connection_id": rule.gmail_connection_id,
            "support_label_id": rule.support_label_id,
            "routing_direction": rule.routing_direction,
            "is_active": rule.is_active,
        },
    )
    db.commit()
    db.refresh(rule)
    return rule
