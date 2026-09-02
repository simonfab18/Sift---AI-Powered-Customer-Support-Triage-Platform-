from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.gmail_connection import GmailConnection


def utc_now() -> datetime:
    return datetime.now(UTC)


class MailImportRule(Base):
    __tablename__ = "mail_import_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    gmail_connection_id: Mapped[str] = mapped_column(
        ForeignKey("gmail_connections.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    support_label_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    processed_label_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    spam_label_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    import_unread_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    routing_direction: Mapped[str] = mapped_column(String(40), nullable=False, default="shared_queue", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    gmail_connection: Mapped["GmailConnection"] = relationship(
        "GmailConnection",
        back_populates="import_rule",
    )
