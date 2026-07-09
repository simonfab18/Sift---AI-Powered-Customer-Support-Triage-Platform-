from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.member import MemberRole, MemberStatus, OrganizationMember
from app.models.reply_suggestion import ReplySuggestion
from app.models.ticket_internal_note import TicketInternalNoteMention


def create_ticket(client, organization_id: str, subject: str = "Where is my order?") -> dict:
    response = client.post(
        f"/v1/orgs/{organization_id}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Customer",
            "subject": subject,
            "message_text": "I need help with this order.",
            "priority": "medium",
        },
    )
    assert response.status_code == 201
    return response.json()


def add_agent_member(client, organization_id: str) -> None:
    with client.session_factory() as db:
        db.add(
            OrganizationMember(
                organization_id=organization_id,
                user_id="user-agent",
                email="agent@example.com",
                role=MemberRole.AGENT.value,
                status=MemberStatus.ACTIVE.value,
            )
        )
        db.commit()


def test_saved_views_are_user_scoped_and_invalid_filters_are_dropped(client, create_org) -> None:
    organization = create_org()
    response = client.post(
        f"/v1/orgs/{organization['id']}/saved-views",
        json={"name": "Critical", "filters": {"priority": "critical", "status": "gone", "unknown": "x"}},
    )

    assert response.status_code == 201
    view = response.json()
    assert view["filters"] == {"priority": "critical"}

    add_agent_member(client, organization["id"])
    client.current_user.update({"id": "user-agent", "email": "agent@example.com"})
    scoped_response = client.get(f"/v1/orgs/{organization['id']}/saved-views")
    assert scoped_response.status_code == 200
    assert scoped_response.json() == []


def test_bulk_actions_return_per_item_results_and_require_destructive_confirmation(client, create_org) -> None:
    organization = create_org()
    ticket = create_ticket(client, organization["id"])

    blocked = client.post(
        f"/v1/orgs/{organization['id']}/tickets/bulk-actions",
        json={"ticket_ids": [ticket["id"]], "action": "resolve"},
    )
    assert blocked.status_code == 400

    response = client.post(
        f"/v1/orgs/{organization['id']}/tickets/bulk-actions",
        json={"ticket_ids": [ticket["id"], "missing-ticket"], "action": "resolve", "confirm": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["success"] is True
    assert body["results"][0]["ticket"]["status"] == "resolved"
    assert body["results"][1] == {"ticket_id": "missing-ticket", "success": False, "ticket": None, "error": "Ticket not found"}

    with client.session_factory() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "ticket.bulk_action_item_succeeded"))
        assert audit is not None


def test_response_template_insert_creates_editable_unapproved_suggestion(client, create_org) -> None:
    organization = create_org()
    ticket = create_ticket(client, organization["id"])
    created = client.post(
        f"/v1/orgs/{organization['id']}/response-templates",
        json={"name": "Shipping update", "body": "Thanks for reaching out. We are checking this now.", "category_tags": ["Order"]},
    )
    assert created.status_code == 201

    inserted = client.post(
        f"/v1/orgs/{organization['id']}/response-templates/{created.json()['id']}/insert",
        json={"ticket_id": ticket["id"]},
    )

    assert inserted.status_code == 200
    suggestion = inserted.json()["suggestion"]
    assert suggestion["status"] == "suggested"
    assert suggestion["created_by"] == "agent"
    assert suggestion["body"] == "Thanks for reaching out. We are checking this now."

    edited = client.patch(
        f"/v1/orgs/{organization['id']}/reply-suggestions/{suggestion['id']}",
        json={"edited_body": "Edited before approval."},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "edited"


def test_internal_notes_are_separate_from_suggestions_and_track_mentions_and_edits(client, create_org) -> None:
    organization = create_org()
    add_agent_member(client, organization["id"])
    ticket = create_ticket(client, organization["id"])

    note_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/internal-notes",
        json={"body": "Please review with @agent@example.com before replying."},
    )
    assert note_response.status_code == 201
    note = note_response.json()

    suggestions = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/reply-suggestions")
    assert note["body"] not in [item["body"] for item in suggestions.json()]

    mentions = client.get(f"/v1/orgs/{organization['id']}/internal-notes/{note['id']}/mentions")
    assert mentions.status_code == 200
    assert mentions.json()[0]["mentioned_user_id"] == "user-agent"

    edited = client.patch(
        f"/v1/orgs/{organization['id']}/internal-notes/{note['id']}",
        json={"body": "Updated note body."},
    )
    assert edited.status_code == 200
    assert edited.json()["version"] == 2

    edits = client.get(f"/v1/orgs/{organization['id']}/internal-notes/{note['id']}/edits")
    assert edits.status_code == 200
    assert edits.json()[0]["previous_body"] == "Please review with @agent@example.com before replying."

    with client.session_factory() as db:
        mention = db.scalar(select(TicketInternalNoteMention).where(TicketInternalNoteMention.note_id == note["id"]))
        assert mention is None


def test_collaboration_lock_blocks_silent_reply_overwrite(client, create_org) -> None:
    organization = create_org()
    add_agent_member(client, organization["id"])
    ticket = create_ticket(client, organization["id"])
    suggestion_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/reply-suggestions",
        json={"body": "Original reply"},
    )
    assert suggestion_response.status_code == 201
    suggestion = suggestion_response.json()

    lock_response = client.post(
        f"/v1/orgs/{organization['id']}/collaboration-locks",
        json={"ticket_id": ticket["id"], "resource_type": "reply_suggestion", "resource_id": suggestion["id"], "ttl_seconds": 120},
    )
    assert lock_response.status_code == 201

    client.current_user.update({"id": "user-agent", "email": "agent@example.com"})
    conflict = client.patch(
        f"/v1/orgs/{organization['id']}/reply-suggestions/{suggestion['id']}",
        json={"edited_body": "Agent overwrite"},
    )
    assert conflict.status_code == 409

    with client.session_factory() as db:
        stored = db.get(ReplySuggestion, suggestion["id"])
        assert stored.edited_body is None
