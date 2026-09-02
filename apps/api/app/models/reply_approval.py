from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ReplyApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DRAFT_CREATED = "draft_created"


class ReplyApproval(Base):
    __tablename__ = "reply_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    ai_triage_result_id: Mapped[str] = mapped_column(ForeignKey("ai_triage_results.id"), nullable=False, index=True)
    gmail_connection_id: Mapped[str | None] = mapped_column(ForeignKey("gmail_connections.id"), nullable=True, index=True)
    suggested_reply: Mapped[str] = mapped_column(Text, nullable=False)
    final_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ReplyApprovalStatus.PENDING.value, index=True)
    reply_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approved_reply_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmail_draft_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
