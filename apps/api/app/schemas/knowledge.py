from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.knowledge import KnowledgeStatus


class KnowledgeSourceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    source_type: str = Field(default="faq", min_length=1, max_length=60)
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSourceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1)
    source_type: str | None = Field(default=None, min_length=1, max_length=60)
    status: KnowledgeStatus | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    source_metadata: dict[str, Any] | None = None


class KnowledgeSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    title: str
    body: str
    source_type: str
    status: str
    owner_user_id: str
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    source_metadata: dict[str, Any]
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KnowledgeRetrievalSource(BaseModel):
    id: str
    title: str
    source_type: str
    score: int
    matched_terms: list[str]
    excerpt: str


class KnowledgeSearchResponse(BaseModel):
    sources: list[KnowledgeRetrievalSource]


