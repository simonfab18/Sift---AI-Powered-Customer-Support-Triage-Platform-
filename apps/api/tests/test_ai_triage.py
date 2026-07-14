import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.integrations.gemini.client import GeminiQuotaExceededError
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketSentiment, TicketTriageStatus
from app.integrations.gemini.prompts import build_triage_prompt
from app.schemas.ai import TriageOutput


@pytest.fixture
def ticket(client: TestClient, create_org) -> tuple[dict, dict]:
    organization = create_org()
    response = client.post(
        f"/v1/orgs/{organization['id']}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": "I need a refund for a broken item",
            "message_text": "The item arrived broken and I want a refund please.",
        },
    )
    assert response.status_code == 201
    return organization, response.json()


@pytest.mark.asyncio
async def test_triage_ticket_stores_result_updates_ticket_and_writes_event(
    client: TestClient,
    ticket: tuple[dict, dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization, created_ticket = ticket

    async def fake_classify(prompt: str):
        assert "I need a refund" in prompt
        return (
            TriageOutput(
                category=TicketCategory.REFUND,
                priority=TicketPriority.HIGH,
                sentiment=TicketSentiment.NEGATIVE,
                summary="Customer received a broken item and requests a refund.",
                suggested_action="Review order details and approve a refund if eligible.",
                draft_reply="Hi Casey, thanks for contacting us. Best regards, Customer Support Team",
                confidence_score=91,
                reasoning="Clear customer intent and urgency signals.",
                requires_human_review=False,
            ),
            {"model": "gemini-test", "output_text": "{}"},
        )

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)

    response = client.post(f"/v1/orgs/{organization['id']}/tickets/{created_ticket['id']}/triage")

    assert response.status_code == 201
    result = response.json()
    assert result["category"] == "refund"
    assert result["priority"] == "high"
    assert result["sentiment"] == "negative"
    assert result["requires_human_review"] is True

    ticket_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{created_ticket['id']}")
    updated_ticket = ticket_response.json()
    assert updated_ticket["category"] == "refund"
    assert updated_ticket["priority"] == "high"
    assert updated_ticket["sentiment"] == "negative"

    events_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{created_ticket['id']}/events")
    event_types = [event["event_type"] for event in events_response.json()]
    assert "ticket.ai_triaged" in event_types


def test_list_ticket_triage_results(client: TestClient, create_org, monkeypatch: pytest.MonkeyPatch) -> None:
    organization = create_org()
    ticket_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets",
        json={
            "customer_email": "shopper@example.com",
            "customer_name": "Casey Customer",
            "subject": "What colors does this shirt come in?",
            "message_text": "Can you tell me which colors are available for this shirt?",
        },
    )
    assert ticket_response.status_code == 201
    created_ticket = ticket_response.json()

    async def fake_classify(prompt: str):
        return (
            TriageOutput(
                category=TicketCategory.PRODUCT_QUESTION,
                priority=TicketPriority.LOW,
                sentiment=TicketSentiment.NEUTRAL,
                summary="Customer asks a product question.",
                suggested_action="Answer the product question.",
                draft_reply="Hi Casey, here is the answer. Best regards, Customer Support Team",
                confidence_score=91,
                reasoning="Clear customer intent and urgency signals.",
                requires_human_review=False,
            ),
            {"model": "gemini-test", "output_text": "{}"},
        )

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)

    create_response = client.post(f"/v1/orgs/{organization['id']}/tickets/{created_ticket['id']}/triage")
    assert create_response.status_code == 201

    list_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{created_ticket['id']}/triage")

    assert list_response.status_code == 200
    results = list_response.json()
    assert len(results) == 1
    assert results[0]["summary"] == "Customer asks a product question."
    assert results[0]["requires_human_review"] is False


def test_triage_requires_organization_membership(
    client: TestClient,
    ticket: tuple[dict, dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization, created_ticket = ticket
    client.current_user["id"] = "not-a-member"

    async def fake_classify(prompt: str):
        raise AssertionError("Gemini should not be called without membership")

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)

    response = client.post(f"/v1/orgs/{organization['id']}/tickets/{created_ticket['id']}/triage")

    assert response.status_code == 403


def test_manual_triage_quota_failure_returns_retryable_api_error(
    client: TestClient,
    ticket: tuple[dict, dict],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization, created_ticket = ticket

    async def fake_classify(prompt: str):
        raise GeminiQuotaExceededError("Gemini quota exceeded", retry_after_seconds=61)

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)

    response = client.post(f"/v1/orgs/{organization['id']}/tickets/{created_ticket['id']}/triage")

    assert response.status_code == 429
    assert response.json()["detail"] == "Gemini quota exceeded"
    assert response.headers["retry-after"] == "61"

    with client.session_factory() as db:
        stored_ticket = db.get(Ticket, created_ticket["id"])

    assert stored_ticket.triage_status == TicketTriageStatus.FAILED.value
    assert stored_ticket.triage_error_message == "Gemini quota exceeded"
    assert stored_ticket.active_triage_job_id is None

def test_triage_output_requires_confidence_and_reasoning() -> None:
    with pytest.raises(ValidationError):
        TriageOutput.model_validate(
            {
                "category": "refund",
                "priority": "high",
                "sentiment": "negative",
                "summary": "Customer needs help.",
                "suggested_action": "Review the case.",
                "draft_reply": "Thanks for contacting us.",
                "requires_human_review": True,
            }
        )


def test_triage_output_rejects_invalid_confidence_score() -> None:
    with pytest.raises(ValidationError):
        TriageOutput.model_validate(
            {
                "category": "refund",
                "priority": "high",
                "sentiment": "negative",
                "summary": "Customer needs help.",
                "suggested_action": "Review the case.",
                "draft_reply": "Thanks for contacting us.",
                "confidence_score": 101,
                "reasoning": "Clear refund request.",
                "requires_human_review": True,
            }
        )

def test_triage_prompt_discourages_other_and_medium_defaults() -> None:
    prompt = build_triage_prompt(
        customer_name=None,
        customer_email="customer@example.com",
        subject="I was charged twice",
        message="Please refund the duplicate charge on my order.",
    )

    assert "Do not use category other when any named category is a reasonable fit" in prompt
    assert "Avoid defaulting to medium" in prompt
    assert "charged twice" in prompt
    assert "category refund, priority high" in prompt


def test_triage_prompt_contains_common_gmail_workflow_examples() -> None:
    prompt = build_triage_prompt(
        customer_name="Casey",
        customer_email="casey@example.com",
        subject="Package broken",
        message="The item arrived broken and I need a replacement.",
    )

    assert "category order_status" in prompt
    assert "category damaged_item" in prompt
    assert "category account_access" in prompt
    assert "Where is my order?" in prompt
    assert "The item arrived broken" in prompt