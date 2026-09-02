import base64

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.gmail_connection import GmailConnection
from app.models.ticket_attachment import TicketAttachment


def ticket_payload() -> dict:
    return {
        "customer_email": "customer@example.com",
        "customer_name": "Casey Customer",
        "subject": "Receipt attached",
        "message_text": "Please check the attached receipt.",
        "category": "billing",
        "priority": "medium",
        "sentiment": "neutral",
    }


def create_ticket(client: TestClient, organization_id: str) -> dict:
    response = client.post(f"/v1/orgs/{organization_id}/tickets", json=ticket_payload())
    assert response.status_code == 201
    return response.json()


def create_gmail_attachment(client: TestClient, organization_id: str, ticket_id: str, **overrides) -> TicketAttachment:
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization_id,
            connected_by_user_id="user-owner",
            gmail_email="support@example.com",
            google_account_id="google-account-1",
            encrypted_refresh_token="encrypted-token",
            scopes="gmail.readonly",
            status="active",
        )
        db.add(connection)
        db.flush()
        attachment_data = {
            "organization_id": organization_id,
            "ticket_id": ticket_id,
            "gmail_connection_id": connection.id,
            "gmail_message_id": "gmail-message-1",
            "gmail_attachment_id": "gmail-attachment-1",
            "filename": "receipt.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 128,
            "content_disposition": "attachment",
            "is_inline": False,
            "policy_status": "metadata_only",
        }
        attachment_data.update(overrides)
        attachment = TicketAttachment(**attachment_data)
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        return attachment


def enable_storage(monkeypatch) -> None:
    from app.services import attachment_service

    monkeypatch.setattr(attachment_service.settings, "attachment_storage_backend", "gcs")
    monkeypatch.setattr(attachment_service.settings, "attachment_storage_bucket", "test-bucket")
    monkeypatch.setattr(attachment_service.settings, "attachment_signed_url_ttl_seconds", 120)


async def fake_refresh_connection_access_token(db, connection):
    return "gmail-access-token", None


