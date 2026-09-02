from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OperationsJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    job_type: str
    queue_name: str
    status: str
    attempts: int
    max_attempts: int
    retryable: bool
    correlation_id: str | None = None
    related_resource_type: str | None = None
    related_resource_id: str | None = None
    error_class: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    next_retry_at: datetime | None = None
    duration_ms: int | None = None
    alert_owner: str | None = None
    runbook_url: str | None = None
    job_metadata: dict
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class OperationsFailureListRead(BaseModel):
    jobs: list[OperationsJobRead]


class OperationsRetryRead(BaseModel):
    original_job: OperationsJobRead
    retry_job: OperationsJobRead


class SyncConnectionHealthRead(BaseModel):
    connection_id: str
    gmail_email: str
    status: str
    sync_status: str | None = None
    watch_status: str | None = None
    consecutive_sync_failures: int
    last_successful_sync_at: datetime | None = None
    last_sync_started_at: datetime | None = None
    sync_error_code: str | None = None
    sync_error_message: str | None = None
    degraded: bool


class SyncHealthRead(BaseModel):
    active_connections: int
    degraded_connections: int
    disconnected_connections: int
    stale_connections: int
    connections: list[SyncConnectionHealthRead]


class StatusDependencyRead(BaseModel):
    status: str
    detail: str | None = None


class ServiceStatusRead(BaseModel):
    service: str
    environment: str
    release_version: str
    status: str
    dependencies: dict[str, StatusDependencyRead]
