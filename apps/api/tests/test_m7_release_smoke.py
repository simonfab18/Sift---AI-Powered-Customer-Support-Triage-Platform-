import asyncio
import base64
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.encryption import encrypt_secret
from app.models.audit_log import AuditLog
from app.models.gmail_connection import GmailConnection
from app.models.job_run import JobRun
from app.models.mail_import_rule import MailImportRule
from app.models.reply_approval import ReplyApproval
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketSentiment
from app.schemas.ai import TriageOutput
from app.services.ai_triage_service import run_ticket_triage_job
from app.services.gmail_history_sync_service import list_stale_connections, run_gmail_history_sync


def _encoded_body(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


def _gmail_message(message_id: str) -> dict:
    return {
        "id": message_id,
        "threadId": "gmail-thread-id",
        "labelIds": ["INBOX", "UNREAD"],
        "internalDate": "1704067200000",
        "snippet": "snippet text",
        "payload": {
            "headers": [
                {"name": "From", "value": "Casey Customer <casey@example.com>"},
                {"name": "Subject", "value": "Pilot support question"},
                {"name": "Date", "value": "Mon, 01 Jan 2024 12:00:00 +0000"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _encoded_body("Can you help me with my order?")}},
            ],
        },
    }


def _create_history_connection(client: TestClient, organization_id: str) -> str:
    with client.session_factory() as db:
        connection = GmailConnection(
            organization_id=organization_id,
            connected_by_user_id="user-owner",
            gmail_email="support@example.com",
            google_account_id="google-account-id",
            encrypted_refresh_token=encrypt_secret("refresh-token"),
            scopes="openid email https://www.googleapis.com/auth/gmail.modify",
            status="active",
            watch_status="active",
            sync_status="active",
            gmail_history_id="100",
        )
        db.add(connection)
        db.flush()
        db.add(MailImportRule(organization_id=organization_id, gmail_connection_id=connection.id))
        db.commit()
        return connection.id


