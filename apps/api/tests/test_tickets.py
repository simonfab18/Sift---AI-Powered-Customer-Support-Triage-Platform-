from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.ai_triage_result import AITriageResult
from app.models.member import MemberRole, MemberStatus, OrganizationMember
from app.models.ticket import Ticket


def ticket_payload(**overrides):
    payload = {
        "customer_email": "customer@example.com",
        "customer_name": "Casey Customer",
        "subject": "Where is my order?",
        "message_text": "I ordered last week and have not received tracking.",
        "category": "order_status",
        "priority": "medium",
        "sentiment": "neutral",
    }
    payload.update(overrides)
    return payload


def create_ticket(client: TestClient, organization_id: str, **overrides) -> dict:
    response = client.post(
        f"/v1/orgs/{organization_id}/tickets",
        json=ticket_payload(**overrides),
    )
    assert response.status_code == 201
    return response.json()


def test_create_ticket_creates_customer_and_event(client: TestClient, create_org) -> None:
    organization = create_org()

    ticket = create_ticket(client, organization["id"])
    events_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/events")

    assert ticket["customer"]["email"] == "customer@example.com"
    assert ticket["status"] == "new"
    assert events_response.status_code == 200
    assert [event["event_type"] for event in events_response.json()] == ["ticket.created"]


def test_list_tickets_is_scoped_to_organization(client: TestClient, create_org) -> None:
    first_org = create_org("First Org")
    second_org = create_org("Second Org")
    first_ticket = create_ticket(client, first_org["id"], subject="First org ticket")
    create_ticket(client, second_org["id"], subject="Second org ticket")

    response = client.get(f"/v1/orgs/{first_org['id']}/tickets")

    assert response.status_code == 200
    tickets = response.json()
    assert len(tickets) == 1
    assert tickets[0]["id"] == first_ticket["id"]
    assert tickets[0]["subject"] == "First org ticket"


def test_user_cannot_read_ticket_from_org_they_do_not_belong_to(client: TestClient, create_org) -> None:
    organization = create_org()
    ticket = create_ticket(client, organization["id"])
    client.current_user.update({"id": "outside-user", "email": "outside@example.com"})

    response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}")

    assert response.status_code == 403


def test_update_ticket_writes_event(client: TestClient, create_org) -> None:
    organization = create_org()
    ticket = create_ticket(client, organization["id"])

    response = client.patch(
        f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}",
        json={"priority": "high", "status": "open"},
    )
    events_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/events")

    assert response.status_code == 200
    assert response.json()["priority"] == "high"
    assert response.json()["status"] == "open"
    assert [event["event_type"] for event in events_response.json()] == [
        "ticket.created",
        "ticket.updated",
    ]


def test_assign_ticket_requires_active_org_member(client: TestClient, create_org) -> None:
    organization = create_org()
    ticket = create_ticket(client, organization["id"])

    bad_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/assign",
        json={"assigned_to_user_id": "missing-agent"},
    )

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

    good_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/assign",
        json={"assigned_to_user_id": "agent-user"},
    )

    assert bad_response.status_code == 400
    assert good_response.status_code == 200
    assert good_response.json()["assigned_to_user_id"] == "agent-user"



def test_agent_cannot_assign_ticket_to_teammate(client: TestClient, create_org) -> None:
    organization = create_org()
    ticket = create_ticket(client, organization["id"])

    with client.session_factory() as db:
        owner = db.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization["id"],
                OrganizationMember.user_id == "user-owner",
            )
        )
        owner.role = MemberRole.AGENT.value
        db.add(
            OrganizationMember(
                organization_id=organization["id"],
                user_id="other-agent",
                email="other-agent@example.com",
                role=MemberRole.AGENT.value,
                status=MemberStatus.ACTIVE.value,
            )
        )
        db.commit()

    response = client.post(
        f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/assign",
        json={"assigned_to_user_id": "other-agent"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role"

def test_mark_spam_and_resolve_update_status(client: TestClient, create_org) -> None:
    organization = create_org()
    spam_ticket = create_ticket(client, organization["id"], subject="Buy followers now")
    resolve_ticket = create_ticket(client, organization["id"], subject="Normal ticket")

    spam_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets/{spam_ticket['id']}/mark-spam"
    )
    resolve_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets/{resolve_ticket['id']}/resolve"
    )

    assert spam_response.status_code == 200
    assert spam_response.json()["status"] == "spam"
    assert spam_response.json()["category"] == "spam"
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"


def test_ticket_filters_by_status_and_priority(client: TestClient, create_org) -> None:
    organization = create_org()
    high_ticket = create_ticket(client, organization["id"], subject="Urgent", priority="high")
    create_ticket(client, organization["id"], subject="Low", priority="low")

    response = client.get(f"/v1/orgs/{organization['id']}/tickets?priority=high")

    assert response.status_code == 200
    assert [ticket["id"] for ticket in response.json()] == [high_ticket["id"]]


