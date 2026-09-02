from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.core.encryption import encrypt_secret
from app.models.ai_triage_result import AITriageResult
from app.models.gmail_connection import GmailConnection
from app.models.job_run import JobRun
from app.models.mail_import_rule import MailImportRule
from app.models.reply_approval import ReplyApproval
from app.models.ticket import Ticket
from app.models.workspace_settings import WorkspaceSettings


def _create_active_connection(client: TestClient, organization_id: str) -> str:
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


def _create_approved_reply(client: TestClient, organization_id: str, connection_id: str) -> str:
    ticket_response = client.post(
        f"/v1/orgs/{organization_id}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": "Question about my order",
            "message_text": "Can you help me with my order?",
        },
    )
    ticket_id = ticket_response.json()["id"]
    with client.session_factory() as db:
        ticket = db.get(Ticket, ticket_id)
        ticket.gmail_connection_id = connection_id
        ticket.gmail_thread_id = "gmail-thread-id"
        triage = AITriageResult(
            organization_id=organization_id,
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
            organization_id=organization_id,
            ticket_id=ticket.id,
            ai_triage_result_id=triage.id,
            gmail_connection_id=connection_id,
            suggested_reply="Suggested reply.",
            final_reply="Suggested reply.",
            status="approved",
            approved_by_user_id="user-owner",
        )
        db.add(approval)
        db.commit()
        return approval.id


def test_workspace_settings_expose_pilot_controls(client: TestClient, create_org) -> None:
    organization = create_org()

    response = client.patch(
        f"/v1/orgs/{organization['id']}/workspace-settings",
        json={
            "sync_enabled": False,
            "draft_creation_enabled": False,
            "pilot_feedback_contact": "pilot-support@example.com",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sync_enabled"] is False
    assert body["draft_creation_enabled"] is False
    assert body["pilot_feedback_contact"] == "pilot-support@example.com"


def test_pilot_allowlist_blocks_oauth_start(client: TestClient, create_org, monkeypatch) -> None:
    organization = create_org()
    monkeypatch.setattr(settings, "google_client_id", "google-client-id")
    monkeypatch.setattr(settings, "pilot_require_allowlist", True)
    monkeypatch.setattr(settings, "pilot_allowlisted_organization_ids", "other-org")

    response = client.get(f"/v1/orgs/{organization['id']}/gmail/oauth/start")

    assert response.status_code == 403
    assert response.json()["detail"] == "Organization is not enabled for the pilot"


def test_workspace_sync_switch_blocks_manual_sync_queue(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = _create_active_connection(client, organization["id"])
    with client.session_factory() as db:
        db.add(WorkspaceSettings(organization_id=organization["id"], sync_enabled=False))
        db.commit()

    response = client.post(
        f"/v1/orgs/{organization['id']}/gmail/connections/{connection_id}/sync/queue",
        json={"max_results": 5},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Gmail sync is disabled for this pilot workspace"


def test_global_auto_triage_switch_leaves_new_ticket_not_queued(
    client: TestClient,
    create_org,
    monkeypatch,
    stub_auto_triage_dispatch,
) -> None:
    organization = create_org()
    monkeypatch.setattr(settings, "pilot_auto_triage_enabled", False)

    response = client.post(
        f"/v1/orgs/{organization['id']}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": "Need help",
            "message_text": "The item arrived broken and I need help.",
        },
    )

    assert response.status_code == 201
    ticket_id = response.json()["id"]
    with client.session_factory() as db:
        ticket = db.get(Ticket, ticket_id)
        jobs = list(db.scalars(select(JobRun).where(JobRun.job_type == "ai_triage")))
    assert ticket.triage_status == "not_queued"
    assert jobs == []
    assert stub_auto_triage_dispatch == []


def test_draft_creation_switch_blocks_gmail_draft_without_deleting_approval(
    client: TestClient,
    create_org,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "encryption_key", "test-encryption-key")
    organization = create_org()
    connection_id = _create_active_connection(client, organization["id"])
    approval_id = _create_approved_reply(client, organization["id"], connection_id)
    with client.session_factory() as db:
        settings_row = db.scalar(select(WorkspaceSettings).where(WorkspaceSettings.organization_id == organization["id"]))
        settings_row.draft_creation_enabled = False
        db.commit()

    response = client.post(f"/v1/orgs/{organization['id']}/reply-suggestions/{approval_id}/create-gmail-draft")

    assert response.status_code == 403
    assert response.json()["detail"] == "Gmail draft creation is disabled for this pilot workspace"
    with client.session_factory() as db:
        approval = db.get(ReplyApproval, approval_id)
    assert approval.status == "approved"
    assert approval.gmail_draft_id is None



