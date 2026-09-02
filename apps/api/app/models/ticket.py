from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.ticket_attachment import TicketAttachment
    from app.models.ticket_event import TicketEvent


def utc_now() -> datetime:
    return datetime.now(UTC)


class TicketStatus(StrEnum):
    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    DRAFT_CREATED = "draft_created"
    RESOLVED = "resolved"
    SPAM = "spam"


class TicketCategory(StrEnum):
    ORDER_STATUS = "order_status"
    REFUND = "refund"
    RETURN = "return"
    DAMAGED_ITEM = "damaged_item"
    BILLING = "billing"
    TECHNICAL_ISSUE = "technical_issue"
    ACCOUNT_ACCESS = "account_access"
    PRODUCT_QUESTION = "product_question"
    COMPLAINT = "complaint"
    SPAM = "spam"
    OTHER = "other"


class TicketPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TicketSentiment(StrEnum):
    ANGRY = "angry"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"


class TicketTriageStatus(StrEnum):
    NOT_QUEUED = "not_queued"
    QUEUED = "queued"
    TRIAGING = "triaging"
    TRIAGED = "triaged"
    FAILED = "triage_failed"


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (UniqueConstraint("organization_id", "gmail_message_id", name="uq_ticket_org_gmail_message"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    gmail_connection_id: Mapped[str | None] = mapped_column(ForeignKey("gmail_connections.id"), nullable=True, index=True)
    gmail_message_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    message_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default=TicketStatus.NEW.value, index=True)
    category: Mapped[str] = mapped_column(String(60), nullable=False, default=TicketCategory.OTHER.value, index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default=TicketPriority.MEDIUM.value, index=True)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False, default=TicketSentiment.NEUTRAL.value)
    assigned_to_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    triage_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=TicketTriageStatus.NOT_QUEUED.value, index=True
    )
    active_triage_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    triage_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triage_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_triage_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_triage_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_review_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resolution_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    sla_status: Mapped[str] = mapped_column(String(30), nullable=False, default="on_track", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="tickets")
    attachments: Mapped[list["TicketAttachment"]] = relationship(
        "TicketAttachment",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["TicketEvent"]] = relationship(
        "TicketEvent",
        back_populates="ticket",
        cascade="all, delete-orphan",
    )
