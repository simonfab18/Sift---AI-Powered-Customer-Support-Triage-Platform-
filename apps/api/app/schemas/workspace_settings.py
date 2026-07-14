from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    default_reply_signature: str
    auto_triage_enabled: bool
    draft_requires_approval: bool
    sync_enabled: bool
    draft_creation_enabled: bool
    direct_send_enabled: bool
    attachment_ai_processing_enabled: bool
    pilot_feedback_contact: str | None
    business_timezone: str
    business_hours: dict
    first_review_target_minutes: int
    resolution_target_minutes: int
    created_at: datetime
    updated_at: datetime


class WorkspaceSettingsUpdate(BaseModel):
    default_reply_signature: str | None = Field(default=None, min_length=1)
    auto_triage_enabled: bool | None = None
    draft_requires_approval: bool | None = None
    sync_enabled: bool | None = None
    draft_creation_enabled: bool | None = None
    direct_send_enabled: bool | None = None
    attachment_ai_processing_enabled: bool | None = None
    pilot_feedback_contact: str | None = Field(default=None, max_length=255)
    business_timezone: str | None = Field(default=None, max_length=80)
    business_hours: dict | None = None
    first_review_target_minutes: int | None = Field(default=None, ge=1)
    resolution_target_minutes: int | None = Field(default=None, ge=1)
