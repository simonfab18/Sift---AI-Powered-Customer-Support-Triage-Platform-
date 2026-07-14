from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class GmailOAuthStartRead(BaseModel):
    auth_url: str
    state: str


class GmailOAuthCallbackRead(BaseModel):
    connection_id: str
    gmail_email: str
    status: str


class GmailConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    connected_by_user_id: str
    gmail_email: str
    display_name: str | None = None
    inbox_type: str = "individual"
    shared_address: str | None = None
    channel_notes: str | None = None
    google_account_id: str
    scopes: str
    token_key_version: int
    reauthorization_required_at: datetime | None = None
    reauthorization_reason: str | None = None
    last_token_error_at: datetime | None = None
    status: str
    last_sync_at: datetime | None = None
    gmail_history_id: str | None = None
    watch_expires_at: datetime | None = None
    last_notification_at: datetime | None = None
    last_sync_started_at: datetime | None = None
    last_successful_sync_at: datetime | None = None
    sync_status: str
    sync_error_code: str | None = None
    sync_error_message: str | None = None
    consecutive_sync_failures: int
    watch_status: str
    watch_error: str | None = None
    disconnected_at: datetime | None = None
    sync_lock_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class GmailConnectionUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    inbox_type: Literal["individual", "google_group", "shared_mailbox"] | None = None
    shared_address: EmailStr | None = None
    channel_notes: str | None = Field(default=None, max_length=500)

    @field_validator("display_name", "channel_notes", mode="before")
    @classmethod
    def blank_string_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class GmailSyncEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    gmail_connection_id: str | None = None
    trigger_type: str
    status: str
    pubsub_message_id: str | None = None
    notification_history_id: str | None = None
    start_history_id: str | None = None
    end_history_id: str | None = None
    messages_seen: int
    messages_imported: int
    messages_skipped: int
    tickets_created: int
    tickets_updated: int
    duration_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    sync_metadata: dict[str, Any]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class GmailWatchActionRead(BaseModel):
    connection: GmailConnectionRead
    event: GmailSyncEventRead

class GmailSyncStatusRead(BaseModel):
    connection: GmailConnectionRead
    recent_events: list[GmailSyncEventRead]


class GmailHistorySyncQueueRead(BaseModel):
    event: GmailSyncEventRead

class MailImportRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    gmail_connection_id: str
    support_label_id: str | None = None
    processed_label_id: str | None = None
    spam_label_id: str | None = None
    import_unread_only: bool
    routing_direction: str
    is_active: bool
    created_at: datetime


class MailImportRuleUpdate(BaseModel):
    support_label_id: str | None = None
    processed_label_id: str | None = None
    spam_label_id: str | None = None
    import_unread_only: bool | None = None
    routing_direction: Literal["shared_queue", "priority_queue", "specialist_queue"] | None = None
    is_active: bool | None = None


class GmailWebhookAcceptedRead(BaseModel):
    status: str
