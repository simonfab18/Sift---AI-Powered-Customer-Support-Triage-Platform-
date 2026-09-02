from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class GmailSyncEvent(Base):
    __tablename__ = "gmail_sync_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    gmail_connection_id: Mapped[str | None] = mapped_column(
        ForeignKey("gmail_connections.id"), nullable=True, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    pubsub_message_id: Mapped[str | None] = mapped_column(String(160), nullable=True, unique=True, index=True)
    notification_history_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    start_history_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    end_history_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    messages_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tickets_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tickets_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
