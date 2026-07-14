import pytest
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.encryption import encrypt_secret
from app.models.gmail_connection import GmailConnection
from app.models.mail_import_rule import MailImportRule
from app.services.gmail_token_service import refresh_connection_access_token


def create_connection(client, organization_id: str) -> str:
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization_id,
            connected_by_user_id="user-owner",
            gmail_email="support@example.com",
            google_account_id="google-account-id",
            encrypted_refresh_token=encrypt_secret("refresh-token"),
            token_key_version=settings.encryption_key_version,
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
            sync_status="active",
            watch_status="active",
        )
        db.add(connection)
        db.flush()
        db.add(MailImportRule(organization_id=organization_id, gmail_connection_id=connection.id))
        db.commit()
        return connection.id


@pytest.mark.asyncio
async def test_revoked_gmail_token_marks_reauthorization_required(client, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    monkeypatch.setattr(settings, "encryption_key_version", 7)
    organization = create_org()
    connection_id = create_connection(client, organization["id"])

    async def fake_refresh(refresh_token: str):
        assert refresh_token == "refresh-token"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_grant")

    monkeypatch.setattr("app.services.gmail_token_service.refresh_gmail_access_token", fake_refresh)

    with client.session_factory() as db:
        connection = db.get(GmailConnection, connection_id)
        with pytest.raises(HTTPException) as exc_info:
            await refresh_connection_access_token(db, connection)
        db.refresh(connection)

    assert exc_info.value.status_code == 401
    assert connection.status == "reauthorization_required"
    assert connection.sync_status == "reauthorization_required"
    assert connection.watch_status == "reauthorization_required"
    assert connection.reauthorization_required_at is not None
    assert connection.reauthorization_reason == "token_revoked"
    assert connection.last_token_error_at is not None


def test_gmail_connection_exposes_key_version_without_token(client, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    monkeypatch.setattr(settings, "encryption_key_version", 3)
    organization = create_org()
    create_connection(client, organization["id"])

    response = client.get(f"/v1/orgs/{organization['id']}/gmail/connections")

    assert response.status_code == 200
    body = response.json()[0]
    assert body["token_key_version"] == 3
    assert "encrypted_refresh_token" not in body
    assert "refresh_token" not in body


@pytest.mark.asyncio
async def test_refresh_access_token_can_decrypt_previous_key_version(client, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "old-encryption-key")
    monkeypatch.setattr(settings, "encryption_key_version", 7)
    monkeypatch.setattr(settings, "encryption_keyring", None)
    organization = create_org()
    connection_id = create_connection(client, organization["id"])

    monkeypatch.setattr(settings, "encryption_key", "new-encryption-key")
    monkeypatch.setattr(settings, "encryption_key_version", 8)
    monkeypatch.setattr(settings, "encryption_keyring", "7:old-encryption-key")

    async def fake_refresh(refresh_token: str):
        assert refresh_token == "refresh-token"
        return "access-token", None

    with client.session_factory() as db:
        connection = db.get(GmailConnection, connection_id)
        access_token, expires_at = await refresh_connection_access_token(db, connection, fake_refresh)

    assert access_token == "access-token"
    assert expires_at is None
