import sys
from types import SimpleNamespace

import pytest

from app.core import error_tracking
from app.core.config import Settings, settings


class FakeGoogleClient:
    instances = []

    def __init__(self, service=None, version=None):
        self.service = service
        self.version = version
        self.reports = []
        FakeGoogleClient.instances.append(self)

    def report(self, message):
        self.reports.append(message)


class FakeScope:
    def __init__(self):
        self.tags = {}
        self.contexts = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def set_tag(self, key, value):
        self.tags[key] = value

    def set_context(self, key, value):
        self.contexts[key] = value


class FakeSentry:
    def __init__(self):
        self.init_kwargs = None
        self.captured = []
        self.scope = FakeScope()

    def init(self, **kwargs):
        self.init_kwargs = kwargs

    def push_scope(self):
        return self.scope

    def capture_exception(self, exc):
        self.captured.append(exc)


@pytest.fixture(autouse=True)
def reset_error_tracking(monkeypatch):
    FakeGoogleClient.instances = []
    monkeypatch.setattr(error_tracking, "_initialized_provider", None)
    monkeypatch.setattr(error_tracking, "_google_client", None)
    monkeypatch.setattr(settings, "error_tracking_provider", "disabled")
    monkeypatch.setattr(settings, "error_tracking_dsn", None)
    monkeypatch.setattr(settings, "service_name", "api")
    monkeypatch.setattr(settings, "release_version", "test-release")
    monkeypatch.setattr(settings, "app_env", "test")


def install_fake_google_module(monkeypatch):
    fake_module = SimpleNamespace(Client=FakeGoogleClient)
    monkeypatch.setitem(sys.modules, "google.cloud.error_reporting", fake_module)


def test_error_tracking_is_disabled_without_provider():
    assert error_tracking.configure_error_tracking() is False
    error_tracking.capture_exception(RuntimeError("boom"))
    assert FakeGoogleClient.instances == []


def test_google_error_reporting_initializes_client(monkeypatch):
    install_fake_google_module(monkeypatch)
    monkeypatch.setattr(settings, "error_tracking_provider", "google-cloud")
    monkeypatch.setattr(settings, "service_name", "sift-api-staging")
    monkeypatch.setattr(settings, "release_version", "release-123")

    assert error_tracking.configure_error_tracking() is True

    assert len(FakeGoogleClient.instances) == 1
    client = FakeGoogleClient.instances[0]
    assert client.service == "sift-api-staging"
    assert client.version == "release-123"


def test_google_error_reporting_capture_sends_sanitized_context(monkeypatch):
    install_fake_google_module(monkeypatch)
    monkeypatch.setattr(settings, "error_tracking_provider", "google-cloud")

    error_tracking.capture_exception(
        RuntimeError("failure refresh_token=secret-value"),
        event_name="task.job_failed",
        job_id="job-1",
        organization_id="org-1",
        task_type="ai_triage",
    )

    client = FakeGoogleClient.instances[0]
    assert len(client.reports) == 1
    report = client.reports[0]
    assert "task.job_failed" in report
    assert "RuntimeError" in report
    assert "job-1" in report
    assert "org-1" in report
    assert "secret-value" not in report


def test_google_error_reporting_missing_dependency_is_non_fatal(monkeypatch):
    monkeypatch.setattr(settings, "error_tracking_provider", "google-cloud")
    monkeypatch.delitem(sys.modules, "google.cloud.error_reporting", raising=False)

    assert error_tracking.configure_error_tracking() is False
    error_tracking.capture_exception(RuntimeError("boom"))


def test_error_tracking_initializes_sentry_without_pii(monkeypatch):
    fake_sentry = FakeSentry()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    monkeypatch.setattr(settings, "error_tracking_provider", "sentry")
    monkeypatch.setattr(settings, "error_tracking_dsn", "https://example@sentry.invalid/1")
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "release_version", "release-123")

    assert error_tracking.configure_error_tracking() is True

    assert fake_sentry.init_kwargs["dsn"] == "https://example@sentry.invalid/1"
    assert fake_sentry.init_kwargs["environment"] == "staging"
    assert fake_sentry.init_kwargs["release"] == "release-123"
    assert fake_sentry.init_kwargs["send_default_pii"] is False
    assert fake_sentry.init_kwargs["traces_sample_rate"] == 0.0
    assert callable(fake_sentry.init_kwargs["before_send"])


def test_sentry_capture_adds_safe_context(monkeypatch):
    fake_sentry = FakeSentry()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
    monkeypatch.setattr(settings, "error_tracking_provider", "sentry")
    monkeypatch.setattr(settings, "error_tracking_dsn", "https://example@sentry.invalid/1")

    exc = RuntimeError("failure")
    error_tracking.capture_exception(
        exc,
        event_name="task.job_failed",
        job_id="job-1",
        organization_id="org-1",
        task_type="ai_triage",
    )

    assert fake_sentry.captured == [exc]
    assert fake_sentry.scope.tags["event_name"] == "task.job_failed"
    assert fake_sentry.scope.tags["job_id"] == "job-1"
    assert fake_sentry.scope.contexts["sift"]["organization_id"] == "org-1"


def test_error_tracking_before_send_redacts_secret_values():
    event = {
        "message": "Authorization: Bearer abc123 refresh_token=refresh-secret",
        "extra": {
            "api_key": "secret-key",
            "safe": "visible",
            "nested": ["client_secret=hidden-value"],
        },
    }

    cleaned = error_tracking._before_send(event)

    assert "abc123" not in cleaned["message"]
    assert "refresh-secret" not in cleaned["message"]
    assert cleaned["extra"]["api_key"] == "[REDACTED]"
    assert cleaned["extra"]["safe"] == "visible"
    assert "hidden-value" not in cleaned["extra"]["nested"][0]


def test_runtime_validation_accepts_google_cloud_without_dsn():
    config = Settings(error_tracking_provider="google-cloud", _env_file=None)

    config.validate_runtime_settings()


def test_runtime_validation_rejects_invalid_provider():
    config = Settings(error_tracking_provider="unknown", _env_file=None)

    with pytest.raises(RuntimeError, match="ERROR_TRACKING_PROVIDER"):
        config.validate_runtime_settings()


def test_runtime_validation_requires_dsn_for_sentry():
    config = Settings(error_tracking_provider="sentry", error_tracking_dsn=None, _env_file=None)

    with pytest.raises(RuntimeError, match="ERROR_TRACKING_DSN"):
        config.validate_runtime_settings()
