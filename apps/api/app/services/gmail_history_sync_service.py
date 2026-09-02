from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.core.config import settings
from app.integrations.gmail.client import (
    GmailHistoryExpiredError,
    get_gmail_message,
    list_gmail_history,
    list_gmail_message_ids,
    refresh_gmail_access_token,
)
from app.integrations.gmail.mapper import normalize_gmail_message
from app.models.gmail_connection import GmailConnection
from app.models.gmail_sync_event import GmailSyncEvent
from app.models.mail_import_rule import MailImportRule
from app.services.email_import_service import import_gmail_message_if_new
from app.services.gmail_token_service import refresh_connection_access_token
from app.services.gmail_watch_service import renew_gmail_watch

SYSTEM_GMAIL_SYNC_ACTOR = AuthenticatedUser(id="system:gmail-sync", email=None)
LOCK_TTL_MINUTES = 5
RECONCILIATION_MAX_RESULTS = 100


def utc_now() -> datetime:
    return datetime.now(UTC)


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _active_connection(db: Session, organization_id: str, connection_id: str) -> GmailConnection:
    connection = db.get(GmailConnection, connection_id)
    if connection is None or connection.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail connection not found")
    if connection.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail connection is not active")
    return connection


def _rule_for_connection(db: Session, connection: GmailConnection) -> MailImportRule:
    rule = db.scalar(
        select(MailImportRule).where(
            MailImportRule.organization_id == connection.organization_id,
            MailImportRule.gmail_connection_id == connection.id,
        )
    )
    if rule is None:
        rule = MailImportRule(organization_id=connection.organization_id, gmail_connection_id=connection.id)
        db.add(rule)
        db.flush()
    return rule


def _message_matches_rule(raw_message: dict, rule: MailImportRule) -> bool:
    label_ids = set(raw_message.get("labelIds") or [])
    if rule.support_label_id and rule.support_label_id not in label_ids:
        return False
    if rule.import_unread_only and label_ids and "UNREAD" not in label_ids:
        return False
    return True


def _event_or_new(
    db: Session,
    connection: GmailConnection,
    event_id: str | None,
    trigger_type: str,
    notification_history_id: str | None,
) -> GmailSyncEvent:
    event = db.get(GmailSyncEvent, event_id) if event_id else None
    if event is not None:
        return event
    event = GmailSyncEvent(
        organization_id=connection.organization_id,
        gmail_connection_id=connection.id,
        trigger_type=trigger_type,
        status="queued",
        notification_history_id=notification_history_id,
        sync_metadata={},
    )
    db.add(event)
    db.flush()
    return event


def _acquire_lock(connection: GmailConnection, event: GmailSyncEvent) -> bool:
    now = utc_now()
    lock_expires_at = _aware(connection.sync_lock_expires_at)
    if connection.sync_lock_id and lock_expires_at and lock_expires_at > now:
        event.status = "skipped"
        event.error_code = "sync_already_running"
        event.error_message = "A Gmail sync is already running for this connection."
        event.completed_at = now
        return False
    connection.sync_lock_id = str(uuid4())
    connection.sync_lock_expires_at = now + timedelta(minutes=LOCK_TTL_MINUTES)
    connection.sync_status = "syncing"
    connection.last_sync_started_at = now
    event.status = "running"
    event.started_at = event.started_at or now
    return True


def _release_lock(connection: GmailConnection) -> None:
    connection.sync_lock_id = None
    connection.sync_lock_expires_at = None


async def run_gmail_history_sync(
    db: Session,
    organization_id: str,
    connection_id: str,
    *,
    event_id: str | None = None,
    notification_history_id: str | None = None,
    trigger_type: str = "history_sync",
) -> GmailSyncEvent:
    connection = _active_connection(db, organization_id, connection_id)
    event = _event_or_new(db, connection, event_id, trigger_type, notification_history_id)
    if not _acquire_lock(connection, event):
        db.commit()
        db.refresh(event)
        return event
    db.commit()

    try:
        event = await _run_locked_history_sync(db, connection.id, event.id, notification_history_id)
    finally:
        db.expire_all()
        locked_connection = db.get(GmailConnection, connection_id)
        if locked_connection is not None:
            _release_lock(locked_connection)
            db.commit()
    db.refresh(event)
    return event


