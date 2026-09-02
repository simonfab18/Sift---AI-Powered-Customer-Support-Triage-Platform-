from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SavedViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    filters: dict[str, Any] = Field(default_factory=dict)


class SavedViewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    filters: dict[str, Any] | None = None


class SavedViewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    user_id: str
    name: str
    filters: dict[str, Any]
    created_at: datetime
    updated_at: datetime
