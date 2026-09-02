from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.encryption import encrypt_secret
from app.models.ai_triage_result import AITriageResult
from app.models.audit_log import AuditLog
from app.models.gmail_connection import GmailConnection
from app.models.gmail_draft import GmailDraft
from app.models.reply_approval import ReplyApproval
from app.models.ticket import Ticket


def test_triage_creates_pending_reply_approval(client: TestClient, create_org, monkeypatch) -> None:
    from app.models.ticket import TicketCategory, TicketPriority, TicketSentiment
    from app.schemas.ai import TriageOutput

    organization = create_org()
    ticket_response = client.post(
        f"/v1/orgs/{organization['id']}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": "Damaged item",
            "message_text": "The item arrived broken and I need a replacement.",
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
                draft_reply="Hi Casey, please send a photo. Best regards, Customer Support Team",
                confidence_score=91,
                reasoning="Clear customer intent and urgency signals.",
                requires_human_review=True,
            ),
            {"model": "gemini-test", "output_text": "{}"},
        )

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)

    response = client.post(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/triage")

    assert response.status_code == 201
    approvals_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/reply-approvals")
    approvals = approvals_response.json()
    assert len(approvals) == 1
    assert approvals[0]["status"] == "pending"
    assert approvals[0]["suggested_reply"].startswith("Hi Casey")


def test_update_reply_approval_saves_agent_edits(client: TestClient, create_org) -> None:
    organization, ticket, approval = _create_ticket_with_reply_approval(client, create_org)

    response = client.patch(
        f"/v1/orgs/{organization['id']}/tickets/{ticket.id}/reply-approvals/{approval.id}",
        json={"final_reply": "Edited reply for approval."},
    )

    assert response.status_code == 200
    assert response.json()["final_reply"] == "Edited reply for approval."


async def fake_refresh_gmail_access_token(refresh_token: str):
    assert refresh_token == "refresh-token"
    return "access-token", None


async def fake_create_gmail_draft(access_token: str, raw_message: str, thread_id: str | None = None):
    assert access_token == "access-token"
    assert raw_message
    assert thread_id == "gmail-thread-id"
    return {"id": "draft-123", "message": {"threadId": thread_id}}


def test_unapproved_suggestion_cannot_create_gmail_draft(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization, ticket, approval = _create_ticket_with_reply_approval(client, create_org, with_gmail=True)

    response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{approval.id}/create-gmail-draft")

    assert response.status_code == 400
    assert response.json()["detail"] == "Reply suggestion must be approved first"


def test_approved_suggestion_creates_gmail_draft_in_correct_thread(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization, ticket, approval = _create_ticket_with_reply_approval(client, create_org, with_gmail=True)
    monkeypatch.setattr(
        "app.services.reply_approval_service.refresh_gmail_access_token",
        fake_refresh_gmail_access_token,
    )
    monkeypatch.setattr("app.services.reply_approval_service.create_gmail_draft", fake_create_gmail_draft)

    approve_response = client.post(
        f"/v1/orgs/{organization['id']}/reply-suggestions/{approval.id}/approve",
        json={"final_reply": "Approved edited reply."},
    )
    draft_response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{approval.id}/create-gmail-draft")

    assert approve_response.status_code == 200
    with client.session_factory() as db:
        approval_audit = db.scalar(
            select(AuditLog).where(AuditLog.action == "reply_suggestion.approved")
        )
        assert approval_audit is not None
        assert approval_audit.resource_id == approval.id
    assert draft_response.status_code == 201
    body = draft_response.json()
    assert body["gmail_draft_id"] == "draft-123"
    assert body["approval"]["status"] == "draft_created"
    assert body["approval"]["final_reply"] == "Approved edited reply."
    assert body["draft"]["gmail_thread_id"] == "gmail-thread-id"

    draft_lookup = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket.id}/gmail-draft")
    assert draft_lookup.status_code == 200
    assert draft_lookup.json()["gmail_draft_id"] == "draft-123"


def test_duplicate_draft_creation_is_prevented(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization, ticket, approval = _create_ticket_with_reply_approval(
        client,
        create_org,
        with_gmail=True,
        approval_status="approved",
    )
    monkeypatch.setattr(
        "app.services.reply_approval_service.refresh_gmail_access_token",
        fake_refresh_gmail_access_token,
    )
    monkeypatch.setattr("app.services.reply_approval_service.create_gmail_draft", fake_create_gmail_draft)

    first_response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{approval.id}/create-gmail-draft")
    second_response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{approval.id}/create-gmail-draft")

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()["gmail_draft_id"] == first_response.json()["gmail_draft_id"]
    with client.session_factory() as db:
        assert len(list(db.scalars(select(GmailDraft)))) == 1
        draft_audit = db.scalar(select(AuditLog).where(AuditLog.action == "gmail.draft.created"))
        assert draft_audit is not None
        assert draft_audit.audit_metadata["gmail_draft_id"] == "draft-123"


def test_ticket_status_becomes_draft_created(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization, ticket, approval = _create_ticket_with_reply_approval(
        client,
        create_org,
        with_gmail=True,
        approval_status="approved",
    )
    monkeypatch.setattr(
        "app.services.reply_approval_service.refresh_gmail_access_token",
        fake_refresh_gmail_access_token,
    )
    monkeypatch.setattr("app.services.reply_approval_service.create_gmail_draft", fake_create_gmail_draft)

    response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{approval.id}/create-gmail-draft")

    assert response.status_code == 201
    ticket_response = client.get(f"/v1/orgs/{organization['id']}/tickets/{ticket.id}")
    assert ticket_response.json()["status"] == "draft_created"


def test_gmail_api_failure_keeps_ticket_recoverable(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization, ticket, approval = _create_ticket_with_reply_approval(
        client,
        create_org,
        with_gmail=True,
        approval_status="approved",
    )
    monkeypatch.setattr(
        "app.services.reply_approval_service.refresh_gmail_access_token",
        fake_refresh_gmail_access_token,
    )

    async def fake_failure(access_token: str, raw_message: str, thread_id: str | None = None):
        raise RuntimeError("gmail unavailable")

    monkeypatch.setattr("app.services.reply_approval_service.create_gmail_draft", fake_failure)

    response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{approval.id}/create-gmail-draft")

    assert response.status_code == 502
    with client.session_factory() as db:
        db_ticket = db.get(Ticket, ticket.id)
        db_approval = db.get(ReplyApproval, approval.id)
        assert db_ticket.status == "new"
        assert db_approval.status == "approved"
        assert db_approval.gmail_draft_id is None
        assert db.scalar(select(GmailDraft)) is None


def test_compat_approve_reply_creates_gmail_draft(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization, ticket, approval = _create_ticket_with_reply_approval(client, create_org, with_gmail=True)
    monkeypatch.setattr(
        "app.services.reply_approval_service.refresh_gmail_access_token",
        fake_refresh_gmail_access_token,
    )
    monkeypatch.setattr("app.services.reply_approval_service.create_gmail_draft", fake_create_gmail_draft)

    response = client.post(
        f"/v1/orgs/{organization['id']}/tickets/{ticket.id}/reply-approvals/{approval.id}/create-gmail-draft",
        json={"final_reply": "Approved edited reply."},
    )

    assert response.status_code == 201
    assert response.json()["gmail_draft_id"] == "draft-123"


def test_approve_reply_requires_gmail_linked_ticket(client: TestClient, create_org) -> None:
    organization, ticket, approval = _create_ticket_with_reply_approval(client, create_org, approval_status="approved")

    response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{approval.id}/create-gmail-draft")

    assert response.status_code == 400
    assert response.json()["detail"] == "Ticket is not linked to a Gmail connection"


def _create_ticket_with_reply_approval(
    client: TestClient,
    create_org,
    with_gmail: bool = False,
    approval_status: str = "pending",
):
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
        assert ticket is not None
        gmail_connection_id = None
        if with_gmail:
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
        approval = ReplyApproval(
            organization_id=organization["id"],
            ticket_id=ticket.id,
            ai_triage_result_id=triage.id,
            gmail_connection_id=gmail_connection_id,
            suggested_reply="Suggested reply.",
            final_reply="Suggested reply.",
            status=approval_status,
            approved_by_user_id="user-owner" if approval_status == "approved" else None,
        )
        db.add(approval)
        db.commit()
        db.refresh(ticket)
        db.refresh(approval)
        ticket_id = ticket.id
        approval_id = approval.id

    with client.session_factory() as db:
        return (
            organization,
            db.scalar(select(Ticket).where(Ticket.id == ticket_id)),
            db.scalar(select(ReplyApproval).where(ReplyApproval.id == approval_id)),
        )

