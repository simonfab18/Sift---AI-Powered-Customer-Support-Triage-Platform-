from __future__ import annotations

from contextvars import ContextVar
from datetime import UTC, datetime
import json
import logging
import re
import sys
from typing import Any
from uuid import uuid4

from app.core.config import settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
job_id_var: ContextVar[str | None] = ContextVar("job_id", default=None)
organization_id_var: ContextVar[str | None] = ContextVar("organization_id", default=None)
connection_id_var: ContextVar[str | None] = ContextVar("connection_id", default=None)
ticket_id_var: ContextVar[str | None] = ContextVar("ticket_id", default=None)

SENSITIVE_KEYS = {
    "authorization",
    "access_token",
    "refresh_token",
    "encrypted_refresh_token",
    "prompt",
    "message_text",
    "message_html",
    "client_secret",
    "api_key",
    "password",
}
SECRET_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s,]+"),
    re.compile(r"(?i)((?:access|refresh)[_-]?token[\"'=:\s]+)[^\s,}\"]+"),
    re.compile(r"(?i)((?:client[_-]?secret|api[_-]?key|password)[\"'=:\s]+)[^\s,}\"]+"),
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "environment": settings.app_env,
            "service": settings.service_name,
            "severity": record.levelname,
            "event_name": getattr(record, "event_name", record.getMessage()),
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or request_id_var.get(),
            "job_id": getattr(record, "job_id", None) or job_id_var.get(),
            "organization_id": getattr(record, "organization_id", None) or organization_id_var.get(),
            "connection_id": getattr(record, "connection_id", None) or connection_id_var.get(),
            "ticket_id": getattr(record, "ticket_id", None) or ticket_id_var.get(),
            "release_version": settings.release_version,
        }
        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        error = getattr(record, "sanitized_error", None)
        if error:
            payload["sanitized_error"] = str(error)
        return json.dumps(_clean_payload(payload), default=str, separators=(",", ":"))


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if key.lower() in SENSITIVE_KEYS:
            cleaned[key] = "[REDACTED]"
        else:
            cleaned[key] = redact_value(value)
    return cleaned


def redact_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    redacted = value
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


def configure_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.logging_level.upper())


def new_request_id() -> str:
    return str(uuid4())


def set_request_context(request_id: str | None = None):
    return request_id_var.set(request_id)


def reset_request_context(token) -> None:
    request_id_var.reset(token)
