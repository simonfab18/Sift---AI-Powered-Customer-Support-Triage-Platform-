from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class JobRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    queue_name: Mapped[str] = mapped_column(String(80), nullable=False, default="default", index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=JobRunStatus.QUEUED.value)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    correlation_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    related_resource_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    related_resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    error_class: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alert_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    runbook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    job_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
