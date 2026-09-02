import asyncio
import base64
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select

from app.core.config import settings
from app.core.encryption import encrypt_secret
from app.integrations.gmail.client import GmailHistoryExpiredError
from app.models.gmail_connection import GmailConnection
from app.models.gmail_sync_event import GmailSyncEvent
from app.models.mail_import_rule import MailImportRule
from app.models.ticket import Ticket
from app.services.gmail_history_sync_service import list_stale_connections, run_gmail_history_sync


def encoded_body(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


def gmail_message(message_id: str, labels: list[str] | None = None) -> dict:
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "labelIds": labels or ["INBOX", "UNREAD"],
        "internalDate": "1704067200000",
        "snippet": "snippet text",
        "payload": {
            "headers": [
                {"name": "From", "value": "Casey Customer <casey@example.com>"},
                {"name": "Subject", "value": f"Subject {message_id}"},
                {"name": "Date", "value": "Mon, 01 Jan 2024 12:00:00 +0000"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": encoded_body("Hello support team")}},
            ],
        },
    }


def create_history_connection(client, organization_id: str, history_id: str | None = "100") -> str:
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization_id,
            connected_by_user_id="user-owner",
            gmail_email="support@example.com",
            google_account_id="google-account-id",
            encrypted_refresh_token=encrypt_secret("refresh-token"),
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
            watch_status="active",
            sync_status="active",
            gmail_history_id=history_id,
        )
        db.add(connection)
        db.flush()
        db.add(MailImportRule(organization_id=organization_id, gmail_connection_id=connection.id))
        db.commit()
        return connection.id


