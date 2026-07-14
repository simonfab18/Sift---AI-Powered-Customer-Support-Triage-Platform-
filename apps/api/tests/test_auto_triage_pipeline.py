import asyncio
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import AuthenticatedUser
from app.integrations.gemini.client import GeminiQuotaExceededError
from app.models.ai_triage_result import AITriageResult
from app.models.job_run import JobRun
from app.models.reply_approval import ReplyApproval
from app.models.ticket import Ticket
from app.models.ticket_event import TicketEvent
from app.models.workspace_settings import WorkspaceSettings
from app.schemas.ai import TriageOutput
from app.models.ticket import TicketCategory, TicketPriority, TicketSentiment
from app.services.ai_triage_service import PROMPT_VERSION, SCHEMA_VERSION, run_ticket_triage_job
from app.services.job_queue_service import enqueue_ticket_triage


def create_api_ticket(client: TestClient, organization_id: str, subject: str = "Need help") -> dict:
    response = client.post(
        f"/v1/orgs/{organization_id}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": subject,
            "message_text": "The item arrived broken and I need help.",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_ticket_creation_queues_auto_triage(client: TestClient, create_org, stub_auto_triage_dispatch) -> None:
    organization = create_org()
    ticket = create_api_ticket(client, organization["id"])

    with client.session_factory() as db:
        stored_ticket = db.get(Ticket, ticket["id"])
        job = db.scalar(select(JobRun).where(JobRun.job_type == "ai_triage"))

    assert stored_ticket.triage_status == "queued"
    assert stored_ticket.active_triage_job_id == job.id
    assert job.status == "queued"
    assert job.job_metadata["ticket_id"] == ticket["id"]
    assert job.job_metadata["prompt_version"] == PROMPT_VERSION
    assert stub_auto_triage_dispatch == [job.id]


def test_workspace_setting_can_disable_auto_triage(client: TestClient, create_org, stub_auto_triage_dispatch) -> None:
    organization = create_org()
    with client.session_factory() as db:
        db.add(WorkspaceSettings(organization_id=organization["id"], auto_triage_enabled=False))
        db.commit()

    ticket = create_api_ticket(client, organization["id"])

    with client.session_factory() as db:
        stored_ticket = db.get(Ticket, ticket["id"])
        jobs = list(db.scalars(select(JobRun).where(JobRun.job_type == "ai_triage")))

    assert stored_ticket.triage_status == "not_queued"
    assert jobs == []
    assert stub_auto_triage_dispatch == []


def test_enqueue_ticket_triage_reuses_active_job(client: TestClient, create_org, stub_auto_triage_dispatch) -> None:
    organization = create_org()
    ticket = create_api_ticket(client, organization["id"])
    actor = AuthenticatedUser(id="user-owner", email="owner@example.com")

    with client.session_factory() as db:
        existing_job = db.scalar(select(JobRun).where(JobRun.job_type == "ai_triage"))
        reused_job = enqueue_ticket_triage(db, organization["id"], ticket["id"], actor)
        jobs = list(db.scalars(select(JobRun).where(JobRun.job_type == "ai_triage")))

    assert reused_job.id == existing_job.id
    assert len(jobs) == 1
    assert stub_auto_triage_dispatch == [existing_job.id]


def test_triage_worker_completes_job_and_versions_result(client: TestClient, create_org, monkeypatch) -> None:
    organization = create_org()
    ticket = create_api_ticket(client, organization["id"], subject="Refund request")

    async def fake_classify(prompt: str):
        return (
            TriageOutput(
                category=TicketCategory.REFUND,
                priority=TicketPriority.HIGH,
                sentiment=TicketSentiment.NEGATIVE,
                summary="Customer needs a refund.",
                suggested_action="Review refund eligibility.",
                draft_reply="Hi Casey, we can help with that.",
                confidence_score=92,
                reasoning="Refund request is explicit.",
                requires_human_review=False,
            ),
            {"model": "gemini-test", "output_text": "{}"},
        )

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)

    with client.session_factory() as db:
        job = db.scalar(select(JobRun).where(JobRun.job_type == "ai_triage"))
        result = asyncio.run(run_ticket_triage_job(db, job.id))
        stored_ticket = db.get(Ticket, ticket["id"])
        stored_job = db.get(JobRun, job.id)
        approval = db.scalar(select(ReplyApproval).where(ReplyApproval.ticket_id == ticket["id"]))
        event_types = [event.event_type for event in db.scalars(select(TicketEvent).where(TicketEvent.ticket_id == ticket["id"]))]

    assert result.prompt_version == PROMPT_VERSION
    assert result.schema_version == SCHEMA_VERSION
    assert result.job_run_id == job.id
    assert result.latency_ms is not None
    assert stored_ticket.triage_status == "triaged"
    assert stored_ticket.active_triage_job_id is None
    assert stored_ticket.priority == "high"
    assert stored_job.status == "succeeded"
    assert stored_job.job_metadata["ai_triage_result_id"] == result.id
    assert approval is not None
    assert "ticket.ai_triaged" in event_types



