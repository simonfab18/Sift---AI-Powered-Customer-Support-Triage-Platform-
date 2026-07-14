from __future__ import annotations

import importlib
import logging
from typing import Any

from app.core.config import settings
from app.core.logging import (
    SENSITIVE_KEYS,
    connection_id_var,
    job_id_var,
    organization_id_var,
    redact_value,
    request_id_var,
    ticket_id_var,
)

logger = logging.getLogger(__name__)
_initialized_provider: str | None = None
_google_client: Any | None = None


def _clean_event_value(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, nested_value in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = _clean_event_value(nested_value)
        return cleaned
    if isinstance(value, list):
        return [_clean_event_value(item) for item in value]
    if isinstance(value, str):
        return redact_value(value)
    return value


def _before_send(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    return _clean_event_value(event)


def _event_context(**context: Any) -> dict[str, Any]:
    safe_context = {
        "request_id": context.get("request_id") or request_id_var.get(),
        "job_id": context.get("job_id") or job_id_var.get(),
        "organization_id": context.get("organization_id") or organization_id_var.get(),
        "connection_id": context.get("connection_id") or connection_id_var.get(),
        "ticket_id": context.get("ticket_id") or ticket_id_var.get(),
        "event_name": context.get("event_name"),
        "task_type": context.get("task_type"),
        "environment": settings.app_env,
        "release_version": settings.release_version,
    }
    return _clean_event_value({key: value for key, value in safe_context.items() if value})


def configure_error_tracking() -> bool:
    provider = settings.normalized_error_tracking_provider
    if provider == "disabled":
        return False
    if provider == _initialized_provider:
        return True
    if provider == "google-cloud":
        return _configure_google_error_reporting()
    if provider == "sentry":
        return _configure_sentry()
    return False


def _configure_google_error_reporting() -> bool:
    global _google_client, _initialized_provider
    try:
        error_reporting = importlib.import_module("google.cloud.error_reporting")
    except ImportError:
        logger.warning(
            "Google Cloud Error Reporting is configured but google-cloud-error-reporting is not installed",
            extra={"event_name": "error_tracking.missing_dependency"},
        )
        return False

    _google_client = error_reporting.Client(
        service=settings.service_name,
        version=settings.release_version,
    )
    _initialized_provider = "google-cloud"
    logger.info(
        "Google Cloud Error Reporting configured",
        extra={"event_name": "error_tracking.configured"},
    )
    return True


def _configure_sentry() -> bool:
    global _initialized_provider
    if not settings.error_tracking_dsn:
        return False
    try:
        sentry_sdk = importlib.import_module("sentry_sdk")
    except ImportError:
        logger.warning(
            "Error tracking DSN is configured but sentry-sdk is not installed",
            extra={"event_name": "error_tracking.missing_dependency"},
        )
        return False

    sentry_sdk.init(
        dsn=settings.error_tracking_dsn,
        environment=settings.app_env,
        release=settings.release_version,
        send_default_pii=False,
        traces_sample_rate=0.0,
        before_send=_before_send,
    )
    _initialized_provider = "sentry"
    logger.info("Sentry error tracking configured", extra={"event_name": "error_tracking.configured"})
    return True


def capture_exception(exc: Exception, **context: Any) -> None:
    provider = settings.normalized_error_tracking_provider
    if provider == "disabled":
        return
    if provider == "google-cloud":
        _capture_google_exception(exc, **context)
        return
    if provider == "sentry":
        _capture_sentry_exception(exc, **context)


def _capture_google_exception(exc: Exception, **context: Any) -> None:
    if _google_client is None and not _configure_google_error_reporting():
        return
    if _google_client is None:
        return

    safe_context = _event_context(**context)
    sanitized_error = redact_value(str(exc))
    message = (
        f"{safe_context.get('event_name', 'application.exception')}: "
        f"{exc.__class__.__name__}: {sanitized_error}\n"
        f"context={safe_context}"
    )
    try:
        _google_client.report(message)
    except Exception as report_exc:
        logger.warning(
            "Google Cloud Error Reporting submission failed",
            extra={
                "event_name": "error_tracking.submit_failed",
                "sanitized_error": redact_value(str(report_exc)),
            },
        )


def _capture_sentry_exception(exc: Exception, **context: Any) -> None:
    if not settings.error_tracking_dsn:
        return
    try:
        sentry_sdk = importlib.import_module("sentry_sdk")
    except ImportError:
        return

    safe_context = _event_context(**context)
    with sentry_sdk.push_scope() as scope:
        for key, value in safe_context.items():
            scope.set_tag(key, str(redact_value(value)))
        if safe_context:
            scope.set_context("sift", _clean_event_value(safe_context))
        sentry_sdk.capture_exception(exc)
