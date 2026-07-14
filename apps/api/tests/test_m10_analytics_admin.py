from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.ai_triage_result import AITriageResult
from app.models.gmail_sync_event import GmailSyncEvent
from app.models.job_run import JobRun
from app.models.member import MemberRole, OrganizationMember
from app.models.reply_suggestion import ReplySuggestion
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.services.audit_log_service import create_audit_log


def _create_ticket(client: TestClient, organization_id: str, subject: str = "Damaged item") -> dict:
    response = client.post(
        f"/v1/orgs/{organization_id}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": subject,
            "message_text": "The product arrived damaged and I need a replacement.",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_m10_admin_analytics_surfaces_support_ai_and_gmail_metrics(client: TestClient, create_org) -> None:
    organization = create_org()
    ticket = _create_ticket(client, organization["id"])
    now = datetime.now(UTC)

    with client.session_factory() as db:
        stored_ticket = db.get(Ticket, ticket["id"])
        stored_ticket.category = "damaged_item"
        stored_ticket.priority = "high"
        stored_ticket.status = "resolved"
        stored_ticket.triage_status = "triaged"
        stored_ticket.assigned_to_user_id = "user-owner"
        stored_ticket.created_at = now - timedelta(hours=3)
        stored_ticket.updated_at = now - timedelta(minutes=20)
        stored_ticket.resolution_due_at = now + timedelta(hours=2)
        db.add_all(
            [
                TicketEvent(
                    organization_id=organization["id"],
                    ticket_id=ticket["id"],
                    actor_user_id="user-owner",
                    event_type="ticket.assigned",
                    created_at=now - timedelta(hours=2, minutes=45),
                    event_metadata={},
                ),
                TicketEvent(
                    organization_id=organization["id"],
                    ticket_id=ticket["id"],
                    actor_user_id="user-owner",
                    event_type="ticket.resolved",
                    created_at=now - timedelta(minutes=20),
                    event_metadata={"previous_status": "draft_created"},
                ),
                TicketEvent(
                    organization_id=organization["id"],
                    ticket_id=ticket["id"],
                    actor_user_id="user-owner",
                    event_type="ticket.updated",
                    created_at=now - timedelta(hours=2),
                    event_metadata={"changes": {"priority": {"from": "medium", "to": "high"}}},
                ),
                AITriageResult(
                    organization_id=organization["id"],
                    ticket_id=ticket["id"],
                    model_name="gemini-test",
                    latency_ms=250,
                    category="damaged_item",
                    priority="high",
                    sentiment="negative",
                    summary="Damaged item",
                    suggested_action="Ask for photo",
                    draft_reply="Please send a photo.",
                    confidence_score=88,
                    reasoning="matched policy",
                    requires_human_review=True,
                ),
                ReplySuggestion(
                    organization_id=organization["id"],
                    ticket_id=ticket["id"],
                    ai_triage_result_id=None,
                    body="Please send a photo.",
                    edited_body="Please send a clear photo.",
                    status="approved",
                    reply_version=2,
                    approved_reply_version=2,
                    approved_by_user_id="user-owner",
                    approved_at=now - timedelta(minutes=50),
                    created_at=now - timedelta(hours=1),
                ),
                JobRun(
                    organization_id=organization["id"],
                    job_type="ai_triage",
                    queue_name="ai_triage",
                    status="succeeded",
                    duration_ms=300,
                ),
                GmailSyncEvent(
                    organization_id=organization["id"],
                    trigger_type="pubsub_notification",
                    status="succeeded",
                    messages_skipped=2,
                    duration_ms=1200,
                    started_at=now - timedelta(minutes=5),
                    completed_at=now - timedelta(minutes=4),
                ),
                GmailSyncEvent(
                    organization_id=organization["id"],
                    trigger_type="watch_renewal",
                    status="succeeded",
                    duration_ms=200,
                ),
                GmailSyncEvent(
                    organization_id=organization["id"],
                    trigger_type="reconciliation",
                    status="succeeded",
                    messages_skipped=1,
                ),
            ]
        )
        db.commit()

    response = client.get(f"/v1/orgs/{organization['id']}/metrics/admin")

    assert response.status_code == 200
    body = response.json()
    assert body["support"]["ticket_volume"] == 1
    assert body["support"]["by_category"] == {"damaged_item": 1}
    assert body["support"]["agent_workload"][0]["user_id"] == "user-owner"
    assert body["support"]["sla_attainment_rate"] == 1.0
    assert body["ai_quality"]["triage_completion_rate"] == 1.0
    assert body["ai_quality"]["confidence_distribution"]["71-90"] == 1
    assert body["ai_quality"]["agent_priority_corrections"] == 1
    assert body["ai_quality"]["reply_approval_rate"] == 1.0
    assert body["gmail_sync"]["notifications_received"] == 1
    assert body["gmail_sync"]["duplicate_skip_count"] == 3
    assert body["gmail_sync"]["watch_renewal_success"] == 1


def test_m10_admin_analytics_requires_owner_or_admin(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        member = db.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization["id"]))
        member.role = MemberRole.AGENT.value
        db.commit()

    response = client.get(f"/v1/orgs/{organization['id']}/metrics/admin")

    assert response.status_code == 403


def test_audit_logs_support_filters_search_limit_and_redaction(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        create_audit_log(
            db,
            organization_id=organization["id"],
            actor_user_id="user-owner",
            action="gmail.connected",
            resource_type="gmail_connection",
            resource_id="gmail-1",
            metadata={"refresh_token": "secret", "safe": "visible"},
        )
        create_audit_log(
            db,
            organization_id=organization["id"],
            actor_user_id="user-owner",
            action="ticket.resolved",
            resource_type="ticket",
            resource_id="ticket-1",
            metadata={"safe": "ticket"},
        )
        db.commit()

    filtered = client.get(f"/v1/orgs/{organization['id']}/audit-logs?action=gmail.connected&search=gmail&limit=1")
    ticket_search = client.get(f"/v1/orgs/{organization['id']}/audit-logs?resource_type=ticket&search=ticket-1")

    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["action"] == "gmail.connected"
    assert filtered.json()[0]["metadata"]["refresh_token"] == "[REDACTED]"
    assert ticket_search.status_code == 200
    assert ticket_search.json()[0]["resource_type"] == "ticket"