async def _run_locked_history_sync(
    db: Session,
    connection_id: str,
    event_id: str,
    notification_history_id: str | None,
) -> GmailSyncEvent:
    connection = db.get(GmailConnection, connection_id)
    event = db.get(GmailSyncEvent, event_id)
    if connection is None or event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail sync target not found")

    rule = _rule_for_connection(db, connection)
    imported = 0
    skipped = 0
    seen = 0
    tickets_created = 0
    created_ticket_ids: list[str] = []
    message_errors: list[dict[str, str]] = []
    start_history_id = connection.gmail_history_id

    try:
        access_token, _ = await refresh_connection_access_token(db, connection, refresh_func=refresh_gmail_access_token)

        if not start_history_id:
            imported, skipped, seen, tickets_created, created_ticket_ids, message_errors = await _run_reconciliation(
                db, connection, rule, access_token
            )
            end_history_id = notification_history_id or connection.gmail_history_id
            event.trigger_type = "reconciliation"
        else:
            imported, skipped, seen, tickets_created, end_history_id, created_ticket_ids, message_errors = await _run_incremental_history(
                db, connection, rule, access_token, start_history_id
            )

        connection.gmail_history_id = end_history_id or notification_history_id or connection.gmail_history_id
        connection.last_sync_at = utc_now()
        connection.last_successful_sync_at = connection.last_sync_at
        connection.sync_status = "active"
        connection.sync_error_code = None
        connection.sync_error_message = None
        connection.consecutive_sync_failures = 0

        event.status = "succeeded"
        event.start_history_id = start_history_id
        event.end_history_id = connection.gmail_history_id
        event.messages_seen = seen
        event.messages_imported = imported
        event.messages_skipped = skipped
        event.tickets_created = tickets_created
        event.completed_at = utc_now()
        event.sync_metadata = {
            **(event.sync_metadata or {}),
            "reconciliation": event.trigger_type == "reconciliation",
            "message_errors": message_errors[:10],
        }
        db.commit()
        _enqueue_created_ticket_triage(db, connection.organization_id, created_ticket_ids)
    except GmailHistoryExpiredError:
        imported, skipped, seen, tickets_created, created_ticket_ids, message_errors = await _handle_expired_history(
            db, connection, event, rule
        )
        event.messages_seen = seen
        event.messages_imported = imported
        event.messages_skipped = skipped
        event.tickets_created = tickets_created
        db.commit()
        _enqueue_created_ticket_triage(db, connection.organization_id, created_ticket_ids)
    except Exception as exc:
        error_message = _safe_error(exc)
        connection.sync_status = "degraded"
        connection.sync_error_code = "history_sync_failed"
        connection.sync_error_message = error_message
        connection.consecutive_sync_failures += 1
        event.status = "failed"
        event.error_code = "history_sync_failed"
        event.error_message = error_message
        event.completed_at = utc_now()
        event.messages_seen = seen
        event.messages_imported = imported
        event.messages_skipped = skipped
        event.tickets_created = tickets_created
        db.commit()
        raise

    db.refresh(event)
    return event


async def _run_incremental_history(
    db: Session,
    connection: GmailConnection,
    rule: MailImportRule,
    access_token: str,
    start_history_id: str,
) -> tuple[int, int, int, int, str | None, list[str], list[dict[str, str]]]:
    message_ids: list[str] = []
    page_token: str | None = None
    end_history_id: str | None = None
    while True:
        page = await list_gmail_history(access_token, start_history_id, page_token=page_token)
        end_history_id = str(page.get("historyId") or "") or end_history_id
        for item in page.get("history", []) or []:
            for added in item.get("messagesAdded", []) or []:
                message = added.get("message") or {}
                message_id = message.get("id")
                if message_id:
                    message_ids.append(message_id)
        page_token = page.get("nextPageToken")
        if not page_token:
            break
    return await _import_message_ids(db, connection, rule, access_token, message_ids, end_history_id)


async def _run_reconciliation(
    db: Session,
    connection: GmailConnection,
    rule: MailImportRule,
    access_token: str,
) -> tuple[int, int, int, int, list[str], list[dict[str, str]]]:
    label_ids = [rule.support_label_id] if rule.support_label_id else []
    message_ids = await list_gmail_message_ids(
        access_token,
        label_ids=label_ids,
        unread_only=rule.import_unread_only,
        max_results=RECONCILIATION_MAX_RESULTS,
    )
    imported, skipped, seen, tickets_created, _, created_ticket_ids, message_errors = await _import_message_ids(
        db, connection, rule, access_token, message_ids, connection.gmail_history_id
    )
    return imported, skipped, seen, tickets_created, created_ticket_ids, message_errors


