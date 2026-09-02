import base64
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.encryption import encrypt_secret
from app.models.gmail_connection import GmailConnection
from app.models.job_run import JobRun
from app.models.mail_import_rule import MailImportRule
from app.models.ticket import Ticket
from app.models.ticket_attachment import TicketAttachment


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


def test_sync_gmail_skips_unfetchable_messages(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])

    async def fake_refresh_gmail_access_token(refresh_token: str):
        return "access-token", datetime.now(UTC)

    async def fake_list_gmail_message_ids(access_token: str, label_ids, unread_only: bool, max_results: int):
        return ["gmail-bad", "gmail-good"]

    async def fake_get_gmail_message(access_token: str, message_id: str):
        if message_id == "gmail-bad":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gmail message fetch failed: status=404; reason=notFound",
            )
        return gmail_message(message_id, subject=f"Subject {message_id}")

    monkeypatch.setattr("app.services.email_import_service.refresh_gmail_access_token", fake_refresh_gmail_access_token)
    monkeypatch.setattr("app.services.email_import_service.list_gmail_message_ids", fake_list_gmail_message_ids)
    monkeypatch.setattr("app.services.email_import_service.get_gmail_message", fake_get_gmail_message)

    response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync",
        json={"max_results": 20},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["job_metadata"]["imported_count"] == 1
    assert body["job_metadata"]["skipped_count"] == 1
    assert body["job_metadata"]["message_errors"][0]["message_id"] == "gmail-bad"

    with client.session_factory() as db:
        tickets = list(db.scalars(select(Ticket)))
    assert [ticket.gmail_message_id for ticket in tickets] == ["gmail-good"]

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


def test_sync_endpoint_queues_import_when_pubsub_backend_is_enabled(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    monkeypatch.setattr(settings, "task_queue_backend", "pubsub")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])
    calls = []

    class StubDispatchedTask:
        message_id = "gmail-import-message"
        topic = "local-gmail-import"

    def fake_publish(*, job_id, organization_id, connection_id, actor_id, actor_email, max_results):
        calls.append(job_id)
        return StubDispatchedTask()

    monkeypatch.setattr("app.services.job_queue_service.publish_gmail_import_task", fake_publish)

    first = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync",
        json={"max_results": 10},
    )
    second = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync",
        json={"max_results": 10},
    )

    assert first.status_code == 200
    assert first.json()["status"] == "queued"
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert calls == [first.json()["id"]]
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


def test_queue_gmail_import_reuses_active_job(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])
    calls = []

    class StubDispatchedTask:
        message_id = "gmail-import-message"
        topic = "local-gmail-import"

    def fake_publish(*, job_id, organization_id, connection_id, actor_id, actor_email, max_results):
        calls.append(job_id)
        return StubDispatchedTask()

    monkeypatch.setattr("app.services.job_queue_service.publish_gmail_import_task", fake_publish)

    first = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync/queue",
        json={"max_results": 10},
    )
    second = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync/queue",
        json={"max_results": 10},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["status"] == "queued"
    assert calls == [first.json()["id"]]

    with client.session_factory() as db:
        jobs = list(db.scalars(select(JobRun).where(JobRun.job_type == "gmail_import")))
    assert len(jobs) == 1


def test_queue_gmail_import_marks_stale_active_job_before_new_job(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])
    old_started_at = datetime.now(UTC) - timedelta(minutes=10)
    calls = []

    with client.session_factory() as db:
        stale_job = JobRun(
            organization_id=organization["id"],
            job_type="gmail_import",
            queue_name="gmail_sync",
            status="running",
            related_resource_type="gmail_connection",
            related_resource_id=connection_id,
            started_at=old_started_at,
            created_at=old_started_at,
            job_metadata={"gmail_connection_id": connection_id, "max_results": 20},
        )
        db.add(stale_job)
        db.commit()
        stale_job_id = stale_job.id

    class StubDispatchedTask:
        message_id = "gmail-import-message"
        topic = "local-gmail-import"

    def fake_publish(*, job_id, organization_id, connection_id, actor_id, actor_email, max_results):
        calls.append(job_id)
        return StubDispatchedTask()

    monkeypatch.setattr("app.services.job_queue_service.publish_gmail_import_task", fake_publish)

    response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync/queue",
        json={"max_results": 10},
    )

    assert response.status_code == 202
    assert response.json()["id"] != stale_job_id
    assert calls == [response.json()["id"]]

    with client.session_factory() as db:
        stale = db.get(JobRun, stale_job_id)
        current = db.get(JobRun, response.json()["id"])
    assert stale.status == "failed"
    assert stale.error_code == "stale_running_import"
    assert current.status == "queued"
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


