from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str


class UserOrganizationRead(BaseModel):
    id: str
    name: str
    slug: str
    role: str


class OrganizationExportRead(BaseModel):
    organization: dict
    generated_at: str
    generated_by_user_id: str
    counts: dict[str, int]
    workspace_settings: dict | None
    members: list[dict]
    gmail_connections: list[dict]
    customers: list[dict]
    tickets: list[dict]
    attachments: list[dict]
    reply_approvals: list[dict]
    audit_logs: list[dict]


class OrganizationDeletionRequestCreate(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)
    confirm: bool = False


class OrganizationDeletionRequestRead(BaseModel):
    organization_id: str
    status: str
    requested_by_user_id: str
    requested_at: str
    sync_paused: bool
    auto_triage_paused: bool
    draft_creation_paused: bool