def test_dashboard_metrics_count_only_organization_tickets(client: TestClient, create_org) -> None:
    first_org = create_org("Metrics First Org")
    second_org = create_org("Metrics Second Org")
    create_ticket(client, first_org["id"], priority="critical")
    resolved_ticket = create_ticket(client, first_org["id"], priority="high")
    spam_ticket = create_ticket(client, first_org["id"], priority="low")
    create_ticket(client, second_org["id"], priority="critical")

    client.post(f"/v1/orgs/{first_org['id']}/tickets/{resolved_ticket['id']}/resolve")
    client.post(f"/v1/orgs/{first_org['id']}/tickets/{spam_ticket['id']}/mark-spam")

    with client.session_factory() as db:
        db.add(
            AITriageResult(
                organization_id=first_org["id"],
                ticket_id=resolved_ticket["id"],
                model_name="gemini-test",
                category="order_status",
                priority="high",
                sentiment="neutral",
                summary="Order update",
                suggested_action="Review tracking",
                draft_reply="We will check this for you.",
                confidence_score=87,
                reasoning="Test confidence",
                requires_human_review=False,
            )
        )
        db.commit()

    response = client.get(f"/v1/orgs/{first_org['id']}/metrics/overview")

    assert response.status_code == 200
    body = response.json()
    assert body["total_tickets"] == 3
    assert body["active_tickets"] == 1
    assert body["resolved_tickets"] == 1
    assert body["spam_tickets"] == 1
    assert body["critical_tickets"] == 1
    assert body["high_priority_tickets"] == 0
    assert body["average_confidence_score"] == 87
    assert body["by_status"] == {"new": 1, "resolved": 1, "spam": 1}
    assert body["by_priority"] == {"critical": 1, "high": 1, "low": 1}
    assert body["by_active_priority"] == {"critical": 1}


def test_filters_return_expected_tickets(client: TestClient, create_org) -> None:
    organization = create_org()
    open_high = create_ticket(client, organization["id"], subject="Open high", priority="high")
    create_ticket(client, organization["id"], subject="Open low", priority="low")
    resolved_high = create_ticket(client, organization["id"], subject="Resolved high", priority="high")
    client.post(f"/v1/orgs/{organization['id']}/tickets/{resolved_high['id']}/resolve")

    active_high_response = client.get(f"/v1/orgs/{organization['id']}/tickets?priority=high")
    resolved_response = client.get(f"/v1/orgs/{organization['id']}/tickets?status=resolved")
    all_high_response = client.get(f"/v1/orgs/{organization['id']}/tickets?status=all&priority=high")

    assert [ticket["id"] for ticket in active_high_response.json()] == [open_high["id"]]
    assert [ticket["id"] for ticket in resolved_response.json()] == [resolved_high["id"]]
    assert {ticket["id"] for ticket in all_high_response.json()} == {open_high["id"], resolved_high["id"]}


def test_critical_and_high_tickets_sort_correctly(client: TestClient, create_org) -> None:
    organization = create_org()
    older_critical = create_ticket(client, organization["id"], subject="Older critical", priority="critical")
    newer_high = create_ticket(client, organization["id"], subject="Newer high", priority="high")
    newer_critical = create_ticket(client, organization["id"], subject="Newer critical", priority="critical")
    older_medium = create_ticket(client, organization["id"], subject="Older medium", priority="medium")

    with client.session_factory() as db:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        timestamps = {
            older_critical["id"]: base,
            newer_high["id"]: base + timedelta(hours=3),
            newer_critical["id"]: base + timedelta(hours=4),
            older_medium["id"]: base + timedelta(hours=1),
        }
        for ticket_id, received_at in timestamps.items():
            ticket = db.scalar(select(Ticket).where(Ticket.id == ticket_id))
            ticket.received_at = received_at
        db.commit()

    response = client.get(f"/v1/orgs/{organization['id']}/tickets")

    assert response.status_code == 200
    assert [ticket["id"] for ticket in response.json()] == [
        newer_critical["id"],
        older_critical["id"],
        newer_high["id"],
        older_medium["id"],
    ]


def test_resolved_and_spam_tickets_do_not_appear_in_default_active_queue(client: TestClient, create_org) -> None:
    organization = create_org()
    active_ticket = create_ticket(client, organization["id"], subject="Active")
    resolved_ticket = create_ticket(client, organization["id"], subject="Resolved")
    spam_ticket = create_ticket(client, organization["id"], subject="Spam")
    client.post(f"/v1/orgs/{organization['id']}/tickets/{resolved_ticket['id']}/resolve")
    client.post(f"/v1/orgs/{organization['id']}/tickets/{spam_ticket['id']}/mark-spam")

    default_response = client.get(f"/v1/orgs/{organization['id']}/tickets")
    all_response = client.get(f"/v1/orgs/{organization['id']}/tickets?status=all")

    assert [ticket["id"] for ticket in default_response.json()] == [active_ticket["id"]]
    assert {ticket["id"] for ticket in all_response.json()} == {
        active_ticket["id"],
        resolved_ticket["id"],
        spam_ticket["id"],
    }


def test_all_status_with_paused_sla_includes_resolved_and_spam_tickets(client: TestClient, create_org) -> None:
    organization = create_org()
    resolved_ticket = create_ticket(client, organization["id"], subject="Resolved paused")
    spam_ticket = create_ticket(client, organization["id"], subject="Spam paused")
    active_ticket = create_ticket(client, organization["id"], subject="Active")
    client.post(f"/v1/orgs/{organization['id']}/tickets/{resolved_ticket['id']}/resolve")
    client.post(f"/v1/orgs/{organization['id']}/tickets/{spam_ticket['id']}/mark-spam")

    paused_response = client.get(f"/v1/orgs/{organization['id']}/tickets?status=all&sla_status=paused")

    paused_ticket_ids = {ticket["id"] for ticket in paused_response.json()}
    assert paused_response.status_code == 200
    assert paused_ticket_ids == {resolved_ticket["id"], spam_ticket["id"]}
    assert active_ticket["id"] not in paused_ticket_ids
