from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.encryption import encrypt_secret
from app.models.audit_log import AuditLog
from app.models.gmail_connection import GmailConnection
from app.models.member import MemberRole, MemberStatus, OrganizationMember
from app.models.workspace_settings import WorkspaceSettings

def test_create_organization_makes_current_user_owner(client: TestClient, create_org) -> None:
    organization = create_org()

    response = client.get("/v1/me")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "user-owner"
    assert body["organizations"] == [
        {
            "id": organization["id"],
            "name": "Acme Support",
            "slug": "acme-support",
            "role": "owner",
        }
    ]


def test_user_cannot_access_organization_they_do_not_belong_to(
    client: TestClient,
    create_org,
) -> None:
    organization = create_org()
    client.current_user.update({"id": "different-user", "email": "different@example.com"})

    response = client.get(f"/v1/organizations/{organization['id']}")

    assert response.status_code == 403


def test_owner_can_invite_agent(client: TestClient, create_org) -> None:
    organization = create_org()

    response = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "agent@example.com", "role": "agent"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "agent@example.com"
    assert body["role"] == "agent"
    assert body["status"] == "invited"


def test_agent_cannot_invite_members(client: TestClient, create_org) -> None:
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
        db.commit()

    client.current_user.update({"id": "agent-user", "email": "agent@example.com"})

    response = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "new-agent@example.com", "role": "agent"},
    )

    assert response.status_code == 403


def test_admin_can_invite_agent_but_not_owner(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        db.add(
            OrganizationMember(
                organization_id=organization["id"],
                user_id="admin-user",
                email="admin@example.com",
                role=MemberRole.ADMIN.value,
                status=MemberStatus.ACTIVE.value,
            )
        )
        db.commit()

    client.current_user.update({"id": "admin-user", "email": "admin@example.com"})

    agent_response = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "new-agent@example.com", "role": "agent"},
    )
    owner_response = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "new-owner@example.com", "role": "owner"},
    )

    assert agent_response.status_code == 201
    assert owner_response.status_code == 403


def test_owner_can_export_organization_data_without_gmail_tokens(client: TestClient, create_org) -> None:
    organization = create_org()
    ticket_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": "Need help",
            "message_text": "Please help with my account.",
        },
    )
    assert ticket_response.status_code == 201
    with client.session_factory() as db:
        db.add(
            GmailConnection(
                organization_id=organization["id"],
                connected_by_user_id="user-owner",
                gmail_email="support@example.com",
                google_account_id="google-account-id",
                encrypted_refresh_token=encrypt_secret("refresh-token"),
                scopes="openid email https://www.googleapis.com/auth/gmail.modify",
                status="active",
                sync_status="active",
                watch_status="active",
            )
        )
        db.commit()

    response = client.get(f"/v1/organizations/{organization['id']}/export")

    assert response.status_code == 200
    body = response.json()
    assert body["organization"]["id"] == organization["id"]
    assert body["counts"]["tickets"] == 1
    assert body["counts"]["gmail_connections"] == 1
    assert body["tickets"][0]["message_text"] == "Please help with my account."
    connection_export = body["gmail_connections"][0]
    assert connection_export["gmail_email"] == "support@example.com"
    assert "encrypted_refresh_token" not in connection_export
    assert "access_token" not in str(body)
    with client.session_factory() as db:
        actions = [row.action for row in db.scalars(select(AuditLog).where(AuditLog.organization_id == organization["id"]))]
    assert "organization.export.generated" in actions


def test_agent_cannot_export_or_request_deletion(client: TestClient, create_org) -> None:
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
        db.commit()

    client.current_user.update({"id": "agent-user", "email": "agent@example.com"})

    export_response = client.get(f"/v1/organizations/{organization['id']}/export")
    deletion_response = client.post(
        f"/v1/organizations/{organization['id']}/deletion-request",
        json={"confirm": True, "reason": "cleanup"},
    )

    assert export_response.status_code == 403
    assert deletion_response.status_code == 403


