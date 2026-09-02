from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.member import MemberRole, MemberStatus


class MemberInvite(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: MemberRole = MemberRole.AGENT


class MemberUpdate(BaseModel):
    role: MemberRole | None = None
    status: MemberStatus | None = None


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    user_id: str
    email: str
    role: str
    status: str
    created_at: datetime
    invite_email_delivery_status: str | None = None
    invite_email_delivery_detail: str | None = None
    invite_url: str | None = None
    ticket_counts: dict[str, int] = Field(default_factory=dict)
