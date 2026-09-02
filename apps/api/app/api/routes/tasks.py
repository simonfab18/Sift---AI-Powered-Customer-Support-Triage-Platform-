import base64
import json
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.services.pubsub_verification_service import verify_scheduler_oidc_token, verify_task_pubsub_oidc_token
from app.services.task_runner_service import (
    run_ai_triage_task,
    run_fallback_sync_scheduler_task,
    run_gmail_history_sync_task,
    run_gmail_import_task,
    run_watch_renewal_task,
    run_watch_renewals_scheduler_task,
)

router = APIRouter(tags=["tasks"])


class PubSubMessage(BaseModel):
    data: str | None = None
    message_id: str | None = Field(default=None, alias="messageId")
    publish_time: str | None = Field(default=None, alias="publishTime")
    attributes: dict[str, str] = Field(default_factory=dict)


class PubSubPushEnvelope(BaseModel):
    message: PubSubMessage
    subscription: str | None = None


def _decode_pubsub_payload(data: str | None) -> dict[str, Any]:
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pub/Sub message data is required")
    padded = data + "=" * (-len(data) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pub/Sub message data is invalid") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pub/Sub message payload is invalid")
    return payload


def _require_fields(payload: dict[str, Any], fields: set[str]) -> None:
    missing = sorted(field for field in fields if payload.get(field) in {None, ""})
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task payload missing fields: " + ", ".join(missing))


def _task_payload(envelope: PubSubPushEnvelope, authorization: str | None) -> dict[str, Any]:
    verify_task_pubsub_oidc_token(authorization)
    return _decode_pubsub_payload(envelope.message.data)


@router.post("/tasks/gmail/import")
def run_gmail_import(envelope: PubSubPushEnvelope, authorization: str | None = Header(default=None)) -> dict[str, str]:
    payload = _task_payload(envelope, authorization)
    _require_fields(payload, {"job_id", "organization_id", "connection_id", "actor_id", "max_results"})
    job_id = run_gmail_import_task(
        job_id=str(payload["job_id"]),
        organization_id=str(payload["organization_id"]),
        connection_id=str(payload["connection_id"]),
        actor_id=str(payload["actor_id"]),
        actor_email=payload.get("actor_email"),
        max_results=int(payload["max_results"]),
    )
    return {"status": "completed", "job_id": job_id}


@router.post("/tasks/gmail/history-sync")
def run_gmail_history_sync(envelope: PubSubPushEnvelope, authorization: str | None = Header(default=None)) -> dict[str, str]:
    payload = _task_payload(envelope, authorization)
    _require_fields(payload, {"organization_id", "connection_id", "event_id"})
    event_id = run_gmail_history_sync_task(
        organization_id=str(payload["organization_id"]),
        connection_id=str(payload["connection_id"]),
        event_id=str(payload["event_id"]),
        notification_history_id=payload.get("notification_history_id"),
        trigger_type=str(payload.get("trigger_type") or "history_sync"),
    )
    return {"status": "completed", "event_id": event_id}


@router.post("/tasks/ai/triage")
def run_ai_triage(envelope: PubSubPushEnvelope, authorization: str | None = Header(default=None)) -> dict[str, str]:
    payload = _task_payload(envelope, authorization)
    _require_fields(payload, {"job_id"})
    task_status, result_id = run_ai_triage_task(job_id=str(payload["job_id"]))
    if task_status == "deferred":
        return {"status": "deferred", "job_id": result_id}
    return {"status": "completed", "ai_triage_result_id": result_id}


@router.post("/tasks/gmail/watch-renewal")
def run_gmail_watch_renewal(envelope: PubSubPushEnvelope, authorization: str | None = Header(default=None)) -> dict[str, str]:
    payload = _task_payload(envelope, authorization)
    _require_fields(payload, {"organization_id", "connection_id"})
    event_id = run_watch_renewal_task(
        organization_id=str(payload["organization_id"]),
        connection_id=str(payload["connection_id"]),
    )
    return {"status": "completed", "event_id": event_id}


@router.post("/tasks/scheduler/fallback-sync")
def run_scheduler_fallback_sync(authorization: str | None = Header(default=None)) -> dict[str, object]:
    verify_scheduler_oidc_token(authorization)
    event_ids = run_fallback_sync_scheduler_task()
    return {"status": "completed", "queued_event_ids": event_ids, "count": len(event_ids)}


@router.post("/tasks/scheduler/watch-renewals")
def run_scheduler_watch_renewals(authorization: str | None = Header(default=None)) -> dict[str, object]:
    verify_scheduler_oidc_token(authorization)
    connection_ids = run_watch_renewals_scheduler_task()
    return {"status": "completed", "queued_connection_ids": connection_ids, "count": len(connection_ids)}
