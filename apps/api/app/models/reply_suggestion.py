from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ReplySuggestionStatus(StrEnum):
    SUGGESTED = "suggested"
    EDITED = "edited"
    APPROVED = "approved"
    REJECTED = "rejected"
    DRAFT_CREATED = "draft_created"


class ReplySuggestionCreatedBy(StrEnum):
    AI = "ai"
    AGENT = "agent"


class ReplySuggestionVersion(Base):
    __tablename__ = "reply_suggestion_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    reply_suggestion_id: Mapped[str] = mapped_column(ForeignKey("reply_suggestions.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class ReplySuggestion(Base):
    __tablename__ = "reply_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    ai_triage_result_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_triage_results.id"),
        nullable=True,
        index=True,
    )
    gmail_connection_id: Mapped[str | None] = mapped_column(ForeignKey("gmail_connections.id"), nullable=True, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default=ReplySuggestionStatus.SUGGESTED.value, index=True)
    reply_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    approved_reply_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String(20), nullable=False, default=ReplySuggestionCreatedBy.AI.value)
    created_by_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gmail_draft_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    version_history: Mapped[list[ReplySuggestionVersion]] = relationship("ReplySuggestionVersion", order_by="ReplySuggestionVersion.version", lazy="selectin")