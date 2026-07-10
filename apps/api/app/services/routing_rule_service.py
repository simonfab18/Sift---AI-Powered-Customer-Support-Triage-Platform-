from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.customer import Customer
from app.models.member import MemberRole, MemberStatus, OrganizationMember
from app.models.routing_rule import RoutingRule, RoutingRuleExecution
from app.models.ticket import Ticket, TicketPriority, TicketStatus
from app.schemas.routing_rule import RoutingRuleCreate, RoutingRuleTestRequest, RoutingRuleUpdate
from app.services.rbac_service import require_membership, require_role
from app.services.ticket_lifecycle_service import transition_ticket_status

PRIORITY_RANK = {
    TicketPriority.LOW.value: 1,
    TicketPriority.MEDIUM.value: 2,
    TicketPriority.HIGH.value: 3,
    TicketPriority.CRITICAL.value: 4,
}


def list_routing_rules(db: Session, organization_id: str, actor: AuthenticatedUser) -> list[RoutingRule]:
    require_membership(db, organization_id, actor)
    return list(
        db.scalars(
            select(RoutingRule)
            .where(RoutingRule.organization_id == organization_id)
            .order_by(RoutingRule.priority_order.asc(), RoutingRule.created_at.asc())
        )
    )


def create_routing_rule(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    payload: RoutingRuleCreate,
) -> RoutingRule:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    rule = RoutingRule(
        organization_id=organization_id,
        name=payload.name,
        priority_order=payload.priority_order,
        is_active=payload.is_active,
        conditions=payload.conditions,
        actions=payload.actions,
        created_by_user_id=actor.id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_routing_rule(
    db: Session,
    organization_id: str,
    rule_id: str,
    actor: AuthenticatedUser,
    payload: RoutingRuleUpdate,
) -> RoutingRule:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    rule = db.get(RoutingRule, rule_id)
    if rule is None or rule.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing rule not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    rule.updated_by_user_id = actor.id
    db.commit()
    db.refresh(rule)
    return rule


def _ticket_sample(db: Session, ticket: Ticket) -> dict[str, Any]:
    customer = db.get(Customer, ticket.customer_id)
    customer_email = customer.email if customer else ""
    sender_domain = customer_email.split("@")[-1].lower() if "@" in customer_email else ""
    return {
        "ticket_id": ticket.id,
        "category": ticket.category,
        "priority": ticket.priority,
        "sentiment": ticket.sentiment,
        "subject": ticket.subject,
        "message_text": ticket.message_text,
        "customer_email": customer_email,
        "sender_domain": sender_domain,
        "gmail_connection_id": ticket.gmail_connection_id,
        "gmail_message_id": ticket.gmail_message_id,
    }


def _matches_value(expected: Any, actual: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, list):
        return str(actual).lower() in {str(item).lower() for item in expected}
    return str(actual).lower() == str(expected).lower()


def evaluate_routing_rule(rule: RoutingRule, sample: dict[str, Any]) -> tuple[bool, list[str]]:
    conditions = rule.conditions or {}
    matched: list[str] = []

    checks = {
        "category": sample.get("category"),
        "priority": sample.get("priority"),
        "sentiment": sample.get("sentiment"),
        "sender_domain": sample.get("sender_domain"),
        "customer_email": sample.get("customer_email"),
        "gmail_label": sample.get("gmail_label"),
    }
    for key, actual in checks.items():
        if key in conditions:
            if not _matches_value(conditions[key], actual):
                return False, matched
            matched.append(key)

    keyword = conditions.get("keyword")
    if keyword:
        haystack = f"{sample.get('subject', '')} {sample.get('message_text', '')}".lower()
        keywords = keyword if isinstance(keyword, list) else [keyword]
        if not any(str(item).lower() in haystack for item in keywords):
            return False, matched
        matched.append("keyword")

    business_hours = conditions.get("business_hours")
    if business_hours is not None:
        now = sample.get("now")
        if not isinstance(now, datetime):
            now = datetime.now()
        is_business_hour = 9 <= now.hour < 17 and now.weekday() < 5
        if bool(business_hours) != is_business_hour:
            return False, matched
        matched.append("business_hours")

    return True, matched


def _active_member_exists(db: Session, organization_id: str, user_id: str) -> bool:
    return (
        db.scalar(
            select(OrganizationMember.id).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.status == MemberStatus.ACTIVE.value,
            )
        )
        is not None
    )


def _apply_actions(db: Session, rule: RoutingRule, ticket: Ticket) -> dict[str, Any]:
    actions = rule.actions or {}
    applied: dict[str, Any] = {}

    assignee = actions.get("assign_user_id") or actions.get("assign_agent_id")
    if assignee and _active_member_exists(db, ticket.organization_id, str(assignee)):
        ticket.assigned_to_user_id = str(assignee)
        applied["assigned_to_user_id"] = str(assignee)

    priority_floor = actions.get("priority_floor")
    if priority_floor in PRIORITY_RANK and PRIORITY_RANK[priority_floor] > PRIORITY_RANK.get(ticket.priority, 0):
        ticket.priority = priority_floor
        applied["priority_floor"] = priority_floor

    if actions.get("require_approval"):
        if ticket.status in {TicketStatus.NEW.value, TicketStatus.OPEN.value, TicketStatus.PENDING.value}:
            transition_ticket_status(ticket, TicketStatus.AWAITING_APPROVAL.value)
        applied["require_approval"] = True

    for record_only_key in ["add_tag", "notify_role", "notify_user_id"]:
        if record_only_key in actions:
            applied[record_only_key] = actions[record_only_key]

    return applied


def test_routing_rule(
    db: Session,
    organization_id: str,
    rule_id: str,
    actor: AuthenticatedUser,
    payload: RoutingRuleTestRequest,
) -> dict[str, Any]:
    require_membership(db, organization_id, actor)
    rule = db.get(RoutingRule, rule_id)
    if rule is None or rule.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing rule not found")

    if payload.ticket_id:
        ticket = db.get(Ticket, payload.ticket_id)
        if ticket is None or ticket.organization_id != organization_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
        sample = _ticket_sample(db, ticket)
    else:
        sample = payload.sample or {}
    matched, matched_conditions = evaluate_routing_rule(rule, sample)
    return {"matched": matched, "matched_conditions": matched_conditions, "actions_preview": rule.actions if matched else {}}


def apply_routing_rules(db: Session, ticket: Ticket) -> list[RoutingRuleExecution]:
    rules = db.scalars(
        select(RoutingRule)
        .where(RoutingRule.organization_id == ticket.organization_id, RoutingRule.is_active.is_(True))
        .order_by(RoutingRule.priority_order.asc(), RoutingRule.created_at.asc())
    ).all()
    sample = _ticket_sample(db, ticket)
    executions: list[RoutingRuleExecution] = []
    for rule in rules:
        matched, _ = evaluate_routing_rule(rule, sample)
        actions_applied = _apply_actions(db, rule, ticket) if matched else {}
        execution = RoutingRuleExecution(
            organization_id=ticket.organization_id,
            routing_rule_id=rule.id,
            ticket_id=ticket.id,
            matched=matched,
            actions_applied=actions_applied,
        )
        db.add(execution)
        executions.append(execution)
    return executions


def list_routing_rule_executions(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
) -> list[RoutingRuleExecution]:
    require_membership(db, organization_id, actor)
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return list(
        db.scalars(
            select(RoutingRuleExecution)
            .where(RoutingRuleExecution.organization_id == organization_id, RoutingRuleExecution.ticket_id == ticket_id)
            .order_by(RoutingRuleExecution.created_at.asc())
        )
    )
