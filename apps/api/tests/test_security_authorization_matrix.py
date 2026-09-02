from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.member import MemberRole, MemberStatus, OrganizationMember


def add_member(client: TestClient, organization_id: str, user_id: str, role: MemberRole) -> None:
    with client.session_factory() as db:
        db.add(
            OrganizationMember(
                organization_id=organization_id,
                user_id=user_id,
                email=f"{user_id}@example.com",
                role=role.value,
                status=MemberStatus.ACTIVE.value,
            )
        )
        db.commit()


def set_user(client: TestClient, user_id: str) -> None:
    client.current_user.update({"id": user_id, "email": f"{user_id}@example.com"})


def test_agent_is_denied_owner_admin_security_surfaces(client: TestClient, create_org) -> None:
    organization = create_org()
    add_member(client, organization["id"], "agent-user", MemberRole.AGENT)
    set_user(client, "agent-user")

    checks = [
        client.patch(f"/v1/orgs/{organization['id']}/workspace-settings", json={"auto_triage_enabled": False}),
        client.get(f"/v1/orgs/{organization['id']}/gmail/oauth/start"),
        client.delete(f"/v1/orgs/{organization['id']}/gmail/connections/missing-connection"),
        client.post(f"/v1/orgs/{organization['id']}/gmail/connections/missing-connection/history-sync/queue"),
        client.post(f"/v1/orgs/{organization['id']}/members/invite", json={"email": "new@example.com", "role": "agent"}),
        client.get(f"/v1/orgs/{organization['id']}/audit-logs"),
        client.get(f"/v1/orgs/{organization['id']}/operations/failures"),
    ]

    assert [response.status_code for response in checks] == [403, 403, 403, 403, 403, 403, 403]


def test_agent_can_use_allowed_ticket_workflow_surfaces(client: TestClient, create_org) -> None:
    organization = create_org()
    add_member(client, organization["id"], "agent-user", MemberRole.AGENT)
    set_user(client, "agent-user")

    create_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": "Need help",
            "message_text": "Please help with my order.",
        },
    )
    list_response = client.get(f"/v1/orgs/{organization['id']}/tickets")
    ticket_id = create_response.json()["id"]
    suggestion_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets/{ticket_id}/reply-suggestions",
        json={"body": "Thanks for reaching out."},
    )

    assert create_response.status_code == 201
    assert list_response.status_code == 200
    assert suggestion_response.status_code == 201


def test_cross_organization_resource_ids_fail_closed(client: TestClient, create_org) -> None:
    first_org = create_org("First Org")
    ticket_response = client.post(
        f"/v1/orgs/{first_org['id']}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": "First org ticket",
            "message_text": "Private ticket body.",
        },
    )
    second_org = create_org("Second Org")
    ticket_id = ticket_response.json()["id"]

    responses = [
        client.get(f"/v1/orgs/{second_org['id']}/tickets/{ticket_id}"),
        client.patch(f"/v1/orgs/{second_org['id']}/tickets/{ticket_id}", json={"priority": "high"}),
        client.get(f"/v1/orgs/{second_org['id']}/tickets/{ticket_id}/events"),
        client.post(f"/v1/orgs/{second_org['id']}/tickets/{ticket_id}/triage/retry"),
    ]

    assert all(response.status_code == 404 for response in responses)


def test_disabled_member_loses_access_immediately(client: TestClient, create_org) -> None:
    organization = create_org()
    add_member(client, organization["id"], "agent-user", MemberRole.AGENT)

    with client.session_factory() as db:
        member = db.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization["id"],
                OrganizationMember.user_id == "agent-user",
            )
        )
        member.status = MemberStatus.DISABLED.value
        db.commit()

    set_user(client, "agent-user")
    response = client.get(f"/v1/orgs/{organization['id']}/tickets")

    assert response.status_code == 403
