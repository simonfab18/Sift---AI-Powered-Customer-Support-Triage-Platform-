from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_encryption_keyring(raw: str | None) -> dict[int, str]:
    if not raw:
        return {}

    parsed: dict[int, str] = {}
    for item in raw.split(","):
        entry = item.strip()
        if not entry:
            continue
        if ":" not in entry:
            raise ValueError("ENCRYPTION_KEYRING entries must use version:key format.")
        version_text, key = entry.split(":", 1)
        try:
            version = int(version_text.strip())
        except ValueError as exc:
            raise ValueError("ENCRYPTION_KEYRING versions must be integers.") from exc
        if version < 1:
            raise ValueError("ENCRYPTION_KEYRING versions must be positive integers.")
        if not key.strip():
            raise ValueError("ENCRYPTION_KEYRING keys must not be empty.")
        parsed[version] = key.strip()
    return parsed


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Customer Support Triage API"
    app_env: str = "local"
    debug: bool = True

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = Field(default="http://localhost:3000")

    database_url: str = "sqlite:///./support_triage.db"
    encryption_key: str | None = None
    encryption_keyring: str | None = None
    frontend_origin: str | None = None
    error_tracking_dsn: str | None = None
    error_tracking_provider: str = "disabled"
    logging_level: str = "INFO"
    service_name: str = "api"
    release_version: str = "0.1.0"
    operations_internal_token: str | None = None
    operations_alert_owner: str = "platform"
    operations_runbook_base_url: str | None = None
    operations_failure_alert_threshold: int = 3
    rate_limit_enabled: bool = True
    rate_limit_default_limit: int = 120
    rate_limit_default_window_seconds: int = 60
    rate_limit_sensitive_limit: int = 10
    rate_limit_sensitive_window_seconds: int = 60
    max_request_body_bytes: int = 1048576
    encryption_key_version: int = 1
    pilot_allowlisted_organization_ids: str | None = None
    pilot_require_allowlist: bool = False
    pilot_sync_enabled: bool = True
    pilot_auto_triage_enabled: bool = True
    pilot_draft_creation_enabled: bool = True
    sync_fallback_interval_minutes: int = 15
    watch_renewal_schedule: str = "0 3 * * *"

    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_secret_key: str | None = None
    supabase_jwks_url: str | None = None
    supabase_jwt_secret: str | None = None
    auth_allow_unverified_jwt: bool = False

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = "http://localhost:8000/v1/gmail/oauth/callback"
    google_cloud_project_id: str | None = None
    google_cloud_region: str = "asia-southeast1"
    google_pubsub_topic: str | None = None
    google_pubsub_subscription: str | None = None
    pubsub_expected_audience: str | None = None
    pubsub_service_account_email: str | None = None

    task_queue_backend: str = "local"
    task_oidc_expected_audience: str | None = None
    task_pubsub_service_account_email: str | None = None
    scheduler_service_account_email: str | None = None
    task_pubsub_gmail_import_topic: str | None = None
    task_pubsub_gmail_history_sync_topic: str | None = None
    task_pubsub_ai_triage_topic: str | None = None
    task_pubsub_watch_renewal_topic: str | None = None

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    ai_triage_daily_gemini_limit: int = 20

    attachment_storage_backend: str = "disabled"
    attachment_storage_bucket: str | None = None
    attachment_signed_url_ttl_seconds: int = 300
    attachment_signing_service_account_email: str | None = None
    attachment_malware_scanning_backend: str = "basic"

    @property
    def encryption_keyring_values(self) -> dict[int, str]:
        return parse_encryption_keyring(self.encryption_keyring)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @property
    def pilot_allowlist(self) -> set[str]:
        raw = self.pilot_allowlisted_organization_ids or ""
        return {item.strip() for item in raw.split(",") if item.strip()}

    @property
    def normalized_app_env(self) -> str:
        return self.app_env.lower().strip()

    @property
    def normalized_error_tracking_provider(self) -> str:
        if self.error_tracking_dsn and self.error_tracking_provider == "disabled":
            return "sentry"
        return self.error_tracking_provider.lower().strip()

    @property
    def normalized_task_queue_backend(self) -> str:
        return self.task_queue_backend.lower().strip()

    @property
    def normalized_attachment_storage_backend(self) -> str:
        return self.attachment_storage_backend.lower().strip()

    @property
    def normalized_attachment_malware_scanning_backend(self) -> str:
        return self.attachment_malware_scanning_backend.lower().strip()

    @property
    def is_production_like(self) -> bool:
        return self.normalized_app_env in {"staging", "production"}

    def validate_runtime_settings(self) -> None:
        """Fail fast for staging/production instead of starting with unsafe defaults."""
        allowed_envs = {"local", "development", "test", "staging", "production"}
        if self.normalized_app_env not in allowed_envs:
            raise RuntimeError(
                "APP_ENV must be one of local, development, test, staging, or production."
            )

        try:
            self.encryption_keyring_values
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

        if self.normalized_error_tracking_provider not in {"disabled", "google-cloud", "sentry"}:
            raise RuntimeError("ERROR_TRACKING_PROVIDER must be disabled, google-cloud, or sentry.")
        if self.normalized_error_tracking_provider == "sentry" and not self.error_tracking_dsn:
            raise RuntimeError("ERROR_TRACKING_DSN is required when ERROR_TRACKING_PROVIDER is sentry.")

        if self.ai_triage_daily_gemini_limit < 0:
            raise RuntimeError("AI_TRIAGE_DAILY_GEMINI_LIMIT must be zero or greater.")

        if self.normalized_task_queue_backend not in {"local", "pubsub"}:
            raise RuntimeError("TASK_QUEUE_BACKEND must be local or pubsub.")
        if self.normalized_attachment_storage_backend not in {"disabled", "gcs"}:
            raise RuntimeError("ATTACHMENT_STORAGE_BACKEND must be disabled or gcs.")
        if self.normalized_attachment_storage_backend == "gcs" and not self.attachment_storage_bucket:
            raise RuntimeError("ATTACHMENT_STORAGE_BUCKET is required when ATTACHMENT_STORAGE_BACKEND is gcs.")
        if self.normalized_attachment_malware_scanning_backend not in {"basic", "disabled"}:
            raise RuntimeError("ATTACHMENT_MALWARE_SCANNING_BACKEND must be basic or disabled.")

        if not self.is_production_like:
            return

        required_values = {
            "DATABASE_URL": self.database_url,
            "ENCRYPTION_KEY": self.encryption_key,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_PUBLISHABLE_KEY": self.supabase_publishable_key,
            "SUPABASE_SECRET_KEY": self.supabase_secret_key,
            "SUPABASE_JWKS_URL or SUPABASE_JWT_SECRET": self.supabase_jwks_url
            or self.supabase_jwt_secret,
            "GOOGLE_CLIENT_ID": self.google_client_id,
            "GOOGLE_CLIENT_SECRET": self.google_client_secret,
            "GOOGLE_REDIRECT_URI": self.google_redirect_uri,
            "GOOGLE_CLOUD_PROJECT_ID": self.google_cloud_project_id,
            "GOOGLE_CLOUD_REGION": self.google_cloud_region,
            "GOOGLE_PUBSUB_TOPIC": self.google_pubsub_topic,
            "GOOGLE_PUBSUB_SUBSCRIPTION": self.google_pubsub_subscription,
            "PUBSUB_EXPECTED_AUDIENCE": self.pubsub_expected_audience,
            "PUBSUB_SERVICE_ACCOUNT_EMAIL": self.pubsub_service_account_email,
            "TASK_QUEUE_BACKEND": self.task_queue_backend,
            "TASK_OIDC_EXPECTED_AUDIENCE": self.task_oidc_expected_audience,
            "TASK_PUBSUB_SERVICE_ACCOUNT_EMAIL": self.task_pubsub_service_account_email,
            "SCHEDULER_SERVICE_ACCOUNT_EMAIL": self.scheduler_service_account_email,
            "TASK_PUBSUB_GMAIL_IMPORT_TOPIC": self.task_pubsub_gmail_import_topic,
            "TASK_PUBSUB_GMAIL_HISTORY_SYNC_TOPIC": self.task_pubsub_gmail_history_sync_topic,
            "TASK_PUBSUB_AI_TRIAGE_TOPIC": self.task_pubsub_ai_triage_topic,
            "TASK_PUBSUB_WATCH_RENEWAL_TOPIC": self.task_pubsub_watch_renewal_topic,
            "GEMINI_API_KEY": self.gemini_api_key,
            "GEMINI_MODEL": self.gemini_model,
            "FRONTEND_ORIGIN": self.frontend_origin,
            "API_CORS_ORIGINS": self.api_cors_origins,
            "SYNC_FALLBACK_INTERVAL_MINUTES": self.sync_fallback_interval_minutes,
            "WATCH_RENEWAL_SCHEDULE": self.watch_renewal_schedule,
            "RELEASE_VERSION": self.release_version,
            "OPERATIONS_ALERT_OWNER": self.operations_alert_owner,
            "RATE_LIMIT_SENSITIVE_LIMIT": self.rate_limit_sensitive_limit,
            "RATE_LIMIT_SENSITIVE_WINDOW_SECONDS": self.rate_limit_sensitive_window_seconds,
            "MAX_REQUEST_BODY_BYTES": self.max_request_body_bytes,
            "ENCRYPTION_KEY_VERSION": self.encryption_key_version,
        }
        missing = [name for name, value in required_values.items() if not value]
        if missing:
            raise RuntimeError(
                "Missing required production settings: " + ", ".join(sorted(missing))
            )

        if self.normalized_task_queue_backend != "pubsub":
            raise RuntimeError("TASK_QUEUE_BACKEND must be pubsub in staging and production.")
        if self.database_url.startswith("sqlite"):
            raise RuntimeError("DATABASE_URL must not use SQLite outside local development.")
        if self.debug:
            raise RuntimeError("DEBUG must be false in staging and production.")
        if self.auth_allow_unverified_jwt:
            raise RuntimeError("AUTH_ALLOW_UNVERIFIED_JWT must be false in staging and production.")
        if "*" in self.cors_origins:
            raise RuntimeError("API_CORS_ORIGINS must not contain '*' in staging or production.")
        if self.encryption_key == "dev-only-change-me":
            raise RuntimeError("ENCRYPTION_KEY must be replaced outside local development.")
        if self.pilot_require_allowlist and not self.pilot_allowlist:
            raise RuntimeError("PILOT_ALLOWLISTED_ORGANIZATION_IDS is required when PILOT_REQUIRE_ALLOWLIST is true.")


settings = Settings()