def test_mocked_release_smoke_gmail_to_draft_and_reconnect(
    client: TestClient,
    create_org,
    monkeypatch,
    stub_auto_triage_dispatch,
) -> None:
    organization = create_org()
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    monkeypatch.setattr(settings, "google_pubsub_topic", "projects/test/topics/gmail")
    connection_id = _create_history_connection(client, organization["id"])

    async def fake_refresh(refresh_token: str):
        return "access-token", datetime.now(UTC) + timedelta(hours=1)

    async def fake_history(access_token: str, start_history_id: str, page_token: str | None = None):
        return {"historyId": "101", "history": [{"messagesAdded": [{"message": {"id": "gmail-1"}}]}]}

    async def fake_get_message(access_token: str, message_id: str):
        return _gmail_message(message_id)

    async def fake_classify(prompt: str):
        return (
            TriageOutput(
                category=TicketCategory.PRODUCT_QUESTION,
                priority=TicketPriority.MEDIUM,
                sentiment=TicketSentiment.NEUTRAL,
                summary="Customer asks for order help.",
                suggested_action="Reply with next steps.",
                draft_reply="Hi Casey, we can help with your order.",
                confidence_score=90,
                reasoning="Clear support request.",
                requires_human_review=False,
            ),
            {"model": "gemini-test", "output_text": "{}"},
        )

    async def fake_create_draft(access_token: str, raw_message: str, thread_id: str | None = None):
        assert thread_id == "gmail-thread-id"
        return {"id": "draft-123", "message": {"threadId": thread_id}}

    monkeypatch.setattr("app.services.gmail_history_sync_service.refresh_gmail_access_token", fake_refresh)
    monkeypatch.setattr("app.services.gmail_history_sync_service.list_gmail_history", fake_history)
    monkeypatch.setattr("app.services.gmail_history_sync_service.get_gmail_message", fake_get_message)
    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)
    monkeypatch.setattr("app.services.reply_approval_service.refresh_gmail_access_token", fake_refresh)
    monkeypatch.setattr("app.services.reply_approval_service.create_gmail_draft", fake_create_draft)

    with client.session_factory() as db:
        sync_event = asyncio.run(run_gmail_history_sync(db, organization["id"], connection_id))
        ticket = db.scalar(select(Ticket).where(Ticket.organization_id == organization["id"]))
        triage_job = db.scalar(select(JobRun).where(JobRun.job_type == "ai_triage"))
        triage_result = asyncio.run(run_ticket_triage_job(db, triage_job.id))
        approval = db.scalar(select(ReplyApproval).where(ReplyApproval.ticket_id == ticket.id))
        sync_status = sync_event.status
        ticket_id = ticket.id
        ticket_gmail_message_id = ticket.gmail_message_id
        triage_job_id = triage_job.id
        triage_summary = triage_result.summary
        approval_id = approval.id
        approval_status = approval.status

    assert sync_status == "succeeded"
    assert ticket_gmail_message_id == "gmail-1"
    assert stub_auto_triage_dispatch == [triage_job_id]
    assert triage_summary == "Customer asks for order help."
    assert approval_status == "pending"

    approve_response = client.post(
        f"/v1/orgs/{organization['id']}/reply-suggestions/{approval_id}/approve",
        json={"final_reply": "Hi Casey, we can help with your order today."},
    )
    draft_response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{approval_id}/create-gmail-draft")
    resolve_response = client.post(f"/v1/orgs/{organization['id']}/tickets/{ticket_id}/resolve")
    audit_response = client.get(f"/v1/orgs/{organization['id']}/audit-logs")
    disconnect_response = client.delete(f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}")

    assert approve_response.status_code == 200
    assert draft_response.status_code == 201
    assert draft_response.json()["gmail_draft_id"] == "draft-123"
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"
    assert audit_response.status_code == 200
    assert any(item["action"] == "gmail.draft.created" for item in audit_response.json())
    assert disconnect_response.status_code == 204

    async def fake_exchange_oauth_code(code: str):
        return {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "scope": "openid email https://www.googleapis.com/auth/gmail.modify",
        }

    async def fake_fetch_google_userinfo(access_token: str):
        return {"email": "support@example.com", "sub": "google-account-id"}

    async def fake_watch(access_token: str, topic_name: str, label_ids: list[str] | None = None):
        return {"historyId": "reconnected-history", "expiration": "1893456000000"}

    monkeypatch.setattr(settings, "google_client_id", "google-client-id")
    monkeypatch.setattr(settings, "google_client_secret", "google-client-secret")
    monkeypatch.setattr(settings, "google_redirect_uri", "http://localhost:8000/v1/gmail/oauth/callback")
    monkeypatch.setattr("app.services.gmail_connection_service.exchange_oauth_code", fake_exchange_oauth_code)
    monkeypatch.setattr("app.services.gmail_connection_service.fetch_google_userinfo", fake_fetch_google_userinfo)
    monkeypatch.setattr("app.services.gmail_watch_service.watch_gmail_mailbox", fake_watch)

    start_response = client.get(f"/v1/orgs/{organization['id']}/gmail/oauth/start")
    callback_response = client.get(f"/v1/gmail/oauth/callback?state={start_response.json()['state']}&code=callback-code")

    assert start_response.status_code == 200
    assert callback_response.status_code == 200
    with client.session_factory() as db:
        connection = db.get(GmailConnection, connection_id)
        connection.last_successful_sync_at = datetime.now(UTC) - timedelta(minutes=settings.sync_fallback_interval_minutes + 5)
        db.commit()
        stale_connection_ids = [item.id for item in list_stale_connections(db)]
        audit_actions = [item.action for item in db.scalars(select(AuditLog).where(AuditLog.organization_id == organization["id"]))]
        connection_status = connection.status
        connection_watch_status = connection.watch_status
        connection_history_id = connection.gmail_history_id

    assert connection_status == "active"
    assert connection_watch_status == "active"
    assert connection_history_id == "reconnected-history"
    assert stale_connection_ids == [connection_id]
    assert "gmail.connection.connected" in audit_actions

