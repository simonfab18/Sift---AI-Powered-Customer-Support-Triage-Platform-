from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.encryption import encrypt_secret
from app.models.gmail_connection import GmailConnection
from app.models.gmail_sync_event import GmailSyncEvent
from app.models.mail_import_rule import MailImportRule


def create_watch_connection(client: TestClient, organization_id: str) -> str:
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization_id,
            connected_by_user_id="user-owner",
            gmail_email="support@example.com",
            google_account_id="google-account-id",
            encrypted_refresh_token=encrypt_secret("refresh-token"),
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
        )
        db.add(connection)
        db.flush()
        db.add(MailImportRule(organization_id=organization_id, gmail_connection_id=connection.id))
        db.commit()
        return connection.id


def test_register_gmail_watch_stores_history_and_expiration(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    monkeypatch.setattr(settings, "google_pubsub_topic", "projects/customer-support-triage-501408/topics/gmail-notifications")
    organization = create_org()
    connection_id = create_watch_connection(client, organization["id"])

    async def fake_refresh(refresh_token: str):
        assert refresh_token == "refresh-token"
        return "access-token", datetime.now(UTC)

    async def fake_watch(access_token: str, topic_name: str, label_ids: list[str] | None = None):
        assert access_token == "access-token"
        assert topic_name == "projects/customer-support-triage-501408/topics/gmail-notifications"
        assert label_ids == ["INBOX"]
        return {"historyId": "12345", "expiration": "1893456000000"}

    monkeypatch.setattr("app.services.gmail_watch_service.refresh_gmail_access_token", fake_refresh)
    monkeypatch.setattr("app.services.gmail_watch_service.watch_gmail_mailbox", fake_watch)

    response = client.post(f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/watch/register")

    assert response.status_code == 200
    body = response.json()
    assert body["connection"]["gmail_history_id"] == "12345"
    assert body["connection"]["watch_status"] == "active"
    assert body["event"]["status"] == "succeeded"

    with client.session_factory() as db:
        connection = db.get(GmailConnection, connection_id)
        event = db.scalar(select(GmailSyncEvent).where(GmailSyncEvent.trigger_type == "watch_register"))
        assert connection.gmail_history_id == "12345"
        assert connection.watch_status == "active"
        assert connection.sync_status == "active"
        assert event is not None
        assert event.end_history_id == "12345"


def test_renew_gmail_watch_updates_existing_checkpoint(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    monkeypatch.setattr(settings, "google_pubsub_topic", "projects/customer-support-triage-501408/topics/gmail-notifications")
    organization = create_org()
    connection_id = create_watch_connection(client, organization["id"])

    async def fake_refresh(refresh_token: str):
        return "access-token", datetime.now(UTC)

    async def fake_watch(access_token: str, topic_name: str, label_ids: list[str] | None = None):
        return {"historyId": "99999", "expiration": "1893456000000"}

    monkeypatch.setattr("app.services.gmail_watch_service.refresh_gmail_access_token", fake_refresh)
    monkeypatch.setattr("app.services.gmail_watch_service.watch_gmail_mailbox", fake_watch)

    response = client.post(f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/watch/renew")

    assert response.status_code == 200
    assert response.json()["connection"]["gmail_history_id"] == "99999"
    assert response.json()["event"]["trigger_type"] == "watch_renewal"


def test_watch_registration_failure_is_visible(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    monkeypatch.setattr(settings, "google_pubsub_topic", "projects/customer-support-triage-501408/topics/gmail-notifications")
    organization = create_org()
    connection_id = create_watch_connection(client, organization["id"])

    async def fake_refresh(refresh_token: str):
        return "access-token", datetime.now(UTC)

    async def fake_watch(access_token: str, topic_name: str, label_ids: list[str] | None = None):
        raise RuntimeError("watch unavailable")

    monkeypatch.setattr("app.services.gmail_watch_service.refresh_gmail_access_token", fake_refresh)
    monkeypatch.setattr("app.services.gmail_watch_service.watch_gmail_mailbox", fake_watch)

    response = client.post(f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/watch/register")

    assert response.status_code == 200
    assert response.json()["connection"]["watch_status"] == "error"
    assert response.json()["connection"]["sync_status"] == "degraded"
    assert response.json()["event"]["status"] == "failed"


def test_revoke_connection_marks_sync_disconnected(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_watch_connection(client, organization["id"])

    response = client.delete(f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}")

    assert response.status_code == 204
    with client.session_factory() as db:
        connection = db.get(GmailConnection, connection_id)
        assert connection.status == "revoked"
        assert connection.sync_status == "disconnected"
        assert connection.watch_status == "disconnected"
        assert connection.disconnected_at is not None

def test_enqueue_due_watch_renewals_queues_expiring_active_connections(client: TestClient, create_org, monkeypatch) -> None:
    from app.services.job_queue_service import enqueue_due_watch_renewals

    organization = create_org()
    queued: list[tuple[str, str]] = []

    class StubDispatchedTask:
        message_id = "watch-renewal-message"
        topic = "local-watch-renewal"

    def fake_publish(*, organization_id: str, connection_id: str):
        queued.append((organization_id, connection_id))
        return StubDispatchedTask()

    monkeypatch.setattr("app.services.job_queue_service.publish_watch_renewal_task", fake_publish)

    with client.session_factory() as db:
        due_connection = GmailConnection(
            organization_id=organization["id"],
            connected_by_user_id="user-owner",
            gmail_email="due@example.com",
            google_account_id="google-due",
            encrypted_refresh_token="encrypted-refresh-token",
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
            watch_status="active",
            watch_expires_at=datetime.now(UTC) + timedelta(hours=2),
        )
        later_connection = GmailConnection(
            organization_id=organization["id"],
            connected_by_user_id="user-owner",
            gmail_email="later@example.com",
            google_account_id="google-later",
            encrypted_refresh_token="encrypted-refresh-token",
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
            watch_status="active",
            watch_expires_at=datetime.now(UTC) + timedelta(days=3),
        )
        db.add_all([due_connection, later_connection])
        db.commit()

        queued_ids = enqueue_due_watch_renewals(db)

    assert queued_ids == [due_connection.id]
    assert queued == [(organization["id"], due_connection.id)]
