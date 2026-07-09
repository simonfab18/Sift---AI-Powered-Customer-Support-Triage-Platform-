from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CollaborationLockAcquire(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=36)
    resource_type: str = Field(default="reply_suggestion", min_length=1, max_length=40)
    resource_id: str = Field(min_length=1, max_length=36)
    mode: str = Field(default="edit", min_length=1, max_length=20)
    ttl_seconds: int = Field(default=120, ge=30, le=900)


class CollaborationLockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    ticket_id: str
    resource_type: str
    resource_id: str
    locked_by_user_id: str
    mode: str
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
