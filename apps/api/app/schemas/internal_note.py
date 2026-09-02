from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InternalNoteCreate(BaseModel):
    body: str = Field(min_length=1)


class InternalNoteUpdate(BaseModel):
    body: str = Field(min_length=1)


class InternalNoteMentionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    note_id: str
    mentioned_user_id: str
    created_at: datetime


class InternalNoteEditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    note_id: str
    edited_by_user_id: str
    previous_body: str
    new_body: str
    version: int
    created_at: datetime


class InternalNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    ticket_id: str
    body: str
    created_by_user_id: str
    updated_by_user_id: str | None = None
    version: int
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
