import asyncio

from sqlalchemy import select

from app.models.job_run import JobRun
from app.models.knowledge import KnowledgeUsageEvent
from app.models.member import MemberRole, MemberStatus, OrganizationMember
from app.models.ticket import TicketCategory, TicketPriority, TicketSentiment
from app.schemas.ai import TriageOutput
from app.services.ai_triage_service import PROMPT_VERSION, run_ticket_triage_job


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


def create_ticket(client, organization_id: str, subject: str, message: str) -> dict:
    response = client.post(
        f"/v1/orgs/{organization_id}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Customer",
            "subject": subject,
            "message_text": message,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_knowledge_sources_are_org_scoped_effective_and_archivable(client, create_org) -> None:
    org_a = create_org("Org A")
    org_b = create_org("Org B")

    created = client.post(
        f"/v1/orgs/{org_a['id']}/knowledge",
        json={
            "title": "Refund policy",
            "body": "Refunds require the original order number and damaged item photos.",
            "source_type": "policy",
        },
    )
    assert created.status_code == 201
    source = created.json()

    found = client.get(f"/v1/orgs/{org_a['id']}/knowledge/search", params={"q": "refund damaged photos"})
    assert found.status_code == 200
    assert found.json()["sources"][0]["id"] == source["id"]

    isolated = client.get(f"/v1/orgs/{org_b['id']}/knowledge/search", params={"q": "refund damaged photos"})
    assert isolated.status_code == 200
    assert isolated.json()["sources"] == []

    archived = client.post(f"/v1/orgs/{org_a['id']}/knowledge/{source['id']}/archive")
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    after_archive = client.get(f"/v1/orgs/{org_a['id']}/knowledge/search", params={"q": "refund damaged photos"})
    assert after_archive.json()["sources"] == []


def test_ai_triage_records_knowledge_sources_used(client, create_org, monkeypatch) -> None:
    organization = create_org()
    client.post(
        f"/v1/orgs/{organization['id']}/knowledge",
        json={
            "title": "Replacement policy",
            "body": "Damaged products qualify for replacement after photo review.",
            "source_type": "policy",
        },
    )
    ticket = create_ticket(
        client,
        organization["id"],
        "Damaged product",
        "The product arrived damaged. Can I get a replacement after I send photos?",
    )

    async def fake_classify(prompt: str):
        assert "Replacement policy" in prompt
        return (
            TriageOutput(
                category=TicketCategory.DAMAGED_ITEM,
                priority=TicketPriority.HIGH,
                sentiment=TicketSentiment.NEGATIVE,
                summary="Customer reports a damaged product.",
                suggested_action="Review replacement policy and request photos.",
                draft_reply="Hi, please send photos and we will review the replacement.",
                confidence_score=90,
                reasoning="Damaged product and replacement request match policy.",
                requires_human_review=True,
            ),
            {"model": "gemini-test", "output_text": "{}"},
        )

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)

    with client.session_factory() as db:
        job = db.scalar(select(JobRun).where(JobRun.job_type == "ai_triage"))
        result = asyncio.run(run_ticket_triage_job(db, job.id))
        usage = db.scalar(select(KnowledgeUsageEvent).where(KnowledgeUsageEvent.ai_triage_result_id == result.id))

    assert result.prompt_version == PROMPT_VERSION
    assert result.knowledge_sources[0]["title"] == "Replacement policy"
    assert usage is not None
    assert usage.ticket_id == ticket["id"]


def test_routing_rules_apply_in_order_and_sla_fields_are_filterable(client, create_org) -> None:
    organization = create_org()
    add_agent_member(client, organization["id"])

    settings = client.patch(
        f"/v1/orgs/{organization['id']}/workspace-settings",
        json={
            "business_timezone": "Asia/Singapore",
            "business_hours": {"0": {"start": "09:00", "end": "17:00"}},
            "first_review_target_minutes": 60,
            "resolution_target_minutes": 120,
        },
    )
    assert settings.status_code == 200

    rule = client.post(
        f"/v1/orgs/{organization['id']}/routing-rules",
        json={
            "name": "Refunds to agent",
            "priority_order": 1,
            "is_active": True,
            "conditions": {"keyword": "refund"},
            "actions": {"assign_user_id": "user-agent", "priority_floor": "high", "require_approval": True},
        },
    )
    assert rule.status_code == 201

    test_response = client.post(
        f"/v1/orgs/{organization['id']}/routing-rules/{rule.json()['id']}/test",
        json={"sample": {"subject": "Refund", "message_text": "Please refund this order."}},
    )
    assert test_response.status_code == 200
    assert test_response.json()["matched"] is True

    ticket = create_ticket(client, organization["id"], "Refund request", "Please refund this order.")
    assert ticket["priority"] == "high"
    assert ticket["status"] == "awaiting_approval"
    assert ticket["assigned_to_user_id"] == "user-agent"
    assert ticket["first_review_due_at"] is not None
    assert ticket["resolution_due_at"] is not None
    assert ticket["sla_status"] in {"on_track", "warning", "breached"}

    executions = client.get(f"/v1/orgs/{organization['id']}/routing-rules/tickets/{ticket['id']}/executions")
    assert executions.status_code == 200
    assert executions.json()[0]["matched"] is True
    assert executions.json()[0]["actions_applied"]["assigned_to_user_id"] == "user-agent"

    filtered = client.get(f"/v1/orgs/{organization['id']}/tickets", params={"sla_status": ticket["sla_status"]})
    assert filtered.status_code == 200
    assert filtered.json()[0]["id"] == ticket["id"]