def test_sync_gmail_captures_long_gmail_attachment_ids(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])
    long_attachment_id = "A" * 420

    async def fake_refresh_gmail_access_token(refresh_token: str):
        return "access-token", datetime.now(UTC)

    async def fake_list_gmail_message_ids(access_token: str, label_ids, unread_only: bool, max_results: int):
        return ["gmail-long-attachment"]

    async def fake_get_gmail_message(access_token: str, message_id: str):
        message = gmail_message(message_id, subject="Attachment with long ID")
        message["payload"]["mimeType"] = "multipart/mixed"
        message["payload"]["parts"].append(
            {
                "filename": "resume.pdf",
                "mimeType": "application/pdf",
                "headers": [{"name": "Content-Disposition", "value": "attachment; filename=resume.pdf"}],
                "body": {"attachmentId": long_attachment_id, "size": 12345},
            }
        )
        return message

    monkeypatch.setattr("app.services.email_import_service.refresh_gmail_access_token", fake_refresh_gmail_access_token)
    monkeypatch.setattr("app.services.email_import_service.list_gmail_message_ids", fake_list_gmail_message_ids)
    monkeypatch.setattr("app.services.email_import_service.get_gmail_message", fake_get_gmail_message)

    response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync",
        json={"max_results": 20},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    with client.session_factory() as db:
        attachment = db.scalar(select(TicketAttachment).where(TicketAttachment.gmail_message_id == "gmail-long-attachment"))
    assert attachment is not None
    assert attachment.gmail_attachment_id == long_attachment_id
def test_sync_gmail_captures_attachment_metadata_only(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = create_connection(client, organization["id"])

    async def fake_refresh_gmail_access_token(refresh_token: str):
        return "access-token", datetime.now(UTC)

    async def fake_list_gmail_message_ids(access_token: str, label_ids, unread_only: bool, max_results: int):
        return ["gmail-attachment-1"]

    async def fake_get_gmail_message(access_token: str, message_id: str):
        message = gmail_message(message_id, subject="Attachment included")
        message["payload"]["mimeType"] = "multipart/mixed"
        message["payload"]["parts"].append(
            {
                "filename": "invoice.pdf",
                "mimeType": "application/pdf",
                "headers": [{"name": "Content-Disposition", "value": "attachment; filename=invoice.pdf"}],
                "body": {"attachmentId": "att-1", "size": 12345},
            }
        )
        return message

    monkeypatch.setattr("app.services.email_import_service.refresh_gmail_access_token", fake_refresh_gmail_access_token)
    monkeypatch.setattr("app.services.email_import_service.list_gmail_message_ids", fake_list_gmail_message_ids)
    monkeypatch.setattr("app.services.email_import_service.get_gmail_message", fake_get_gmail_message)

    response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync",
        json={"max_results": 20},
    )

    assert response.status_code == 200
    with client.session_factory() as db:
        ticket = db.scalar(select(Ticket).where(Ticket.gmail_message_id == "gmail-attachment-1"))
        attachments = list(db.scalars(select(TicketAttachment).where(TicketAttachment.ticket_id == ticket.id)))

    assert len(attachments) == 1
    attachment = attachments[0]
    assert attachment.filename == "invoice.pdf"
    assert attachment.mime_type == "application/pdf"
    assert attachment.size_bytes == 12345
    assert attachment.gmail_attachment_id == "att-1"
    assert attachment.policy_status == "metadata_only"
    assert attachment.storage_status == "not_downloaded"
    assert attachment.scan_status == "not_scanned"

    detail_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["attachments"][0]["filename"] == "invoice.pdf"
    assert detail["attachments"][0]["storage_status"] == "not_downloaded"