async def _handle_expired_history(
    db: Session,
    connection: GmailConnection,
    event: GmailSyncEvent,
    rule: MailImportRule,
) -> tuple[int, int, int, int, list[str], list[dict[str, str]]]:
    access_token, _ = await refresh_connection_access_token(db, connection, refresh_func=refresh_gmail_access_token)
    imported, skipped, seen, tickets_created, created_ticket_ids, message_errors = await _run_reconciliation(db, connection, rule, access_token)
    await renew_gmail_watch(db, connection.organization_id, connection.id, actor=None)
    db.flush()
    db.refresh(connection)
    connection.sync_status = "active"
    connection.sync_error_code = None
    connection.sync_error_message = None
    connection.consecutive_sync_failures = 0
    connection.last_sync_at = utc_now()
    connection.last_successful_sync_at = connection.last_sync_at
    event.trigger_type = "reconciliation"
    event.status = "succeeded"
    event.error_code = "history_checkpoint_expired_recovered"
    event.error_message = None
    event.end_history_id = connection.gmail_history_id
    event.completed_at = utc_now()
    event.sync_metadata = {
        **(event.sync_metadata or {}),
        "recovery_reason": "history_checkpoint_expired",
        "message_errors": message_errors[:10],
    }
    return imported, skipped, seen, tickets_created, created_ticket_ids, message_errors


async def _import_message_ids(
    db: Session,
    connection: GmailConnection,
    rule: MailImportRule,
    access_token: str,
    message_ids: list[str],
    end_history_id: str | None,
) -> tuple[int, int, int, int, str | None, list[str], list[dict[str, str]]]:
    imported = 0
    skipped = 0
    tickets_created = 0
    seen = 0
    created_ticket_ids: list[str] = []
    message_errors: list[dict[str, str]] = []
    for message_id in dict.fromkeys(message_ids):
        seen += 1
        try:
            raw_message = await get_gmail_message(access_token, message_id)
        except HTTPException as exc:
            skipped += 1
            message_errors.append({"message_id": message_id, "error": str(exc.detail)[:300]})
            continue
        if not _message_matches_rule(raw_message, rule):
            skipped += 1
            continue
        normalized = normalize_gmail_message(raw_message)
        ticket, created = import_gmail_message_if_new(
            db,
            connection.organization_id,
            connection.id,
            SYSTEM_GMAIL_SYNC_ACTOR,
            normalized,
        )
        if created and ticket is not None:
            imported += 1
            tickets_created += 1
            created_ticket_ids.append(ticket.id)
        else:
            skipped += 1
    return imported, skipped, seen, tickets_created, end_history_id, created_ticket_ids, message_errors


def _enqueue_created_ticket_triage(db: Session, organization_id: str, ticket_ids: list[str]) -> None:
    for ticket_id in ticket_ids:
        try:
            from app.services.job_queue_service import enqueue_ticket_triage

            enqueue_ticket_triage(
                db,
                organization_id,
                ticket_id,
                SYSTEM_GMAIL_SYNC_ACTOR,
                raise_on_enqueue_error=False,
            )
        except Exception:
            continue


def create_history_sync_event(
    db: Session,
    connection: GmailConnection,
    *,
    trigger_type: str,
    pubsub_message_id: str | None = None,
    notification_history_id: str | None = None,
    metadata: dict | None = None,
) -> GmailSyncEvent:
    event = GmailSyncEvent(
        organization_id=connection.organization_id,
        gmail_connection_id=connection.id,
        trigger_type=trigger_type,
        status="queued",
        pubsub_message_id=pubsub_message_id,
        notification_history_id=notification_history_id,
        sync_metadata=metadata or {},
        created_at=utc_now(),
    )
    db.add(event)
    db.flush()
    return event


def list_stale_connections(db: Session) -> list[GmailConnection]:
    cutoff = utc_now() - timedelta(minutes=settings.sync_fallback_interval_minutes)
    return list(
        db.scalars(
            select(GmailConnection).where(
                GmailConnection.status == "active",
                GmailConnection.watch_status == "active",
                or_(
                    GmailConnection.last_successful_sync_at.is_(None),
                    GmailConnection.last_successful_sync_at < cutoff,
                ),
                or_(
                    GmailConnection.sync_lock_expires_at.is_(None),
                    GmailConnection.sync_lock_expires_at < utc_now(),
                ),
            )
        )
    )
