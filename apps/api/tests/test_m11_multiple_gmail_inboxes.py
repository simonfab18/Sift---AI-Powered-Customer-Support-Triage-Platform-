from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.gmail_connection import GmailConnection
from app.models.mail_import_rule import MailImportRule
from app.models.member import MemberRole, MemberStatus, OrganizationMember
from app.services.email_import_service import import_gmail_message_if_new
from app.integrations.gmail.mapper import NormalizedGmailMessage
from app.api.deps import AuthenticatedUser


def _create_connection(client: TestClient, organization_id: str, email: str, display_name: str | None = None) -> tuple[str, str]:
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization_id,
            connected_by_user_id="user-owner",
            gmail_email=email,
            display_name=display_name,
            google_account_id=f"google-{email}",
            encrypted_refresh_token="encrypted-token",
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
        )
        db.add(connection)
        db.flush()
        rule = MailImportRule(organization_id=organization_id, gmail_connection_id=connection.id)
        db.add(rule)
        db.commit()
        return connection.id, rule.id


def test_owner_can_label_multiple_gmail_inboxes_and_update_connection_rule(client: TestClient, create_org) -> None:
    organization = create_org()
    support_id, support_rule_id = _create_connection(client, organization["id"], "support@example.com", "Support")
    returns_id, returns_rule_id = _create_connection(client, organization["id"], "returns@example.com", "Returns")

    label_response = client.patch(
        f"/v1/orgs/{organization['id']}/gmail/connections/{returns_id}",
        json={"display_name": "Returns desk"},
    )
    rule_response = client.patch(
        f"/v1/orgs/{organization['id']}/gmail/import-rules/{returns_rule_id}",
        json={"support_label_id": "Label_returns", "import_unread_only": False, "routing_direction": "specialist_queue"},
    )
    list_response = client.get(f"/v1/orgs/{organization['id']}/gmail/connections")
    rules_response = client.get(f"/v1/orgs/{organization['id']}/gmail/import-rules")

    assert label_response.status_code == 200
    assert label_response.json()["display_name"] == "Returns desk"
    assert rule_response.status_code == 200
    assert rule_response.json()["routing_direction"] == "specialist_queue"
    assert {item["id"] for item in list_response.json()} == {support_id, returns_id}
    rules_by_id = {item["id"]: item for item in rules_response.json()}
    assert rules_by_id[support_rule_id]["routing_direction"] == "shared_queue"
    assert rules_by_id[returns_rule_id]["support_label_id"] == "Label_returns"

    with client.session_factory() as db:
        actions = {row.action for row in db.scalars(select(AuditLog))}
        assert "gmail.connection.updated" in actions
        assert "gmail.import_rule.updated" in actions


def test_agent_cannot_update_gmail_inbox_label_or_import_rule(client: TestClient, create_org) -> None:
    organization = create_org()
    connection_id, rule_id = _create_connection(client, organization["id"], "support@example.com", "Support")
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
    label_response = client.patch(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}",
        json={"display_name": "Agent edit"},
    )
    rule_response = client.patch(
        f"/v1/orgs/{organization['id']}/gmail/import-rules/{rule_id}",
        json={"routing_direction": "priority_queue"},
    )

    assert label_response.status_code == 403
    assert rule_response.status_code == 403



def test_saved_view_preserves_source_inbox_filter(client: TestClient, create_org) -> None:
    organization = create_org()
    returns_id, _ = _create_connection(client, organization["id"], "returns@example.com", "Returns")

    response = client.post(
        f"/v1/orgs/{organization['id']}/saved-views",
        json={
            "name": "Returns breached",
            "filters": {
                "gmail_connection_id": returns_id,
                "sla_status": "breached",
                "priority": "high",
                "unknown": "drop-me",
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["filters"] == {
        "gmail_connection_id": returns_id,
        "sla_status": "breached",
        "priority": "high",
    }


def test_ticket_queue_exposes_and_filters_source_inbox(client: TestClient, create_org) -> None:
    organization = create_org()
    support_id, _ = _create_connection(client, organization["id"], "support@example.com", "Support")
    returns_id, _ = _create_connection(client, organization["id"], "returns@example.com", "Returns")
    actor = AuthenticatedUser(id="user-owner", email="owner@example.com")

    with client.session_factory() as db:
        import_gmail_message_if_new(
            db,
            organization["id"],
            support_id,
            actor,
            NormalizedGmailMessage(
                gmail_message_id="gmail-support-1",
                gmail_thread_id="thread-support",
                subject="Support question",
                customer_email="casey@example.com",
                customer_name="Casey",
                message_text="Need support",
                message_html=None,
                received_at=datetime.now(UTC),
                attachments=[],
            ),
        )
        import_gmail_message_if_new(
            db,
            organization["id"],
            returns_id,
            actor,
            NormalizedGmailMessage(
                gmail_message_id="gmail-returns-1",
                gmail_thread_id="thread-returns",
                subject="Return question",
                customer_email="riley@example.com",
                customer_name="Riley",
                message_text="Need return",
                message_html=None,
                received_at=datetime.now(UTC),
                attachments=[],
            ),
        )
        db.commit()

    all_response = client.get(f"/v1/orgs/{organization['id']}/tickets?status=all")
    filtered_response = client.get(f"/v1/orgs/{organization['id']}/tickets?status=all&gmail_connection_id={returns_id}")

    assert all_response.status_code == 200
    assert {ticket["gmail_connection_display_name"] for ticket in all_response.json()} == {"Support", "Returns"}
    assert filtered_response.status_code == 200
    assert len(filtered_response.json()) == 1
    assert filtered_response.json()[0]["subject"] == "Return question"
    assert filtered_response.json()[0]["gmail_connection_email"] == "returns@example.com"