def test_history_sync_processes_paginated_messages_and_advances_checkpoint(client, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_history_connection(client, organization["id"])

    async def fake_refresh(refresh_token: str):
        assert refresh_token == "refresh-token"
        return "access-token", datetime.now(UTC)

    async def fake_history(access_token: str, start_history_id: str, page_token: str | None = None):
        if page_token is None:
            return {
                "historyId": "101",
                "nextPageToken": "page-2",
                "history": [{"messagesAdded": [{"message": {"id": "gmail-1"}}]}],
            }
        return {
            "historyId": "102",
            "history": [{"messagesAdded": [{"message": {"id": "gmail-2"}}]}],
        }

    async def fake_get_message(access_token: str, message_id: str):
        return gmail_message(message_id)

    monkeypatch.setattr("app.services.gmail_history_sync_service.refresh_gmail_access_token", fake_refresh)
    monkeypatch.setattr("app.services.gmail_history_sync_service.list_gmail_history", fake_history)
    monkeypatch.setattr("app.services.gmail_history_sync_service.get_gmail_message", fake_get_message)

    with client.session_factory() as db:
        event = db.scalar(select(GmailSyncEvent).where(GmailSyncEvent.gmail_connection_id == connection_id))
        result = asyncio.run(
            run_gmail_history_sync(
                db,
                organization["id"],
                connection_id,
                event_id=event.id if event else None,
            )
        )
        connection = db.get(GmailConnection, connection_id)
        tickets = list(db.scalars(select(Ticket)))

    assert result.status == "succeeded"
    assert result.messages_seen == 2
    assert result.messages_imported == 2
    assert connection.gmail_history_id == "102"
    assert len(tickets) == 2


def test_history_sync_skips_unfetchable_messages(client, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_history_connection(client, organization["id"])

    async def fake_refresh(refresh_token: str):
        return "access-token", datetime.now(UTC)

    async def fake_history(access_token: str, start_history_id: str, page_token: str | None = None):
        return {
            "historyId": "101",
            "history": [
                {
                    "messagesAdded": [
                        {"message": {"id": "gmail-bad"}},
                        {"message": {"id": "gmail-good"}},
                    ]
                }
            ],
        }

    async def fake_get_message(access_token: str, message_id: str):
        if message_id == "gmail-bad":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gmail message fetch failed: status=404; reason=notFound",
            )
        return gmail_message(message_id)

    monkeypatch.setattr("app.services.gmail_history_sync_service.refresh_gmail_access_token", fake_refresh)
    monkeypatch.setattr("app.services.gmail_history_sync_service.list_gmail_history", fake_history)
    monkeypatch.setattr("app.services.gmail_history_sync_service.get_gmail_message", fake_get_message)

    with client.session_factory() as db:
        result = asyncio.run(run_gmail_history_sync(db, organization["id"], connection_id))
        connection = db.get(GmailConnection, connection_id)
        tickets = list(db.scalars(select(Ticket)))

    assert result.status == "succeeded"
    assert result.messages_seen == 2
    assert result.messages_imported == 1
    assert result.messages_skipped == 1
    assert result.sync_metadata["message_errors"][0]["message_id"] == "gmail-bad"
    assert connection.sync_status == "active"
    assert [ticket.gmail_message_id for ticket in tickets] == ["gmail-good"]


def test_history_sync_skips_duplicate_messages(client, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_history_connection(client, organization["id"])

    async def fake_refresh(refresh_token: str):
        return "access-token", datetime.now(UTC)

    async def fake_history(access_token: str, start_history_id: str, page_token: str | None = None):
        return {"historyId": "101", "history": [{"messagesAdded": [{"message": {"id": "gmail-1"}}]}]}

    async def fake_get_message(access_token: str, message_id: str):
        return gmail_message(message_id)

    monkeypatch.setattr("app.services.gmail_history_sync_service.refresh_gmail_access_token", fake_refresh)
    monkeypatch.setattr("app.services.gmail_history_sync_service.list_gmail_history", fake_history)
    monkeypatch.setattr("app.services.gmail_history_sync_service.get_gmail_message", fake_get_message)

    with client.session_factory() as db:
        first = asyncio.run(run_gmail_history_sync(db, organization["id"], connection_id))
        first_imported = first.messages_imported
        second = asyncio.run(run_gmail_history_sync(db, organization["id"], connection_id))
        second_imported = second.messages_imported
        second_skipped = second.messages_skipped
        tickets = list(db.scalars(select(Ticket)))

    assert first_imported == 1
    assert second_imported == 0
    assert second_skipped == 1
    assert len(tickets) == 1


def test_history_sync_does_not_run_when_lock_is_active(client, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_history_connection(client, organization["id"])
    with client.session_factory() as db:
        connection = db.get(GmailConnection, connection_id)
        connection.sync_lock_id = "existing-lock"
        connection.sync_lock_expires_at = datetime.now(UTC) + timedelta(minutes=5)
        db.commit()
        result = asyncio.run(run_gmail_history_sync(db, organization["id"], connection_id))

    assert result.status == "skipped"
    assert result.error_code == "sync_already_running"


def test_expired_history_checkpoint_runs_reconciliation(client, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    monkeypatch.setattr(settings, "google_pubsub_topic", "projects/customer-support-triage-501408/topics/gmail-notifications")
    organization = create_org()
    connection_id = create_history_connection(client, organization["id"], history_id="old-history")

    async def fake_refresh(refresh_token: str):
        return "access-token", datetime.now(UTC)

    async def fake_history(access_token: str, start_history_id: str, page_token: str | None = None):
        raise GmailHistoryExpiredError("expired")

    async def fake_list_ids(access_token: str, label_ids, unread_only: bool, max_results: int):
        return ["gmail-1"]

    async def fake_get_message(access_token: str, message_id: str):
        return gmail_message(message_id)

    async def fake_watch(access_token: str, topic_name: str, label_ids: list[str] | None = None):
        return {"historyId": "fresh-history", "expiration": "1893456000000"}

    monkeypatch.setattr("app.services.gmail_history_sync_service.refresh_gmail_access_token", fake_refresh)
    monkeypatch.setattr("app.services.gmail_watch_service.refresh_gmail_access_token", fake_refresh)
    monkeypatch.setattr("app.services.gmail_history_sync_service.list_gmail_history", fake_history)
    monkeypatch.setattr("app.services.gmail_history_sync_service.list_gmail_message_ids", fake_list_ids)
    monkeypatch.setattr("app.services.gmail_history_sync_service.get_gmail_message", fake_get_message)
    monkeypatch.setattr("app.services.gmail_watch_service.watch_gmail_mailbox", fake_watch)

    with client.session_factory() as db:
        result = asyncio.run(run_gmail_history_sync(db, organization["id"], connection_id))
        connection = db.get(GmailConnection, connection_id)

    assert result.status == "succeeded"
    assert result.trigger_type == "reconciliation"
    assert result.error_code == "history_checkpoint_expired_recovered"
    assert connection.gmail_history_id == "fresh-history"


def test_fallback_scan_finds_stale_active_connections(client, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    monkeypatch.setattr(settings, "sync_fallback_interval_minutes", 15)
    organization = create_org()
    connection_id = create_history_connection(client, organization["id"])
    with client.session_factory() as db:
        connection = db.get(GmailConnection, connection_id)
        connection.last_successful_sync_at = datetime.now(UTC) - timedelta(minutes=30)
        db.commit()
        stale = list_stale_connections(db)

    assert [connection.id for connection in stale] == [connection_id]
