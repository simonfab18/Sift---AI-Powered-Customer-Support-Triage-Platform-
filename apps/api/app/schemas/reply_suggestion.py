from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReplySuggestionVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    ticket_id: str
    reply_suggestion_id: str
    version: int
    body: str
    status: str
    created_by_user_id: str | None = None
    created_at: datetime


class ReplySuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    ticket_id: str
    ai_triage_result_id: str | None = None
    gmail_connection_id: str | None = None
    body: str
    edited_body: str | None = None
    status: str
    reply_version: int
    approved_reply_version: int | None = None
    created_by: str
    created_by_user_id: str | None = None
    approved_by_user_id: str | None = None
    approved_at: datetime | None = None
    gmail_draft_id: str | None = None
    created_at: datetime
    updated_at: datetime
    version_history: list[ReplySuggestionVersionRead] = Field(default_factory=list)


class ReplySuggestionCreate(BaseModel):
    body: str = Field(min_length=1)


class ReplySuggestionUpdate(BaseModel):
    edited_body: str = Field(min_length=1)