def test_owner_deletion_request_pauses_workspace_and_audits(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        db.add(WorkspaceSettings(organization_id=organization["id"], sync_enabled=True, auto_triage_enabled=True, draft_creation_enabled=True))
        db.commit()

    missing_confirm = client.post(
        f"/v1/organizations/{organization['id']}/deletion-request",
        json={"confirm": False, "reason": "no longer needed"},
    )
    response = client.post(
        f"/v1/organizations/{organization['id']}/deletion-request",
        json={"confirm": True, "reason": "no longer needed"},
    )

    assert missing_confirm.status_code == 400
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "requested"
    assert body["sync_paused"] is True
    assert body["auto_triage_paused"] is True
    assert body["draft_creation_paused"] is True
    with client.session_factory() as db:
        settings = db.scalar(select(WorkspaceSettings).where(WorkspaceSettings.organization_id == organization["id"]))
        audit_log = db.scalar(select(AuditLog).where(AuditLog.action == "organization.deletion_requested"))
        memberships = list(db.scalars(select(OrganizationMember).where(OrganizationMember.organization_id == organization["id"])))
    assert settings is not None
    assert settings.sync_enabled is False
    assert settings.auto_triage_enabled is False
    assert settings.draft_creation_enabled is False
    assert audit_log is not None
    assert audit_log.audit_metadata["reason"] == "no longer needed"
    assert memberships
    assert {member.status for member in memberships} == {MemberStatus.DISABLED.value}

    me_response = client.get("/v1/me")
    assert me_response.status_code == 200
    assert me_response.json()["organizations"] == []

def test_owner_can_mark_gmail_connection_as_google_group(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization["id"],
            connected_by_user_id="user-owner",
            gmail_email="delegate@example.com",
            google_account_id="google-group-account-id",
            encrypted_refresh_token=encrypt_secret("refresh-token"),
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
            sync_status="active",
            watch_status="active",
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
        connection_id = connection.id

    response = client.patch(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}",
        json={
            "display_name": "Support Group",
            "inbox_type": "google_group",
            "shared_address": "Support@Example.com",
            "channel_notes": "Google Group forwards to this connected Gmail account.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Support Group"
    assert body["inbox_type"] == "google_group"
    assert body["shared_address"] == "support@example.com"
    assert body["channel_notes"] == "Google Group forwards to this connected Gmail account."
    with client.session_factory() as db:
        stored = db.get(GmailConnection, connection_id)
        audit_log = db.scalar(select(AuditLog).where(AuditLog.action == "gmail.connection.updated"))
    assert stored is not None
    assert stored.inbox_type == "google_group"
    assert stored.shared_address == "support@example.com"
    assert audit_log is not None
    assert audit_log.audit_metadata["inbox_type"] == "google_group"
    assert audit_log.audit_metadata["shared_address"] == "support@example.com"


def test_agent_cannot_update_gmail_connection_channel_metadata(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization["id"],
            connected_by_user_id="user-owner",
            gmail_email="delegate@example.com",
            google_account_id="agent-denied-account-id",
            encrypted_refresh_token=encrypt_secret("refresh-token"),
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
            sync_status="active",
            watch_status="active",
        )
        db.add(connection)
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
        db.refresh(connection)
        connection_id = connection.id

    client.current_user.update({"id": "agent-user", "email": "agent@example.com"})

    response = client.patch(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}",
        json={"inbox_type": "shared_mailbox", "shared_address": "help@example.com"},
    )

    assert response.status_code == 403


def test_shared_gmail_source_requires_shared_address(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization["id"],
            connected_by_user_id="user-owner",
            gmail_email="delegate@example.com",
            google_account_id="missing-shared-address-account-id",
            encrypted_refresh_token=encrypt_secret("refresh-token"),
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
            sync_status="active",
            watch_status="active",
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
        connection_id = connection.id

    response = client.patch(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}",
        json={"inbox_type": "google_group"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Shared Gmail source address is required for Google Group or shared mailbox sources"


def test_individual_gmail_source_clears_shared_address(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization["id"],
            connected_by_user_id="user-owner",
            gmail_email="delegate@example.com",
            inbox_type="shared_mailbox",
            shared_address="help@example.com",
            google_account_id="clear-shared-address-account-id",
            encrypted_refresh_token=encrypt_secret("refresh-token"),
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
            sync_status="active",
            watch_status="active",
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
        connection_id = connection.id

    response = client.patch(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}",
        json={"inbox_type": "individual"},
    )

    assert response.status_code == 200
    assert response.json()["inbox_type"] == "individual"
    assert response.json()["shared_address"] is None

def test_agent_member_cannot_create_additional_organization(client: TestClient, create_org) -> None:
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
        db.commit()

    client.current_user.update({"id": "agent-user", "email": "agent@example.com"})

    response = client.post("/v1/organizations", json={"name": "Agent Workspace"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Only owners and admins can create organizations"


def test_admin_can_request_organization_deletion(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        db.add(WorkspaceSettings(organization_id=organization["id"], sync_enabled=True, auto_triage_enabled=True, draft_creation_enabled=True))
        db.add(
            OrganizationMember(
                organization_id=organization["id"],
                user_id="admin-user",
                email="admin@example.com",
                role=MemberRole.ADMIN.value,
                status=MemberStatus.ACTIVE.value,
            )
        )
        db.commit()

    client.current_user.update({"id": "admin-user", "email": "admin@example.com"})

    response = client.post(
        f"/v1/organizations/{organization['id']}/deletion-request",
        json={"confirm": True, "reason": "Remove requested from organization manager"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "requested"
