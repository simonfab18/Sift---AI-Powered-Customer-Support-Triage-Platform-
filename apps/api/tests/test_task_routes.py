import base64
import json

from fastapi import HTTPException, status
from fastapi.testclient import TestClient


def encode_payload(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")


def test_task_route_rejects_missing_google_identity(client: TestClient) -> None:
    response = client.post(
        "/v1/tasks/ai/triage",
        json={"message": {"messageId": "task-1", "data": encode_payload({"job_id": "job-1"})}},
    )

    assert response.status_code == 401


def test_task_route_rejects_unexpected_google_identity(client: TestClient, monkeypatch) -> None:
    def fake_verify(authorization: str | None):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unexpected task Pub/Sub service account")

    monkeypatch.setattr("app.api.routes.tasks.verify_task_pubsub_oidc_token", fake_verify)

    response = client.post(
        "/v1/tasks/ai/triage",
        headers={"Authorization": "Bearer bad-token"},
        json={"message": {"messageId": "task-1", "data": encode_payload({"job_id": "job-1"})}},
    )

    assert response.status_code == 401


def test_ai_triage_task_route_runs_task_with_valid_identity(client: TestClient, monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr("app.api.routes.tasks.verify_task_pubsub_oidc_token", lambda authorization: {"email": "task@example.com"})
    monkeypatch.setattr("app.api.routes.tasks.run_ai_triage_task", lambda *, job_id: calls.append(job_id) or ("completed", "result-1"))

    response = client.post(
        "/v1/tasks/ai/triage",
        headers={"Authorization": "Bearer valid-token"},
        json={"message": {"messageId": "task-1", "data": encode_payload({"job_id": "job-1"})}},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "completed", "ai_triage_result_id": "result-1"}
    assert calls == ["job-1"]


def test_scheduler_route_requires_scheduler_identity(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.tasks.verify_scheduler_oidc_token",
        lambda authorization: (_ for _ in ()).throw(HTTPException(status_code=401, detail="bad scheduler")),
    )

    response = client.post("/v1/tasks/scheduler/fallback-sync", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 401


def test_scheduler_route_runs_with_valid_identity(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.api.routes.tasks.verify_scheduler_oidc_token", lambda authorization: {"email": "scheduler@example.com"})
    monkeypatch.setattr("app.api.routes.tasks.run_fallback_sync_scheduler_task", lambda: ["event-1", "event-2"])

    response = client.post("/v1/tasks/scheduler/fallback-sync", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    assert response.json() == {"status": "completed", "queued_event_ids": ["event-1", "event-2"], "count": 2}