def test_store_attachment_downloads_from_gmail_and_writes_private_object(client: TestClient, create_org, monkeypatch) -> None:
    from app.services import attachment_service

    organization = create_org()
    ticket = create_ticket(client, organization["id"])
    attachment = create_gmail_attachment(client, organization["id"], ticket["id"])
    uploaded: dict[str, object] = {}

    async def fake_get_gmail_attachment(access_token: str, message_id: str, attachment_id: str) -> dict:
        assert access_token == "gmail-access-token"
        assert message_id == "gmail-message-1"
        assert attachment_id == "gmail-attachment-1"
        return {"data": base64.urlsafe_b64encode(b"pdf bytes").decode().rstrip("=")}

    def fake_upload(object_name: str, content: bytes, content_type: str | None) -> None:
        uploaded["object_name"] = object_name
        uploaded["content"] = content
        uploaded["content_type"] = content_type

    enable_storage(monkeypatch)
    monkeypatch.setattr(attachment_service, "refresh_connection_access_token", fake_refresh_connection_access_token)
    monkeypatch.setattr(attachment_service, "get_gmail_attachment", fake_get_gmail_attachment)
    monkeypatch.setattr(attachment_service, "_upload_gcs_object", fake_upload)

    response = client.post(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/attachments/{attachment.id}/store")

    assert response.status_code == 200
    body = response.json()
    assert body["storage_status"] == "stored"
    assert body["scan_status"] == "clean"
    assert str(uploaded["object_name"]).endswith(f"/attachments/{attachment.id}")
    assert uploaded["content"] == b"pdf bytes"
    assert uploaded["content_type"] == "application/pdf"

    with client.session_factory() as db:
        audit_actions = [
            row.action
            for row in db.scalars(select(AuditLog).where(AuditLog.organization_id == organization["id"]))
        ]
    assert "attachment.stored" in audit_actions



def test_store_attachment_blocks_eicar_content_before_upload(client: TestClient, create_org, monkeypatch) -> None:
    from app.services import attachment_service

    organization = create_org()
    ticket = create_ticket(client, organization["id"])
    attachment = create_gmail_attachment(client, organization["id"], ticket["id"])

    async def fake_get_gmail_attachment(access_token: str, message_id: str, attachment_id: str) -> dict:
        return {
            "data": base64.urlsafe_b64encode(
                b"prefix " + attachment_service.EICAR_TEST_SIGNATURE + b" suffix"
            ).decode().rstrip("=")
        }

    def fail_upload(*args, **kwargs) -> None:
        raise AssertionError("infected attachment should not be uploaded")

    enable_storage(monkeypatch)
    monkeypatch.setattr(attachment_service, "refresh_connection_access_token", fake_refresh_connection_access_token)
    monkeypatch.setattr(attachment_service, "get_gmail_attachment", fake_get_gmail_attachment)
    monkeypatch.setattr(attachment_service, "_upload_gcs_object", fail_upload)

    response = client.post(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/attachments/{attachment.id}/store")

    assert response.status_code == 400
    assert response.json()["detail"] == "Attachment failed malware scanning."
    with client.session_factory() as db:
        stored = db.get(TicketAttachment, attachment.id)
        assert stored is not None
        assert stored.policy_status == "blocked_malware"
        assert stored.storage_status == "blocked"
        assert stored.scan_status == "infected"
        assert stored.storage_object_name is None
        assert stored.notes == "Attachment blocked by basic malware scanner."
        audit_actions = [
            row.action
            for row in db.scalars(select(AuditLog).where(AuditLog.organization_id == organization["id"]))
        ]
    assert "attachment.blocked_malware" in audit_actions


def test_store_attachment_marks_scan_not_required_when_scanner_disabled(client: TestClient, create_org, monkeypatch) -> None:
    from app.services import attachment_service

    organization = create_org()
    ticket = create_ticket(client, organization["id"])
    attachment = create_gmail_attachment(client, organization["id"], ticket["id"])
    uploaded: dict[str, object] = {}

    async def fake_get_gmail_attachment(access_token: str, message_id: str, attachment_id: str) -> dict:
        return {"data": base64.urlsafe_b64encode(b"pdf bytes").decode().rstrip("=")}

    def fake_upload(object_name: str, content: bytes, content_type: str | None) -> None:
        uploaded["object_name"] = object_name

    enable_storage(monkeypatch)
    monkeypatch.setattr(attachment_service.settings, "attachment_malware_scanning_backend", "disabled")
    monkeypatch.setattr(attachment_service, "refresh_connection_access_token", fake_refresh_connection_access_token)
    monkeypatch.setattr(attachment_service, "get_gmail_attachment", fake_get_gmail_attachment)
    monkeypatch.setattr(attachment_service, "_upload_gcs_object", fake_upload)

    response = client.post(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/attachments/{attachment.id}/store")

    assert response.status_code == 200
    assert response.json()["scan_status"] == "not_required"
    assert str(uploaded["object_name"]).endswith(f"/attachments/{attachment.id}")
def test_create_attachment_download_url_requires_stored_clean_attachment(client: TestClient, create_org, monkeypatch) -> None:
    from app.services import attachment_service

    organization = create_org()
    ticket = create_ticket(client, organization["id"])
    attachment = create_gmail_attachment(
        client,
        organization["id"],
        ticket["id"],
        storage_status="stored",
        storage_object_name="orgs/org-1/tickets/ticket-1/attachments/attachment-1",
        scan_status="clean",
    )

    enable_storage(monkeypatch)
    monkeypatch.setattr(attachment_service, "_generate_gcs_signed_url", lambda object_name, filename: "https://signed.example/download")

    response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/attachments/{attachment.id}/download-url")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "attachment_id": attachment.id,
        "download_url": "https://signed.example/download",
        "expires_in_seconds": 120,
    }
    with client.session_factory() as db:
        audit_actions = [
            row.action
            for row in db.scalars(select(AuditLog).where(AuditLog.organization_id == organization["id"]))
        ]
    assert "attachment.download_url_created" in audit_actions


def test_blocked_attachment_cannot_be_stored(client: TestClient, create_org, monkeypatch) -> None:
    from app.services import attachment_service

    organization = create_org()
    ticket = create_ticket(client, organization["id"])
    attachment = create_gmail_attachment(
        client,
        organization["id"],
        ticket["id"],
        policy_status="blocked_mime",
        mime_type="application/x-msdownload",
    )

    enable_storage(monkeypatch)
    monkeypatch.setattr(attachment_service, "_upload_gcs_object", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not upload")))

    response = client.post(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/attachments/{attachment.id}/store")

    assert response.status_code == 400
    assert response.json()["detail"] == "Attachment is blocked by policy."


def test_attachment_routes_enforce_organization_membership(client: TestClient, create_org, monkeypatch) -> None:
    organization = create_org()
    ticket = create_ticket(client, organization["id"])
    attachment = create_gmail_attachment(client, organization["id"], ticket["id"])
    enable_storage(monkeypatch)
    client.current_user.update({"id": "outside-user", "email": "outside@example.com"})

    response = client.post(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/attachments/{attachment.id}/store")

    assert response.status_code == 403

def test_gcs_signed_url_uses_iam_signing_for_cloud_run_credentials(monkeypatch) -> None:
    import sys
    import types

    from app.services import attachment_service

    captured: dict[str, object] = {}

    class RuntimeCredentials:
        token = "runtime-access-token"
        service_account_email = "cloud-run@example.iam.gserviceaccount.com"

        def refresh(self, request) -> None:
            captured["refreshed"] = True

    class Signing:
        pass

    class Request:
        pass

    class FakeBlob:
        def generate_signed_url(self, **kwargs) -> str:
            captured.update(kwargs)
            return "https://storage.example/signed"

    class FakeBucket:
        def blob(self, object_name: str) -> FakeBlob:
            captured["object_name"] = object_name
            return FakeBlob()

    class FakeClient:
        _credentials = object()

        def __init__(self, project: str | None = None) -> None:
            captured["project"] = project

        def bucket(self, bucket_name: str | None) -> FakeBucket:
            captured["bucket"] = bucket_name
            return FakeBucket()

    google_module = types.ModuleType("google")
    auth_module = types.ModuleType("google.auth")
    credentials_module = types.ModuleType("google.auth.credentials")
    transport_module = types.ModuleType("google.auth.transport")
    requests_module = types.ModuleType("google.auth.transport.requests")
    cloud_module = types.ModuleType("google.cloud")
    storage_module = types.ModuleType("google.cloud.storage")

    auth_module.default = lambda scopes: (RuntimeCredentials(), "support-triage")
    credentials_module.Signing = Signing
    requests_module.Request = Request
    storage_module.Client = FakeClient
    google_module.auth = auth_module
    cloud_module.storage = storage_module

    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.auth", auth_module)
    monkeypatch.setitem(sys.modules, "google.auth.credentials", credentials_module)
    monkeypatch.setitem(sys.modules, "google.auth.transport", transport_module)
    monkeypatch.setitem(sys.modules, "google.auth.transport.requests", requests_module)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_module)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", storage_module)
    monkeypatch.setattr(attachment_service.settings, "google_cloud_project_id", "support-triage")
    monkeypatch.setattr(attachment_service.settings, "attachment_storage_bucket", "attachments")
    monkeypatch.setattr(attachment_service.settings, "attachment_signed_url_ttl_seconds", 120)
    monkeypatch.setattr(attachment_service.settings, "attachment_signing_service_account_email", None)

    url = attachment_service._generate_gcs_signed_url("orgs/org/tickets/ticket/attachments/file", "receipt.pdf")

    assert url == "https://storage.example/signed"
    assert captured["project"] == "support-triage"
    assert captured["bucket"] == "attachments"
    assert captured["object_name"] == "orgs/org/tickets/ticket/attachments/file"
    assert captured["refreshed"] is True
    assert captured["service_account_email"] == "cloud-run@example.iam.gserviceaccount.com"
    assert captured["access_token"] == "runtime-access-token"
    assert captured["response_disposition"] == 'attachment; filename="receipt.pdf"'
