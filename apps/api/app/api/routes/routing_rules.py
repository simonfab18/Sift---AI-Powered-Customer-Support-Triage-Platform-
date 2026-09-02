from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.routing_rule import (
    RoutingRuleCreate,
    RoutingRuleExecutionRead,
    RoutingRuleRead,
    RoutingRuleTestRequest,
    RoutingRuleTestResponse,
    RoutingRuleUpdate,
)
from app.services.routing_rule_service import (
    create_routing_rule,
    list_routing_rule_executions,
    list_routing_rules,
    test_routing_rule,
    update_routing_rule,
)

router = APIRouter(prefix="/orgs/{organization_id}/routing-rules", tags=["routing-rules"])


@router.get("", response_model=list[RoutingRuleRead])
def read_routing_rules(organization_id: str, db: DbSession, current_user: CurrentUser):
    return list_routing_rules(db, organization_id, current_user)


@router.post("", response_model=RoutingRuleRead, status_code=status.HTTP_201_CREATED)
def create_org_routing_rule(
    organization_id: str,
    payload: RoutingRuleCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    return create_routing_rule(db, organization_id, current_user, payload)


@router.patch("/{rule_id}", response_model=RoutingRuleRead)
def update_org_routing_rule(
    organization_id: str,
    rule_id: str,
    payload: RoutingRuleUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return update_routing_rule(db, organization_id, rule_id, current_user, payload)


@router.post("/{rule_id}/test", response_model=RoutingRuleTestResponse)
def test_org_routing_rule(
    organization_id: str,
    rule_id: str,
    payload: RoutingRuleTestRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    return test_routing_rule(db, organization_id, rule_id, current_user, payload)


@router.get("/tickets/{ticket_id}/executions", response_model=list[RoutingRuleExecutionRead])
def read_ticket_routing_executions(
    organization_id: str,
    ticket_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return list_routing_rule_executions(db, organization_id, ticket_id, current_user)
