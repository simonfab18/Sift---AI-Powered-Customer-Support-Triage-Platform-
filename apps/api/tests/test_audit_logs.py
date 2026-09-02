from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.member import MemberRole, MemberStatus, OrganizationMember
from app.models.organization import Organization
from app.services.audit_log_service import create_audit_log


def test_owner_can_list_audit_logs(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        create_audit_log(
            db,
            organization_id=organization["id"],
            actor_user_id="user-owner",
            action="test.action",
            resource_type="test_resource",
            resource_id="resource-1",
            ip_address="127.0.0.1",
            user_agent="pytest",
            metadata={"safe": "value"},
        )
        db.commit()

    response = client.get(f"/v1/orgs/{organization['id']}/audit-logs")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["action"] == "test.action"
    assert body[0]["metadata"] == {"safe": "value"}


def test_audit_log_access_requires_organization_membership(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        other_org = Organization(name="Other Org", slug="other-org")
        db.add(other_org)
        db.flush()
        create_audit_log(
            db,
            organization_id=other_org.id,
            actor_user_id="other-user",
            action="test.action",
            resource_type="test_resource",
        )
        db.commit()
        other_org_id = other_org.id

    response = client.get(f"/v1/orgs/{other_org_id}/audit-logs")

    assert response.status_code == 403
    own_response = client.get(f"/v1/orgs/{organization['id']}/audit-logs")
    assert own_response.status_code == 200


def test_sensitive_fields_are_redacted_from_audit_logs(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        create_audit_log(
            db,
            organization_id=organization["id"],
            actor_user_id="user-owner",
            action="test.secret_logged",
            resource_type="test_resource",
            metadata={
                "refresh_token": "refresh-secret",
                "client_secret": "client-secret",
                "nested": {"access_token": "access-secret", "safe": "kept"},
                "items": [{"api_key": "api-secret"}],
            },
        )
        db.commit()

    response = client.get(f"/v1/orgs/{organization['id']}/audit-logs")

    assert response.status_code == 200
    metadata = response.json()[0]["metadata"]
    assert metadata["refresh_token"] == "[REDACTED]"
    assert metadata["client_secret"] == "[REDACTED]"
    assert metadata["nested"]["access_token"] == "[REDACTED]"
    assert metadata["nested"]["safe"] == "kept"
    assert metadata["items"][0]["api_key"] == "[REDACTED]"


def test_agents_cannot_read_audit_logs_and_non_members_cannot(client: TestClient, create_org) -> None:
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
        create_audit_log(
            db,
            organization_id=organization["id"],
            actor_user_id="user-owner",
            action="test.action",
            resource_type="test_resource",
        )
        db.commit()

    client.current_user.update({"id": "agent-user", "email": "agent@example.com"})
    agent_response = client.get(f"/v1/orgs/{organization['id']}/audit-logs")
    assert agent_response.status_code == 403

    client.current_user.update({"id": "outside-user", "email": "outside@example.com"})
    outside_response = client.get(f"/v1/orgs/{organization['id']}/audit-logs")
    assert outside_response.status_code == 403


def test_audit_logs_are_persisted_with_redacted_metadata(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        create_audit_log(
            db,
            organization_id=organization["id"],
            actor_user_id="user-owner",
            action="test.persisted_redaction",
            resource_type="test_resource",
            metadata={"password": "plain-password", "public": "visible"},
        )
        db.commit()
        audit_log = db.scalar(select(AuditLog).where(AuditLog.action == "test.persisted_redaction"))

    assert audit_log is not None
    assert audit_log.audit_metadata["password"] == "[REDACTED]"
    assert audit_log.audit_metadata["public"] == "visible"
