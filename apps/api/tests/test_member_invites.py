from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.models.member import MemberStatus, OrganizationMember


def test_invite_member_returns_email_delivery_status_when_smtp_missing(client: TestClient, create_org, monkeypatch) -> None:
    organization = create_org()
    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "smtp_from_email", None)

    response = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "agent@example.com", "role": "agent"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "agent@example.com"
    assert body["status"] == "invited"
    assert body["invite_email_delivery_status"] == "skipped"
    assert body["invite_email_delivery_detail"] == "SMTP is not configured."


def test_invited_member_is_activated_when_same_email_signs_in(client: TestClient, create_org) -> None:
    organization = create_org()
    invite_response = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "agent@example.com", "role": "agent"},
    )
    assert invite_response.status_code == 201
    invited_member_id = invite_response.json()["id"]

    client.current_user["id"] = "user-agent"
    client.current_user["email"] = "agent@example.com"

    me_response = client.get("/v1/me")

    assert me_response.status_code == 200
    organizations = me_response.json()["organizations"]
    assert organizations == [{"id": organization["id"], "name": organization["name"], "slug": organization["slug"], "role": "agent", "joined_via_invite": True}]

    with client.session_factory() as db:
        member = db.scalar(select(OrganizationMember).where(OrganizationMember.id == invited_member_id))
        assert member is not None
        assert member.user_id == "user-agent"
        assert member.status == MemberStatus.ACTIVE.value

def test_send_teammate_invite_email_uses_smtp(monkeypatch) -> None:
    from app.services.email_service import send_teammate_invite_email

    sent: dict[str, object] = {}

    class DummySMTP:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def __enter__(self) -> "DummySMTP":
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

        def starttls(self) -> None:
            sent["tls"] = True

        def login(self, username: str, password: str) -> None:
            sent["username"] = username
            sent["password"] = password

        def send_message(self, message) -> None:
            sent["to"] = message["To"]
            sent["from"] = message["From"]
            sent["subject"] = message["Subject"]
            html_body = message.get_body(preferencelist=("html",))
            sent["payload"] = html_body.get_content() if html_body else str(message)

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 2525)
    monkeypatch.setattr(settings, "smtp_username", "smtp-user")
    monkeypatch.setattr(settings, "smtp_password", "smtp-password")
    monkeypatch.setattr(settings, "smtp_from_email", "invites@sift.test")
    monkeypatch.setattr(settings, "smtp_from_name", "Sift Invites")
    monkeypatch.setattr(settings, "smtp_use_tls", True)
    monkeypatch.setattr(settings, "invite_email_enabled", True)
    monkeypatch.setattr(settings, "frontend_origin", "https://app.sift.test")
    monkeypatch.setattr("app.services.email_service.smtplib.SMTP", DummySMTP)

    result = send_teammate_invite_email(
        to_email="agent@example.com",
        organization_name="Coco Technology",
        organization_id="org-123",
        role="agent",
        invited_by_email="owner@example.com",
    )

    assert result.status == "sent"
    assert sent["host"] == "smtp.example.com"
    assert sent["port"] == 2525
    assert sent["tls"] is True
    assert sent["username"] == "smtp-user"
    assert sent["to"] == "agent@example.com"
    assert sent["subject"] == "You were invited to Sift for Coco Technology"
    assert "https://app.sift.test/signup?" in sent["payload"]
    assert "invite_email=agent%40example.com" in sent["payload"]

def test_remove_invited_member_disables_membership(client: TestClient, create_org) -> None:
    organization = create_org()
    invite_response = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "remove-me@example.com", "role": "agent"},
    )
    assert invite_response.status_code == 201
    invited_member_id = invite_response.json()["id"]

    delete_response = client.delete(f"/v1/orgs/{organization['id']}/members/{invited_member_id}")

    assert delete_response.status_code == 204
    with client.session_factory() as db:
        member = db.scalar(select(OrganizationMember).where(OrganizationMember.id == invited_member_id))
        assert member is not None
        assert member.status == "disabled"

def test_removed_member_is_hidden_from_member_list(client: TestClient, create_org) -> None:
    organization = create_org()
    invite_response = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "hidden-after-remove@example.com", "role": "agent"},
    )
    assert invite_response.status_code == 201
    invited_member_id = invite_response.json()["id"]

    delete_response = client.delete(f"/v1/orgs/{organization['id']}/members/{invited_member_id}")
    assert delete_response.status_code == 204

    list_response = client.get(f"/v1/orgs/{organization['id']}/members")
    assert list_response.status_code == 200
    emails = {member["email"] for member in list_response.json()}
    assert "hidden-after-remove@example.com" not in emails


def test_current_user_cannot_remove_or_change_own_membership(client: TestClient, create_org) -> None:
    organization = create_org()
    members_response = client.get(f"/v1/orgs/{organization['id']}/members")
    assert members_response.status_code == 200
    owner_member = next(member for member in members_response.json() if member["user_id"] == "user-owner")

    update_response = client.patch(
        f"/v1/orgs/{organization['id']}/members/{owner_member['id']}",
        json={"role": "agent"},
    )
    assert update_response.status_code == 400
    assert update_response.json()["detail"] == "You cannot modify your own membership"

    delete_response = client.delete(f"/v1/orgs/{organization['id']}/members/{owner_member['id']}")
    assert delete_response.status_code == 400
    assert delete_response.json()["detail"] == "You cannot remove yourself"

def test_members_include_assigned_ticket_status_counts(client: TestClient, create_org) -> None:
    organization = create_org()
    invite_response = client.post(
        f"/v1/orgs/{organization['id']}/members/invite",
        json={"email": "assigned-agent@example.com", "role": "agent"},
    )
    assert invite_response.status_code == 201
    member_id = invite_response.json()["id"]

    with client.session_factory() as db:
        member = db.get(OrganizationMember, member_id)
        assert member is not None
        member.user_id = "assigned-agent"
        member.status = MemberStatus.ACTIVE.value
        db.commit()

    for status_name in ["new", "open", "pending", "awaiting_approval", "resolved"]:
        ticket_response = client.post(
            f"/v1/orgs/{organization['id']}/tickets",
            json={
                "customer_email": f"{status_name}@example.com",
                "customer_name": status_name,
                "subject": f"{status_name} ticket",
                "message_text": "Please help.",
            },
        )
        assert ticket_response.status_code == 201
        ticket_id = ticket_response.json()["id"]
        with client.session_factory() as db:
            from app.models.ticket import Ticket
            ticket = db.get(Ticket, ticket_id)
            assert ticket is not None
            ticket.assigned_to_user_id = "assigned-agent"
            ticket.status = status_name
            db.commit()

    response = client.get(f"/v1/orgs/{organization['id']}/members")

    assert response.status_code == 200
    agent = next(member for member in response.json() if member["user_id"] == "assigned-agent")
    assert agent["ticket_counts"]["new"] == 1
    assert agent["ticket_counts"]["open"] == 1
    assert agent["ticket_counts"]["pending"] == 1
    assert agent["ticket_counts"]["awaiting_approval"] == 1
    assert agent["ticket_counts"]["resolved"] == 1
    assert agent["ticket_counts"]["total"] == 5
