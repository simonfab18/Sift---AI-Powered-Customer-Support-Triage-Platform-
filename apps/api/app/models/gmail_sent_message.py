from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class GmailSentMessage(Base):
    __tablename__ = "gmail_sent_messages"
    __table_args__ = (UniqueConstraint("organization_id", "reply_suggestion_id", name="uq_gmail_sent_org_suggestion"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    reply_suggestion_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    gmail_message_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    reply_version: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_by_user_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    test_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
