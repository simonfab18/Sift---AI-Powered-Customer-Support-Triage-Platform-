from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class KnowledgeStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False, default="faq")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=KnowledgeStatus.ACTIVE.value, index=True)
    owner_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class KnowledgeUsageEvent(Base):
    __tablename__ = "knowledge_usage_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    knowledge_source_id: Mapped[str] = mapped_column(ForeignKey("knowledge_sources.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    ai_triage_result_id: Mapped[str | None] = mapped_column(ForeignKey("ai_triage_results.id"), nullable=True, index=True)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    score: Mapped[int] = mapped_column(nullable=False, default=0)
    matched_terms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

