from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GmailSyncRequest(BaseModel):
    max_results: int = Field(default=20, ge=1, le=100)


class JobRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    job_type: str
    queue_name: str = "default"
    status: str
    attempts: int = 0
    max_attempts: int = 3
    retryable: bool = False
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
