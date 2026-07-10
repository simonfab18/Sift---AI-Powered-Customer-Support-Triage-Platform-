from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.encryption import decrypt_secret
from app.models.audit_log import AuditLog
from app.models.gmail_connection import GmailConnection
from app.models.gmail_oauth_state import GmailOAuthState
from app.models.mail_import_rule import MailImportRule
from app.models.member import MemberRole, MemberStatus, OrganizationMember


def test_owner_can_start_gmail_oauth(client: TestClient, create_org, monkeypatch) -> None:
    organization = create_org()
    monkeypatch.setattr(settings, "google_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_redirect_uri", "http://localhost:8000/v1/gmail/oauth/callback")

    response = client.get(f"/v1/orgs/{organization['id']}/gmail/oauth/start")

    assert response.status_code == 200
    body = response.json()
    assert body["state"]
    assert "accounts.google.com" in body["auth_url"]
    assert "access_type=offline" in body["auth_url"]
    with client.session_factory() as db:
        state = db.scalar(select(GmailOAuthState).where(GmailOAuthState.state == body["state"]))
        assert state is not None
        assert state.organization_id == organization["id"]


def test_agent_cannot_start_gmail_oauth(client: TestClient, create_org, monkeypatch) -> None:
    organization = create_org()
    monkeypatch.setattr(settings, "google_client_id", "google-client-id")
    with client.session_factory() as db:
        db.add(
            OrganizationMember(
                organization_id=organization["id"],
                user_id="agent-user",
                email="agent@example.com",
                role=MemberRole.AGENT.value,
                status=MemberStatus.ACTIVE.value,
            )
        )
        db.commit()

    client.current_user.update({"id": "agent-user", "email": "agent@example.com"})
    response = client.get(f"/v1/orgs/{organization['id']}/gmail/oauth/start")

    assert response.status_code == 403


def test_oauth_callback_creates_connection_with_encrypted_refresh_token(
    client: TestClient,
    create_org,
    monkeypatch,
) -> None:
    organization = create_org()
    monkeypatch.setattr(settings, "google_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "google-client-secret")
    monkeypatch.setattr(settings, "google_redirect_uri", "http://localhost:8000/v1/gmail/oauth/callback")
    monkeypatch.setattr(settings, "frontend_origin", "https://app.example.com")
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")

    async def fake_exchange_oauth_code(code: str):
        assert code == "callback-code"
        return {
            "access_token": "google-access-token",
            "refresh_token": "google-refresh-token",
            "expires_in": 3600,
            "scope": "openid email https://www.googleapis.com/auth/gmail.modify",
        }

    async def fake_fetch_google_userinfo(access_token: str):
        assert access_token == "google-access-token"
        return {"email": "support@example.com", "sub": "google-account-id"}

    monkeypatch.setattr(
        "app.services.gmail_connection_service.exchange_oauth_code",
        fake_exchange_oauth_code,
    )
    monkeypatch.setattr(
        "app.services.gmail_connection_service.fetch_google_userinfo",
        fake_fetch_google_userinfo,
    )

    start_response = client.get(f"/v1/orgs/{organization['id']}/gmail/oauth/start")
    state = start_response.json()["state"]
    callback_response = client.get(
        f"/v1/gmail/oauth/callback?state={state}&code=callback-code",
        follow_redirects=False,
    )

    assert callback_response.status_code == 303
    assert callback_response.headers["location"].startswith(
        "https://app.example.com/dashboard/settings/gmail?gmail=connected&connection_id="
    )

    with client.session_factory() as db:
        connection = db.scalar(select(GmailConnection))
        import_rule = db.scalar(select(MailImportRule))
        oauth_state = db.scalar(select(GmailOAuthState))
        assert connection is not None
        assert connection.encrypted_refresh_token != "google-refresh-token"
        assert decrypt_secret(connection.encrypted_refresh_token) == "google-refresh-token"
        assert import_rule is not None
        assert import_rule.gmail_connection_id == connection.id
        assert import_rule.import_unread_only is True
        assert oauth_state is None
        audit_log = db.scalar(select(AuditLog))
        assert audit_log is not None
        assert audit_log.action == "gmail.connection.connected"
        assert audit_log.resource_id == connection.id
        assert "refresh_token" not in audit_log.audit_metadata
        assert "access_token" not in audit_log.audit_metadata
        assert audit_log.audit_metadata["gmail_email"] == "support@example.com"
        assert connection.watch_status == "not_configured"
        assert connection.sync_status == "degraded"


def test_oauth_callback_rejects_invalid_state(client: TestClient) -> None:
    response = client.get("/v1/gmail/oauth/callback?state=bad-state&code=callback-code")

    assert response.status_code == 400


def test_members_can_list_connections_and_admin_can_update_import_rule(
    client: TestClient,
    create_org,
    monkeypatch,
) -> None:
    organization = create_org()
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization["id"],
            connected_by_user_id="user-owner",
            gmail_email="support@example.com",
            google_account_id="google-account-id",
            encrypted_refresh_token="encrypted-token",
            scopes="openid email",
            status="active",
        )
        db.add(connection)
        db.flush()
        rule = MailImportRule(
            organization_id=organization["id"],
            gmail_connection_id=connection.id,
        )
        db.add(rule)
        db.commit()
        rule_id = rule.id

    list_response = client.get(f"/v1/orgs/{organization['id']}/gmail/connections")
    rules_response = client.get(f"/v1/orgs/{organization['id']}/gmail/import-rules")
    patch_response = client.patch(
        f"/v1/orgs/{organization['id']}/gmail/import-rules/{rule_id}",
        json={"support_label_id": "Label_support", "import_unread_only": False},
    )

    assert list_response.status_code == 200
    assert list_response.json()[0]["gmail_email"] == "support@example.com"
    assert "encrypted_refresh_token" not in list_response.json()[0]
    assert rules_response.status_code == 200
    assert patch_response.status_code == 200
    assert patch_response.json()["support_label_id"] == "Label_support"
    assert patch_response.json()["import_unread_only"] is False


def test_agent_cannot_revoke_gmail_connection(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        db.add(
            OrganizationMember(
                organization_id=organization["id"],
                user_id="agent-user",
                email="agent@example.com",
                role=MemberRole.AGENT.value,
                status=MemberStatus.ACTIVE.value,
            )
        )
        connection = GmailConnection(
            organization_id=organization["id"],
            connected_by_user_id="user-owner",
            gmail_email="support@example.com",
            google_account_id="google-account-id",
            encrypted_refresh_token="encrypted-token",
            scopes="openid email",
            status="active",
        )
        db.add(connection)
        db.commit()
        connection_id = connection.id

    client.current_user.update({"id": "agent-user", "email": "agent@example.com"})
    response = client.delete(f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}")

    assert response.status_code == 403

