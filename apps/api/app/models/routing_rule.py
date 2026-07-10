from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class RoutingRule(Base):
    __tablename__ = "routing_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    actions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    updated_by_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class RoutingRuleExecution(Base):
    __tablename__ = "routing_rule_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    routing_rule_id: Mapped[str] = mapped_column(ForeignKey("routing_rules.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actions_applied: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
