from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class TicketAttachment(Base):
    __tablename__ = "ticket_attachments"
    __table_args__ = (
        UniqueConstraint("organization_id", "ticket_id", "gmail_attachment_id", name="uq_ticket_attachment_gmail"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    gmail_connection_id: Mapped[str | None] = mapped_column(ForeignKey("gmail_connections.id"), nullable=True, index=True)
    gmail_message_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    gmail_attachment_id: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_disposition: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_inline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    policy_status: Mapped[str] = mapped_column(String(40), nullable=False, default="metadata_only")
    storage_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_downloaded")
    storage_object_name: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    scan_status: Mapped[str] = mapped_column(String(40), nullable=False, default="not_scanned")
    stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    ticket = relationship("Ticket", back_populates="attachments")
