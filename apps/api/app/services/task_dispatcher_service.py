from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class TaskDispatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class DispatchedTask:
    task_type: str
    message_id: str
    topic: str


GMAIL_IMPORT = "gmail_import"
GMAIL_HISTORY_SYNC = "gmail_history_sync"
AI_TRIAGE = "ai_triage"
WATCH_RENEWAL = "watch_renewal"


def _topic_for_task(task_type: str) -> str | None:
    return {
        GMAIL_IMPORT: settings.task_pubsub_gmail_import_topic,
        GMAIL_HISTORY_SYNC: settings.task_pubsub_gmail_history_sync_topic,
        AI_TRIAGE: settings.task_pubsub_ai_triage_topic,
        WATCH_RENEWAL: settings.task_pubsub_watch_renewal_topic,
    }.get(task_type)


def _resolve_topic_path(topic: str) -> str:
    if topic.startswith("projects/"):
        return topic
    if not settings.google_cloud_project_id:
        raise TaskDispatchError("GOOGLE_CLOUD_PROJECT_ID is required for Pub/Sub dispatch")
    return f"projects/{settings.google_cloud_project_id}/topics/{topic}"


def publish_task(task_type: str, payload: dict[str, Any]) -> DispatchedTask:
    topic = _topic_for_task(task_type)
    message = {"task_type": task_type, **payload}
    if settings.normalized_task_queue_backend == "local":
        topic = topic or f"local-{task_type}"
        message_id = f"local-{task_type}-{payload.get('job_id') or payload.get('event_id') or payload.get('connection_id') or 'task'}"
        logger.info(
            "Task dispatch recorded locally",
            extra={"event_name": "task.dispatch.local", "task_type": task_type, "message_id": message_id},
        )
        return DispatchedTask(task_type=task_type, message_id=message_id, topic=topic)

    if not topic:
        raise TaskDispatchError(f"No Pub/Sub topic configured for task type {task_type}")

    if settings.normalized_task_queue_backend != "pubsub":
        raise TaskDispatchError(f"Unsupported task queue backend: {settings.task_queue_backend}")

    try:
        from google.cloud import pubsub_v1
    except ImportError as exc:
        raise TaskDispatchError("google-cloud-pubsub is required for Pub/Sub task dispatch") from exc

    try:
        publisher = pubsub_v1.PublisherClient()
        topic_path = _resolve_topic_path(topic)
        future = publisher.publish(
            topic_path,
            json.dumps(message, separators=(",", ":")).encode("utf-8"),
            task_type=task_type,
        )
        message_id = future.result(timeout=15)
    except Exception as exc:
        raise TaskDispatchError(f"Could not publish {task_type} task: {exc}") from exc

    logger.info(
        "Task dispatched to Pub/Sub",
        extra={"event_name": "task.dispatch.pubsub", "task_type": task_type, "message_id": message_id, "topic": topic},
    )
    return DispatchedTask(task_type=task_type, message_id=message_id, topic=topic)


def publish_gmail_import_task(
    *,
    job_id: str,
    organization_id: str,
    connection_id: str,
    actor_id: str,
    actor_email: str | None,
    max_results: int,
) -> DispatchedTask:
    return publish_task(
        GMAIL_IMPORT,
        {
            "job_id": job_id,
            "organization_id": organization_id,
            "connection_id": connection_id,
            "actor_id": actor_id,
            "actor_email": actor_email,
            "max_results": max_results,
        },
    )


def publish_gmail_history_sync_task(
    *,
    organization_id: str,
    connection_id: str,
    event_id: str,
    notification_history_id: str | None,
    trigger_type: str,
) -> DispatchedTask:
    return publish_task(
        GMAIL_HISTORY_SYNC,
        {
            "organization_id": organization_id,
            "connection_id": connection_id,
            "event_id": event_id,
            "notification_history_id": notification_history_id,
            "trigger_type": trigger_type,
        },
    )


def publish_ai_triage_task(*, job_id: str) -> DispatchedTask:
    return publish_task(AI_TRIAGE, {"job_id": job_id})


def publish_watch_renewal_task(*, organization_id: str, connection_id: str) -> DispatchedTask:
    return publish_task(
        WATCH_RENEWAL,
        {"organization_id": organization_id, "connection_id": connection_id},
    )