from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.mail_import_rule import MailImportRule


def utc_now() -> datetime:
    return datetime.now(UTC)


class GmailConnection(Base):
    __tablename__ = "gmail_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    connected_by_user_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    gmail_email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    inbox_type: Mapped[str] = mapped_column(String(40), nullable=False, default="individual", index=True)
    shared_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    channel_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_account_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    encrypted_refresh_token: Mapped[str] = mapped_column(String(2048), nullable=False)
    token_key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reauthorization_required_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reauthorization_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_token_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scopes: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmail_history_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    watch_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_notification_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(40), nullable=False, default="disconnected", index=True)
    sync_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sync_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_sync_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    watch_status: Mapped[str] = mapped_column(String(40), nullable=False, default="disconnected", index=True)
    watch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_lock_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sync_lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    import_rule: Mapped["MailImportRule | None"] = relationship(
        "MailImportRule",
        back_populates="gmail_connection",
        cascade="all, delete-orphan",
    )
