from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.core.config import settings
from app.integrations.gmail.client import (
    gmail_expiration_from_millis,
    refresh_gmail_access_token,
    watch_gmail_mailbox,
)
from app.models.gmail_connection import GmailConnection
from app.models.gmail_sync_event import GmailSyncEvent
from app.models.mail_import_rule import MailImportRule
from app.models.member import MemberRole
from app.services.audit_log_service import create_audit_log
from app.services.gmail_token_service import refresh_connection_access_token
from app.services.pilot_control_service import is_sync_enabled
from app.services.rbac_service import require_role

WATCH_LABEL_FALLBACK = "INBOX"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _safe_error_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc)


def _watch_labels_for_connection(db: Session, connection: GmailConnection) -> list[str]:
    rule = db.scalar(
        select(MailImportRule).where(
            MailImportRule.organization_id == connection.organization_id,
            MailImportRule.gmail_connection_id == connection.id,
        )
    )
    if rule and rule.support_label_id:
        return [rule.support_label_id]
    return [WATCH_LABEL_FALLBACK]


def _create_sync_event(
    db: Session,
    *,
    organization_id: str,
    connection_id: str | None,
    trigger_type: str,
    event_status: str,
    pubsub_message_id: str | None = None,
    notification_history_id: str | None = None,
    start_history_id: str | None = None,
    end_history_id: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> GmailSyncEvent:
    event = GmailSyncEvent(
        organization_id=organization_id,
        gmail_connection_id=connection_id,
        trigger_type=trigger_type,
        status=event_status,
        pubsub_message_id=pubsub_message_id,
        notification_history_id=notification_history_id,
        start_history_id=start_history_id,
        end_history_id=end_history_id,
        error_code=error_code,
        error_message=error_message,
        sync_metadata=metadata or {},
        started_at=started_at,
        completed_at=completed_at,
    )
    db.add(event)
    return event


def _connection_or_404(db: Session, organization_id: str, connection_id: str) -> GmailConnection:
    connection = db.get(GmailConnection, connection_id)
    if connection is None or connection.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail connection not found")
    return connection


def list_sync_events(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
) -> list[GmailSyncEvent]:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    return list(
        db.scalars(
            select(GmailSyncEvent)
            .where(GmailSyncEvent.organization_id == organization_id)
            .order_by(GmailSyncEvent.created_at.desc())
            .limit(50)
        )
    )


async def register_gmail_watch_for_connection(
    db: Session,
    connection: GmailConnection,
    access_token: str,
    *,
    actor_user_id: str | None,
    trigger_type: str = "watch_register",
    commit: bool = True,
) -> GmailSyncEvent:
    started_at = _utc_now()
    labels = _watch_labels_for_connection(db, connection)
    if not is_sync_enabled(db, connection.organization_id):
        connection.watch_status = "paused"
        connection.sync_status = "paused"
        event = _create_sync_event(
            db,
            organization_id=connection.organization_id,
            connection_id=connection.id,
            trigger_type=trigger_type,
            event_status="skipped",
            error_code="sync_disabled",
            error_message="Gmail sync is disabled for this pilot workspace",
            metadata={"label_ids": labels},
            started_at=started_at,
            completed_at=_utc_now(),
        )
        if commit:
            db.commit()
            db.refresh(event)
        return event

    if not settings.google_pubsub_topic:
        connection.watch_status = "not_configured"
        connection.watch_error = "GOOGLE_PUBSUB_TOPIC is not configured"
        connection.sync_status = "degraded"
        event = _create_sync_event(
            db,
            organization_id=connection.organization_id,
            connection_id=connection.id,
            trigger_type=trigger_type,
            event_status="skipped",
            error_code="pubsub_not_configured",
            error_message=connection.watch_error,
            metadata={"label_ids": labels},
            started_at=started_at,
            completed_at=_utc_now(),
        )
        if commit:
            db.commit()
            db.refresh(event)
        return event

    try:
        response = await watch_gmail_mailbox(
            access_token,
            topic_name=settings.google_pubsub_topic,
            label_ids=labels,
        )
        history_id = str(response.get("historyId") or "") or None
        expires_at = gmail_expiration_from_millis(response.get("expiration"))
        if not history_id:
            raise RuntimeError("Gmail watch response did not include historyId")

        connection.gmail_history_id = history_id
        connection.watch_expires_at = expires_at
        connection.watch_status = "active"
        connection.watch_error = None
        connection.sync_status = "active"
        connection.sync_error_code = None
        connection.sync_error_message = None
        connection.consecutive_sync_failures = 0
        connection.disconnected_at = None

        event = _create_sync_event(
            db,
            organization_id=connection.organization_id,
            connection_id=connection.id,
            trigger_type=trigger_type,
            event_status="succeeded",
            start_history_id=connection.gmail_history_id,
            end_history_id=history_id,
            metadata={
                "label_ids": labels,
                "topic_name": settings.google_pubsub_topic,
                "watch_expires_at": expires_at.isoformat() if expires_at else None,
            },
            started_at=started_at,
            completed_at=_utc_now(),
        )
        create_audit_log(
            db,
            organization_id=connection.organization_id,
            actor_user_id=actor_user_id,
            action="gmail.watch.registered" if trigger_type == "watch_register" else "gmail.watch.renewed",
            resource_type="gmail_connection",
            resource_id=connection.id,
            metadata={
                "gmail_email": connection.gmail_email,
                "history_id": history_id,
                "watch_expires_at": expires_at.isoformat() if expires_at else None,
                "trigger_type": trigger_type,
            },
        )
    except Exception as exc:
        error_message = _safe_error_message(exc)
        connection.watch_status = "error"
        connection.watch_error = error_message
        connection.sync_status = "degraded"
        connection.sync_error_code = "watch_registration_failed"
        connection.sync_error_message = error_message
        connection.consecutive_sync_failures += 1
        event = _create_sync_event(
            db,
            organization_id=connection.organization_id,
            connection_id=connection.id,
            trigger_type=trigger_type,
            event_status="failed",
            error_code="watch_registration_failed",
            error_message=error_message,
            metadata={"label_ids": labels},
            started_at=started_at,
            completed_at=_utc_now(),
        )
        create_audit_log(
            db,
            organization_id=connection.organization_id,
            actor_user_id=actor_user_id,
            action="gmail.watch.failed",
            resource_type="gmail_connection",
            resource_id=connection.id,
            metadata={"gmail_email": connection.gmail_email, "trigger_type": trigger_type},
        )

    if commit:
        db.commit()
        db.refresh(connection)
        db.refresh(event)
    return event


async def register_gmail_watch(
    db: Session,
    organization_id: str,
    connection_id: str,
    actor: AuthenticatedUser,
) -> tuple[GmailConnection, GmailSyncEvent]:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    connection = _connection_or_404(db, organization_id, connection_id)
    if connection.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail connection is not active")

    access_token, _ = await refresh_connection_access_token(db, connection, refresh_func=refresh_gmail_access_token)
    event = await register_gmail_watch_for_connection(
        db,
        connection,
        access_token,
        actor_user_id=actor.id,
        trigger_type="watch_register",
        commit=True,
    )
    return connection, event


async def renew_gmail_watch(
    db: Session,
    organization_id: str,
    connection_id: str,
    actor: AuthenticatedUser | None = None,
) -> tuple[GmailConnection, GmailSyncEvent]:
    if actor is not None:
        require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    connection = _connection_or_404(db, organization_id, connection_id)
    if connection.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail connection is not active")

    access_token, _ = await refresh_connection_access_token(db, connection, refresh_func=refresh_gmail_access_token)
    event = await register_gmail_watch_for_connection(
        db,
        connection,
        access_token,
        actor_user_id=actor.id if actor else None,
        trigger_type="watch_renewal",
        commit=True,
    )
    return connection, event


def mark_connection_disconnected_for_sync(connection: GmailConnection) -> None:
    connection.status = "revoked"
    connection.sync_status = "disconnected"
    connection.watch_status = "disconnected"
    connection.watch_error = None
    connection.disconnected_at = _utc_now()

