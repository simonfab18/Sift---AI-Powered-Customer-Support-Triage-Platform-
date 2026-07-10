import base64
import json

from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.gmail_connection import GmailConnection
from app.models.gmail_sync_event import GmailSyncEvent


def encode_payload(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")


def test_pubsub_webhook_rejects_missing_auth(client: TestClient) -> None:
    response = client.post(
        "/v1/webhooks/google/gmail",
        json={"message": {"messageId": "pubsub-1", "data": encode_payload({"emailAddress": "support@example.com", "historyId": "1"})}},
    )

    assert response.status_code == 401


def test_pubsub_webhook_rejects_invalid_identity(client: TestClient, monkeypatch) -> None:
    def fake_verify(authorization: str | None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unexpected Pub/Sub service account")

    monkeypatch.setattr("app.api.routes.webhooks.verify_pubsub_oidc_token", fake_verify)
    response = client.post(
        "/v1/webhooks/google/gmail",
        headers={"Authorization": "Bearer bad-token"},
        json={"message": {"messageId": "pubsub-1", "data": encode_payload({"emailAddress": "support@example.com", "historyId": "1"})}},
    )

    assert response.status_code == 401


def test_pubsub_webhook_records_valid_notification(client: TestClient, create_org, monkeypatch) -> None:
    organization = create_org()
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization["id"],
            connected_by_user_id="user-owner",
            gmail_email="support@example.com",
            google_account_id="google-account-id",
            encrypted_refresh_token="encrypted-token",
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
            watch_status="active",
            sync_status="active",
        )
        db.add(connection)
        db.commit()
        connection_id = connection.id

    def fake_verify(authorization: str | None):
        assert authorization == "Bearer valid-token"
        return {"email": "pub-sub-push-invoker@customer-support-triage-501408.iam.gserviceaccount.com"}

    monkeypatch.setattr("app.api.routes.webhooks.verify_pubsub_oidc_token", fake_verify)
    queued = []

    class StubDispatchedTask:
        message_id = "history-sync-message"
        topic = "local-gmail-history-sync"

    def fake_publish(**kwargs):
        queued.append(kwargs)
        return StubDispatchedTask()

    monkeypatch.setattr("app.services.job_queue_service.publish_gmail_history_sync_task", fake_publish)

    response = client.post(
        "/v1/webhooks/google/gmail",
        headers={"Authorization": "Bearer valid-token"},
        json={
            "subscription": "projects/customer-support-triage-501408/subscriptions/gmail-notifications-sub",
            "message": {
                "messageId": "pubsub-1",
                "data": encode_payload({"emailAddress": "support@example.com", "historyId": "12345"}),
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
    with client.session_factory() as db:
        connection = db.get(GmailConnection, connection_id)
        event = db.scalar(select(GmailSyncEvent).where(GmailSyncEvent.pubsub_message_id == "pubsub-1"))
        assert connection.last_notification_at is not None
        assert event is not None
        assert event.status == "queued"
        assert event.notification_history_id == "12345"
        assert event.sync_metadata["delivery"] == "queued_history_sync"
        assert queued and queued[0]["organization_id"] == organization["id"]


def test_pubsub_webhook_rejects_malformed_payload(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.webhooks.verify_pubsub_oidc_token", lambda authorization: {"email": "ok"})

    response = client.post(
        "/v1/webhooks/google/gmail",
        headers={"Authorization": "Bearer valid-token"},
        json={"message": {"messageId": "pubsub-1", "data": "not-json"}},
    )

    assert response.status_code == 400
