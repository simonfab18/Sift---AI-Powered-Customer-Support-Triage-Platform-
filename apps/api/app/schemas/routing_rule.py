from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RoutingRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    priority_order: int = Field(default=100, ge=0, le=10000)
    is_active: bool = False
    conditions: dict[str, Any] = Field(default_factory=dict)
    actions: dict[str, Any] = Field(default_factory=dict)


class RoutingRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    priority_order: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None
    conditions: dict[str, Any] | None = None
    actions: dict[str, Any] | None = None


class RoutingRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    name: str
    priority_order: int
    is_active: bool
    conditions: dict[str, Any]
    actions: dict[str, Any]
    created_by_user_id: str
    updated_by_user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class RoutingRuleTestRequest(BaseModel):
    ticket_id: str | None = None
    sample: dict[str, Any] | None = None


class RoutingRuleTestResponse(BaseModel):
    matched: bool
    matched_conditions: list[str]
    actions_preview: dict[str, Any]


class RoutingRuleExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    routing_rule_id: str
    ticket_id: str
    matched: bool
    actions_applied: dict[str, Any]
    created_at: datetime
