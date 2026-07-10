import base64
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.encryption import encrypt_secret
from app.models.gmail_connection import GmailConnection
from app.models.job_run import JobRun
from app.models.mail_import_rule import MailImportRule
from app.models.ticket import Ticket


def encoded_body(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


def gmail_message(message_id: str, subject: str = "Need help") -> dict:
    return {
        "id": message_id,
        "threadId": f"thread-{message_id}",
        "internalDate": "1704067200000",
        "snippet": "snippet text",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "Casey Customer <casey@example.com>"},
                {"name": "Subject", "value": subject},
                {"name": "Date", "value": "Mon, 01 Jan 2024 12:00:00 +0000"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": encoded_body("Hello support team")},
                },
                {
                    "mimeType": "text/html",
                    "body": {"data": encoded_body("<p>Hello support team</p>")},
                },
            ],
        },
    }


def create_connection(client: TestClient, organization_id: str) -> str:
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


def test_sync_gmail_imports_messages_as_tickets(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])

    async def fake_refresh_gmail_access_token(refresh_token: str):
        assert refresh_token == "refresh-token"
        return "access-token", datetime.now(UTC)

    async def fake_list_gmail_message_ids(access_token: str, label_ids, unread_only: bool, max_results: int):
        assert access_token == "access-token"
        assert label_ids == []
        assert unread_only is True
        return ["gmail-1", "gmail-2"]

    async def fake_get_gmail_message(access_token: str, message_id: str):
        return gmail_message(message_id, subject=f"Subject {message_id}")

    monkeypatch.setattr("app.services.email_import_service.refresh_gmail_access_token", fake_refresh_gmail_access_token)
    monkeypatch.setattr("app.services.email_import_service.list_gmail_message_ids", fake_list_gmail_message_ids)
    monkeypatch.setattr("app.services.email_import_service.get_gmail_message", fake_get_gmail_message)

    response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync",
        json={"max_results": 20},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["job_metadata"]["imported_count"] == 2

    tickets_response = client.get(f"/v1/orgs/{organization['id']}/tickets")
    tickets = tickets_response.json()
    assert len(tickets) == 2
    assert {ticket["gmail_message_id"] for ticket in tickets} == {"gmail-1", "gmail-2"}


def test_sync_gmail_deduplicates_existing_messages(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])

    async def fake_refresh_gmail_access_token(refresh_token: str):
        return "access-token", datetime.now(UTC)

    async def fake_list_gmail_message_ids(access_token: str, label_ids, unread_only: bool, max_results: int):
        return ["gmail-1"]

    async def fake_get_gmail_message(access_token: str, message_id: str):
        return gmail_message(message_id)

    monkeypatch.setattr("app.services.email_import_service.refresh_gmail_access_token", fake_refresh_gmail_access_token)
    monkeypatch.setattr("app.services.email_import_service.list_gmail_message_ids", fake_list_gmail_message_ids)
    monkeypatch.setattr("app.services.email_import_service.get_gmail_message", fake_get_gmail_message)

    first_response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync",
        json={"max_results": 20},
    )
    second_response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync",
        json={"max_results": 20},
    )

    assert first_response.json()["job_metadata"]["imported_count"] == 1
    assert second_response.json()["job_metadata"]["imported_count"] == 0
    assert second_response.json()["job_metadata"]["skipped_count"] == 1

    with client.session_factory() as db:
        assert len(list(db.scalars(select(Ticket)))) == 1
        assert len(list(db.scalars(select(JobRun).where(JobRun.job_type == "gmail_import")))) == 2
        assert len(list(db.scalars(select(JobRun).where(JobRun.job_type == "ai_triage")))) == 1


def test_sync_rejects_inactive_import_rule(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])
    with client.session_factory() as db:
        rule = db.scalar(select(MailImportRule).where(MailImportRule.gmail_connection_id == connection_id))
        rule.is_active = False
        db.commit()

    response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync",
        json={"max_results": 20},
    )

    assert response.status_code == 400


def test_queue_gmail_import_creates_queued_job(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])
    calls = []

    class StubDispatchedTask:
        message_id = "gmail-import-message"
        topic = "local-gmail-import"

    def fake_publish(*, job_id, organization_id, connection_id, actor_id, actor_email, max_results):
        calls.append(
            {
                "job_id": job_id,
                "organization_id": organization_id,
                "connection_id": connection_id,
                "actor_id": actor_id,
                "actor_email": actor_email,
                "max_results": max_results,
            }
        )
        return StubDispatchedTask()

    monkeypatch.setattr("app.services.job_queue_service.publish_gmail_import_task", fake_publish)

    response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync/queue",
        json={"max_results": 10},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_metadata"]["gmail_connection_id"] == connection_id
    assert body["job_metadata"]["max_results"] == 10
    assert calls == [
        {
            "job_id": body["id"],
            "organization_id": organization["id"],
            "connection_id": connection_id,
            "actor_id": "user-owner",
            "actor_email": "owner@example.com",
            "max_results": 10,
        }
    ]

    job_response = client.get(f"/v1/orgs/{organization['id']}/jobs/{body['id']}")
    assert job_response.status_code == 200
    assert job_response.json()["id"] == body["id"]


def test_queue_gmail_import_marks_job_failed_when_broker_is_down(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])

    def fake_publish(*args, **kwargs):
        raise RuntimeError("pubsub unavailable")

    monkeypatch.setattr("app.services.job_queue_service.publish_gmail_import_task", fake_publish)

    response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync/queue",
        json={"max_results": 10},
    )

    assert response.status_code == 503
    with client.session_factory() as db:
        job = db.scalar(select(JobRun).where(JobRun.status == "failed"))
        assert job is not None
        assert "Could not enqueue" in (job.error_message or "")