def test_quota_failed_triage_sets_retry_after_without_pubsub_redelivery(
    client: TestClient,
    create_org,
    monkeypatch,
) -> None:
    from app.services import task_runner_service

    organization = create_org()
    ticket = create_api_ticket(client, organization["id"])

    async def fake_classify(prompt: str):
        raise GeminiQuotaExceededError("Gemini quota exceeded", retry_after_seconds=61)

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)
    monkeypatch.setattr(task_runner_service, "SessionLocal", client.session_factory)

    with client.session_factory() as db:
        job = db.scalar(select(JobRun).where(JobRun.job_type == "ai_triage"))
        job_id = job.id

    status, returned_id = task_runner_service.run_ai_triage_task(job_id=job_id)

    assert status == "deferred"
    assert returned_id == job_id
    with client.session_factory() as db:
        failed_ticket = db.get(Ticket, ticket["id"])
        failed_job = db.get(JobRun, job_id)

    assert failed_ticket.triage_status == "triage_failed"
    assert failed_ticket.active_triage_job_id is None
    assert failed_ticket.triage_error_message == "Gemini quota exceeded"
    assert failed_job.status == "failed"
    assert failed_job.error_code == "quota_exceeded"
    assert failed_job.retryable is True
    assert failed_job.next_retry_at is not None
    assert 55 <= (failed_job.next_retry_at - failed_job.finished_at).total_seconds() <= 70


def test_free_tier_daily_limit_defers_without_calling_gemini(
    client: TestClient,
    create_org,
    monkeypatch,
) -> None:
    from app.core.config import settings
    from app.services import task_runner_service

    organization = create_org()
    ticket = create_api_ticket(client, organization["id"])
    monkeypatch.setattr(settings, "ai_triage_daily_gemini_limit", 1)

    async def fail_if_called(prompt: str):
        raise AssertionError("Gemini should not be called after the free-tier daily limit is reached")

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fail_if_called)
    monkeypatch.setattr(task_runner_service, "SessionLocal", client.session_factory)

    with client.session_factory() as db:
        job = db.scalar(select(JobRun).where(JobRun.job_type == "ai_triage"))
        job_id = job.id
        db.add(
            JobRun(
                organization_id=organization["id"],
                job_type="ai_triage",
                queue_name="ai_triage",
                status="succeeded",
                attempts=1,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                job_metadata={"ticket_id": "previous-ticket"},
            )
        )
        db.commit()

    status, returned_id = task_runner_service.run_ai_triage_task(job_id=job_id)

    assert status == "deferred"
    assert returned_id == job_id
    with client.session_factory() as db:
        failed_ticket = db.get(Ticket, ticket["id"])
        failed_job = db.get(JobRun, job_id)
        results = list(db.scalars(select(AITriageResult).where(AITriageResult.ticket_id == ticket["id"])))

    assert failed_ticket.triage_status == "triage_failed"
    assert failed_ticket.triage_error_message == "Gemini free-tier daily triage limit reached; retry after the next UTC day."
    assert failed_job.status == "failed"
    assert failed_job.error_code == "quota_exceeded"
    assert failed_job.retryable is True
    assert failed_job.next_retry_at is not None
    assert results == []

def test_failed_triage_is_visible_and_retryable(client: TestClient, create_org, monkeypatch, stub_auto_triage_dispatch) -> None:
    organization = create_org()
    ticket = create_api_ticket(client, organization["id"])

    async def fake_classify(prompt: str):
        raise RuntimeError("Gemini timeout")

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)

    with client.session_factory() as db:
        job = db.scalar(select(JobRun).where(JobRun.job_type == "ai_triage"))
        with pytest.raises(RuntimeError):
            asyncio.run(run_ticket_triage_job(db, job.id))
        failed_ticket = db.get(Ticket, ticket["id"])
        failed_job = db.get(JobRun, job.id)

    assert failed_ticket.triage_status == "triage_failed"
    assert failed_ticket.triage_error_message == "Gemini timeout"
    assert failed_ticket.active_triage_job_id is None
    assert failed_job.status == "failed"

    retry_response = client.post(f"/v1/orgs/{organization['id']}/tickets/{ticket['id']}/triage/retry")

    assert retry_response.status_code == 202
    retry_job = retry_response.json()
    assert retry_job["status"] == "queued"
    assert retry_job["job_metadata"]["manual_retry"] is True
    assert stub_auto_triage_dispatch[-1] == retry_job["id"]

    with client.session_factory() as db:
        results = list(db.scalars(select(AITriageResult).where(AITriageResult.ticket_id == ticket["id"])))

    assert results == []
