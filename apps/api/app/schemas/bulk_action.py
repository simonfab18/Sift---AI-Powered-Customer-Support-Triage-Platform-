from pydantic import BaseModel, Field

from app.models.ticket import TicketStatus
from app.schemas.ticket import TicketRead


class TicketBulkActionRequest(BaseModel):
    ticket_ids: list[str] = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=40)
    assigned_to_user_id: str | None = Field(default=None, max_length=120)
    status: TicketStatus | None = None
    confirm: bool = False


class TicketBulkActionItemResult(BaseModel):
    ticket_id: str
    success: bool
    ticket: TicketRead | None = None
    error: str | None = None


class TicketBulkActionResponse(BaseModel):
    action: str
    results: list[TicketBulkActionItemResult]
