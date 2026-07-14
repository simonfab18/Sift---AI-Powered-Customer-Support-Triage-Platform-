from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.ticket import TicketCategory, TicketPriority, TicketSentiment, TicketStatus


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    name: str | None = None


class TicketCreate(BaseModel):
    customer_email: EmailStr
    customer_name: str | None = Field(default=None, max_length=160)
    subject: str = Field(min_length=1, max_length=300)
    message_text: str = Field(min_length=1)
    message_html: str | None = None
    category: TicketCategory = TicketCategory.OTHER
    priority: TicketPriority = TicketPriority.MEDIUM
    sentiment: TicketSentiment = TicketSentiment.NEUTRAL


class TicketUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    message_text: str | None = Field(default=None, min_length=1)
    message_html: str | None = None
    status: TicketStatus | None = None
    category: TicketCategory | None = None
    priority: TicketPriority | None = None
    sentiment: TicketSentiment | None = None


class TicketAssign(BaseModel):
    assigned_to_user_id: str | None = Field(default=None, max_length=120)



class TicketAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    gmail_connection_id: str | None = None
    gmail_message_id: str | None = None
    gmail_attachment_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    content_disposition: str | None = None
    is_inline: bool
    policy_status: str
    storage_status: str
    scan_status: str
    stored_at: datetime | None = None
    notes: str | None = None
    created_at: datetime



class AttachmentDownloadUrlResponse(BaseModel):
    attachment_id: str
    download_url: str
    expires_in_seconds: int


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    customer_id: str
    customer: CustomerRead
    gmail_connection_id: str | None = None
    gmail_connection_email: str | None = None
    gmail_connection_display_name: str | None = None
    gmail_message_id: str | None = None
    gmail_thread_id: str | None = None
    subject: str
    message_text: str
    message_html: str | None = None
    received_at: datetime
    status: str
    category: str
    priority: str
    sentiment: str
    assigned_to_user_id: str | None = None
    triage_status: str
    active_triage_job_id: str | None = None
    triage_error_message: str | None = None
    triage_attempts: int
    last_triage_started_at: datetime | None = None
    last_triage_completed_at: datetime | None = None
    first_review_due_at: datetime | None = None
    resolution_due_at: datetime | None = None
    sla_status: str
    created_at: datetime
    updated_at: datetime
    attachments: list[TicketAttachmentRead] = []


class TicketListItem(BaseModel):
    id: str
    customer_email: str
    customer_name: str | None = None
    gmail_connection_id: str | None = None
    gmail_connection_email: str | None = None
    gmail_connection_display_name: str | None = None
    gmail_message_id: str | None = None
    gmail_thread_id: str | None = None
    subject: str
    status: str
    category: str
    priority: str
    sentiment: str
    assigned_to_user_id: str | None = None
    triage_status: str
    triage_error_message: str | None = None
    first_review_due_at: datetime | None = None
    resolution_due_at: datetime | None = None
    sla_status: str
    received_at: datetime
    updated_at: datetime


class TicketEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    ticket_id: str
    actor_user_id: str | None = None
    event_type: str
    event_metadata: dict
    created_at: datetime
