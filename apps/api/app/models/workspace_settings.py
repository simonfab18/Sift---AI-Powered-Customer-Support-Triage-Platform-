from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class WorkspaceSettings(Base):
    __tablename__ = "workspace_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, unique=True, index=True)
    default_reply_signature: Mapped[str] = mapped_column(Text, nullable=False, default="Best regards,\nCustomer Support Team")
    auto_triage_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    draft_requires_approval: Mapped[bool] = mapped_column(default=True, nullable=False)
    sync_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    draft_creation_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    direct_send_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    pilot_feedback_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    business_hours: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    first_review_target_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=240)
    resolution_target_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
