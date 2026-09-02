from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.reply_suggestion import ReplySuggestionRead


class ResponseTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1)
    category_tags: list[str] = Field(default_factory=list)


class ResponseTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    body: str | None = Field(default=None, min_length=1)
    category_tags: list[str] | None = None
    archived: bool | None = None


class ResponseTemplateInsert(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=36)


class ResponseTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    body: str
    category_tags: list[str]
    created_by_user_id: str
    updated_by_user_id: str | None = None
    version: int
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TemplateInsertResult(BaseModel):
    template: ResponseTemplateRead
    suggestion: ReplySuggestionRead
