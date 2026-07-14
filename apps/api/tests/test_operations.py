import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.gmail_connection import GmailConnection
from app.models.job_run import JobRun
from app.models.member import MemberRole, OrganizationMember
from app.services.ai_triage_service import run_ticket_triage_job
from app.services.operations_service import classify_error, sanitize_error


def create_ticket(client: TestClient, organization_id: str) -> dict:
    response = client.post(
        f"/v1/orgs/{organization_id}/tickets",
        json={
            "customer_email": "customer@example.com",
            "customer_name": "Casey Customer",
            "subject": "Need help",
            "message_text": "The item arrived broken and I need help.",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_workspace_operations_lists_retryable_failures_and_retries(
    client: TestClient,
    create_org,
    monkeypatch,
    stub_auto_triage_dispatch,
) -> None:
    organization = create_org()
    ticket = create_ticket(client, organization["id"])

    async def fake_classify(prompt: str):
        raise RuntimeError("Gemini 429 timeout access_token=secret-token")

    monkeypatch.setattr("app.services.ai_triage_service.classify_ticket_with_gemini", fake_classify)

    with client.session_factory() as db:
        job = db.scalar(select(JobRun).where(JobRun.job_type == "ai_triage"))
        with pytest.raises(RuntimeError):
            asyncio.run(run_ticket_triage_job(db, job.id))
        failed_job = db.get(JobRun, job.id)
        assert failed_job.retryable is True
        assert failed_job.error_code == "retryable_error"
        assert "secret-token" not in failed_job.error_message

    response = client.get(f"/v1/orgs/{organization['id']}/operations/failures")
    assert response.status_code == 200
    failures = response.json()["jobs"]
    assert failures[0]["job_type"] == "ai_triage"
    assert failures[0]["queue_name"] == "ai_triage"
    assert failures[0]["related_resource_id"] == ticket["id"]
    assert failures[0]["retryable"] is True

    retry_response = client.post(f"/v1/orgs/{organization['id']}/operations/jobs/{job.id}/retry")
    assert retry_response.status_code == 202
    retry_job = retry_response.json()["retry_job"]
    assert retry_job["status"] == "queued"
    assert retry_job["job_metadata"]["manual_retry"] is True
    assert stub_auto_triage_dispatch[-1] == retry_job["id"]


def test_operations_requires_admin_or_owner(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        member = db.scalar(
            select(OrganizationMember).where(OrganizationMember.organization_id == organization["id"])
        )
        member.role = MemberRole.AGENT.value
        db.commit()

    response = client.get(f"/v1/orgs/{organization['id']}/operations/failures")

    assert response.status_code == 403


def test_internal_system_failures_require_operations_token(client: TestClient, create_org, monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.operations_internal_token", "ops-secret")
    organization = create_org()
    with client.session_factory() as db:
        db.add(
            JobRun(
                organization_id=organization["id"],
                job_type="gmail_import",
                queue_name="gmail_sync",
                status="failed",
                error_message="timeout",
                retryable=True,
            )
        )
        db.commit()

    denied = client.get("/v1/operations/failures")
    allowed = client.get("/v1/operations/failures", headers={"x-operations-token": "ops-secret"})

    assert denied.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["jobs"][0]["job_type"] == "gmail_import"


def test_sync_health_surfaces_degraded_connections(client: TestClient, create_org) -> None:
    organization = create_org()
    with client.session_factory() as db:
        db.add(
            GmailConnection(
                organization_id=organization["id"],
                connected_by_user_id="user-owner",
                gmail_email="support@example.com",
                google_account_id="google-account-id",
                encrypted_refresh_token="encrypted",
                scopes="openid email https://www.googleapis.com/auth/gmail.modify",
                status="active",
                sync_status="degraded",
                sync_error_code="history_sync_failed",
                sync_error_message="refresh_token=secret-value timeout",
                consecutive_sync_failures=2,
            )
        )
        db.commit()

    response = client.get(f"/v1/orgs/{organization['id']}/operations/sync-health")

    assert response.status_code == 200
    body = response.json()
    assert body["degraded_connections"] == 1
    assert body["connections"][0]["degraded"] is True
    assert "secret-value" not in body["connections"][0]["sync_error_message"]


def test_error_sanitizer_and_classifier_redact_secrets() -> None:
    message = "Authorization: Bearer abc refresh_token=refresh access_token=access Gemini 503 timeout"

    sanitized = sanitize_error(message)
    _, error_code, retryable = classify_error(message)

    assert "abc" not in sanitized
    assert "refresh" not in sanitized.split("refresh_token", 1)[-1]
    assert error_code == "retryable_error"
    assert retryable is True

def test_error_reporting_test_requires_scheduler_identity(client: TestClient) -> None:
    response = client.post("/v1/operations/error-reporting-test")

    assert response.status_code == 401


def test_error_reporting_test_reports_with_scheduler_identity(client: TestClient, monkeypatch) -> None:
    captured: list[tuple[Exception, dict]] = []
    monkeypatch.setattr(
        "app.api.routes.operations.verify_scheduler_oidc_token",
        lambda authorization: {"email": "scheduler@example.com"},
    )
    monkeypatch.setattr(
        "app.api.routes.operations.capture_exception",
        lambda exc, **context: captured.append((exc, context)),
    )

    response = client.post(
        "/v1/operations/error-reporting-test",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "reported"}
    assert isinstance(captured[0][0], RuntimeError)
    assert captured[0][1]["event_name"] == "operations.error_reporting_test"
    assert captured[0][1]["task_type"] == "error_reporting_test"

