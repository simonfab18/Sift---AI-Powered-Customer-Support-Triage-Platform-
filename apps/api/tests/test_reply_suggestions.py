from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.encryption import encrypt_secret
from app.models.ai_triage_result import AITriageResult
from app.models.gmail_connection import GmailConnection
from app.models.reply_suggestion import ReplySuggestion
from app.models.ticket import Ticket
from app.schemas.ai import TriageOutput
from app.models.ticket import TicketCategory, TicketPriority, TicketSentiment


async def fake_refresh_gmail_access_token(refresh_token: str):
    assert refresh_token == "refresh-token"
    return "access-token", None


async def fake_create_gmail_draft(access_token: str, raw_message: str, thread_id: str | None = None):
    assert access_token == "access-token"
    assert raw_message
    assert thread_id == "gmail-thread-id"
    return {"id": "draft-123", "message": {"threadId": thread_id}}


def test_ai_triage_creates_reply_suggestion(client: TestClient, create_org, monkeypatch) -> None:
    organization = create_org()
    ticket_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": "Damaged item",
            "message_text": "The item arrived broken.",
        },
    )
    ticket = ticket_response.json()

    async def fake_classify(prompt: str):
        return (
            TriageOutput(
                category=TicketCategory.DAMAGED_ITEM,
                priority=TicketPriority.HIGH,
                sentiment=TicketSentiment.NEGATIVE,
                summary="Customer reports a damaged item.",
                suggested_action="Review replacement eligibility.",
                draft_reply="Hi Casey, please send a photo.",
                confidence_score=91,
                reasoning="Clear customer intent and urgency signals.",
                requires_human_review=True,
            ),
            {"model": "gemini-test", "output_text": "{}"},
        )

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)

    triage_response = client.post(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/triage")
    suggestions_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/reply-suggestions")

    assert triage_response.status_code == 201
    assert suggestions_response.status_code == 200
    suggestions = suggestions_response.json()
    assert len(suggestions) == 1
    assert suggestions[0]["body"] == "Hi Casey, please send a photo."
    assert suggestions[0]["status"] == "suggested"
    assert suggestions[0]["created_by"] == "ai"


def test_agent_can_edit_and_approve_reply_suggestion(client: TestClient, create_org) -> None:
    organization, ticket, suggestion = _create_reply_suggestion(client, create_org)

    edit_response = client.patch(
        f"/v1/orgs/{organization['id']}/reply-suggestions/{suggestion.id}",
        json={"edited_body": "Edited reply."},
    )
    approve_response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{suggestion.id}/approve")

    assert edit_response.status_code == 200
    assert edit_response.json()["status"] == "edited"
    assert edit_response.json()["edited_body"] == "Edited reply."
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"
    assert approve_response.json()["approved_by_user_id"] == "user-owner"

    tickets_response = client.get(f"/v1/orgs/{organization['id']}/tickets")
    listed_ticket = next(item for item in tickets_response.json() if item["id"] == ticket.id)
    assert listed_ticket["latest_reply_status"] == "approved"
    assert listed_ticket["latest_reply_gmail_draft_id"] is None

    ticket_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket.id}")
    assert ticket_response.json()["latest_reply_status"] == "approved"
    events_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket.id}/events")
    assert "ticket.reply_suggestion_approved" in [event["event_type"] for event in events_response.json()]


def test_user_outside_organization_cannot_approve_reply_suggestion(client: TestClient, create_org) -> None:
    organization, _ticket, suggestion = _create_reply_suggestion(client, create_org)
    client.current_user.update({"id": "outside-user", "email": "outside@example.com"})

    response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{suggestion.id}/approve")

    assert response.status_code == 403


def test_rejected_suggestion_cannot_create_draft(client: TestClient, create_org, monkeypatch) -> None:
    organization, _ticket, suggestion = _create_reply_suggestion(client, create_org, with_gmail=True)
    reject_response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{suggestion.id}/reject")
    draft_response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{suggestion.id}/create-gmail-draft")

    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
    assert draft_response.status_code == 400
    assert draft_response.json()["detail"] == "Rejected suggestion cannot create Gmail draft"


def test_approved_reply_suggestion_can_create_draft(client: TestClient, create_org, monkeypatch) -> None:
    organization, ticket, suggestion = _create_reply_suggestion(client, create_org, with_gmail=True)
    monkeypatch.setattr(
        "app.services.reply_suggestion_service.refresh_gmail_access_token",
        fake_refresh_gmail_access_token,
    )
    monkeypatch.setattr("app.services.reply_suggestion_service.create_gmail_draft", fake_create_gmail_draft)

    approve_response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{suggestion.id}/approve")
    draft_response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{suggestion.id}/create-gmail-draft")

    assert approve_response.status_code == 200
    assert draft_response.status_code == 201
    assert draft_response.json()["gmail_draft_id"] == "draft-123"
    assert draft_response.json()["approval"]["status"] == "draft_created"

    ticket_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket.id}")
    assert ticket_response.json()["status"] == "draft_created"


def _create_reply_suggestion(client: TestClient, create_org, with_gmail: bool = False):
    organization = create_org()
    ticket_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": "Question about my order",
            "message_text": "Can you help me with my order?",
        },
    )
    ticket_id = ticket_response.json()["id"]

    with client.session_factory() as db:
        ticket = db.scalar(select(Ticket).where(Ticket.id == ticket_id))
        gmail_connection_id = None
        if with_gmail:
            settings.encryption_key = "test-encryption-key"
            connection = GmailConnection(
                organization_id=organization["id"],
                connected_by_user_id="user-owner",
                gmail_email="support@example.com",
                google_account_id="google-account-id",
                encrypted_refresh_token=encrypt_secret("refresh-token"),
                scopes="https://www.googleapis.com/auth/gmail.compose",
                status="active",
            )
            db.add(connection)
            db.flush()
            gmail_connection_id = connection.id
            ticket.gmail_connection_id = connection.id
            ticket.gmail_thread_id = "gmail-thread-id"
        triage = AITriageResult(
            organization_id=organization["id"],
            ticket_id=ticket.id,
            model_name="gemini-test",
            raw_input={},
            raw_output={},
            validated_output={},
            category="product_question",
            priority="low",
            sentiment="neutral",
            summary="Customer has a question.",
            suggested_action="Answer the question.",
            draft_reply="Suggested reply.",
            requires_human_review=False,
        )
        db.add(triage)
        db.flush()
        suggestion = ReplySuggestion(
            organization_id=organization["id"],
            ticket_id=ticket.id,
            ai_triage_result_id=triage.id,
            gmail_connection_id=gmail_connection_id,
            body="Suggested reply.",
            status="suggested",
            created_by="ai",
        )
        db.add(suggestion)
        db.commit()
        db.refresh(ticket)
        db.refresh(suggestion)
        ticket_id = ticket.id
        suggestion_id = suggestion.id

    with client.session_factory() as db:
        return (
            organization,
            db.scalar(select(Ticket).where(Ticket.id == ticket_id)),
            db.scalar(select(ReplySuggestion).where(ReplySuggestion.id == suggestion_id)),
        )
