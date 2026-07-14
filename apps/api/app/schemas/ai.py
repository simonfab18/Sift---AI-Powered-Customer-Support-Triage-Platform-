from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.ticket import TicketCategory, TicketPriority, TicketSentiment


class TriageOutput(BaseModel):
    category: TicketCategory
    priority: TicketPriority
    sentiment: TicketSentiment
    summary: str = Field(min_length=1)
    suggested_action: str = Field(min_length=1)
    draft_reply: str = Field(min_length=1)
    confidence_score: int = Field(ge=0, le=100)
    reasoning: str = Field(min_length=1)
    requires_human_review: bool


class AITriageResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    ticket_id: str
    model_provider: str
    model_name: str
    prompt_version: str
    schema_version: str
    latency_ms: int | None = None
    job_run_id: str | None = None
    category: str
    priority: str
    sentiment: str
    summary: str
    suggested_action: str
    draft_reply: str
    confidence_score: int
    reasoning: str
    requires_human_review: bool
    validation_status: str
    knowledge_sources: list[dict] = []
    created_at: datetime


class AITriageJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    job_type: str
    status: str
    error_message: str | None = None
    job_metadata: dict
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

class AITriageInboxUsageRead(BaseModel):
    gmail_connection_id: str | None = None
    gmail_email: str | None = None
    used: int


class AITriageUsageRead(BaseModel):
    date: str
    timezone: str = "UTC"
    daily_limit: int
    used: int
    remaining: int | None = None
    paused_for_today: bool
    resets_at: datetime
    per_inbox: list[AITriageInboxUsageRead]
