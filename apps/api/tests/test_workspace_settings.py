from fastapi.testclient import TestClient

from app.models.member import MemberRole, MemberStatus, OrganizationMember


def test_member_can_read_default_workspace_settings(client: TestClient, create_org) -> None:
    organization = create_org()

    response = client.get(f"/v1/orgs/{organization['id']}/workspace-settings")

    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == organization["id"]
    assert body["default_reply_signature"] == "Best regards,\nCustomer Support Team"
    assert body["auto_triage_enabled"] is True
    assert body["draft_requires_approval"] is True
    assert body["attachment_ai_processing_enabled"] is False


def test_owner_can_update_workspace_settings(client: TestClient, create_org) -> None:
    organization = create_org()

    response = client.patch(
        f"/v1/orgs/{organization['id']}/workspace-settings",
        json={
            "default_reply_signature": "Regards,\nPilot Team",
            "auto_triage_enabled": False,
            "draft_requires_approval": True,
            "attachment_ai_processing_enabled": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["default_reply_signature"] == "Regards,\nPilot Team"
    assert body["auto_triage_enabled"] is False
    assert body["attachment_ai_processing_enabled"] is True


def test_agent_cannot_update_workspace_settings(client: TestClient, create_org) -> None:
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
    response = client.patch(
        f"/v1/orgs/{organization['id']}/workspace-settings",
        json={"default_reply_signature": "Agent edit"},
    )

    assert response.status_code == 403


def test_user_outside_organization_cannot_read_workspace_settings(client: TestClient, create_org) -> None:
    organization = create_org()
    client.current_user.update({"id": "outside-user", "email": "outside@example.com"})

    response = client.get(f"/v1/orgs/{organization['id']}/workspace-settings")

    assert response.status_code == 403