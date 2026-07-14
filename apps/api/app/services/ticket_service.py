from fastapi import HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import AuthenticatedUser
from app.models.customer import Customer
from app.models.gmail_connection import GmailConnection
from app.models.member import MemberStatus, OrganizationMember
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketStatus
from app.models.ticket_event import TicketEvent
from app.schemas.ticket import TicketAssign, TicketCreate, TicketListItem, TicketUpdate
from app.services.rbac_service import require_membership
from app.services.routing_rule_service import apply_routing_rules
from app.services.sla_service import initialize_ticket_sla, refresh_ticket_sla_status
from app.services.workspace_settings_service import get_or_create_workspace_settings
from app.services.ticket_lifecycle_service import transition_ticket_status


def write_ticket_event(
    db: Session,
    ticket: Ticket,
    actor: AuthenticatedUser,
    event_type: str,
    metadata: dict | None = None,
) -> TicketEvent:
    event = TicketEvent(
        organization_id=ticket.organization_id,
        ticket_id=ticket.id,
        actor_user_id=actor.id,
        event_type=event_type,
        event_metadata=metadata or {},
    )
    db.add(event)
    return event


def get_or_create_customer(
    db: Session,
    organization_id: str,
    email: str,
    name: str | None,
) -> Customer:
    normalized_email = email.strip().lower()
    customer = db.scalar(
        select(Customer).where(
            Customer.organization_id == organization_id,
            Customer.email == normalized_email,
        )
    )
    if customer is not None:
        if name and customer.name != name:
            customer.name = name
        return customer

    customer = Customer(organization_id=organization_id, email=normalized_email, name=name)
    db.add(customer)
    db.flush()
    return customer


def create_ticket(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    payload: TicketCreate,
) -> Ticket:
    require_membership(db, organization_id, actor)
    customer = get_or_create_customer(
        db,
        organization_id,
        str(payload.customer_email),
        payload.customer_name,
    )
    ticket = Ticket(
        organization_id=organization_id,
        customer_id=customer.id,
        subject=payload.subject,
        message_text=payload.message_text,
        message_html=payload.message_html,
        category=payload.category.value,
        priority=payload.priority.value,
        sentiment=payload.sentiment.value,
    )
    db.add(ticket)
    db.flush()
    settings = get_or_create_workspace_settings(db, organization_id)
    initialize_ticket_sla(ticket, settings)
    apply_routing_rules(db, ticket)
    write_ticket_event(db, ticket, actor, "ticket.created", {"source": "manual"})
    db.commit()
    try:
        from app.services.job_queue_service import enqueue_ticket_triage

        enqueue_ticket_triage(db, organization_id, ticket.id, actor, raise_on_enqueue_error=False)
    except Exception:
        pass
    return get_ticket_or_404(db, organization_id, ticket.id, actor)


def list_tickets(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    status_filter: str | None = None,
    priority_filter: str | None = None,
    sla_status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    gmail_connection_id_filter: str | None = None,
    gmail_inbox_type_filter: str | None = None,
) -> list[TicketListItem]:
    require_membership(db, organization_id, actor)
    priority_rank = case(
        (Ticket.priority == TicketPriority.CRITICAL.value, 0),
        (Ticket.priority == TicketPriority.HIGH.value, 1),
        (Ticket.priority == TicketPriority.MEDIUM.value, 2),
        (Ticket.priority == TicketPriority.LOW.value, 3),
        else_=4,
    )
    statement = (
        select(Ticket)
        .options(selectinload(Ticket.customer), selectinload(Ticket.attachments))
        .where(Ticket.organization_id == organization_id)
        .order_by(priority_rank.asc(), Ticket.received_at.desc(), Ticket.id.asc())
    )
    if status_filter and status_filter != "all":
        statement = statement.where(Ticket.status == status_filter)
    elif status_filter != "all":
        statement = statement.where(Ticket.status.notin_([TicketStatus.RESOLVED.value, TicketStatus.SPAM.value]))
    if priority_filter:
        statement = statement.where(Ticket.priority == priority_filter)
    if sla_status_filter:
        statement = statement.where(Ticket.sla_status == sla_status_filter)
    if gmail_connection_id_filter:
        statement = statement.where(Ticket.gmail_connection_id == gmail_connection_id_filter)
    if gmail_inbox_type_filter and gmail_inbox_type_filter != "all":
        statement = statement.join(GmailConnection, Ticket.gmail_connection_id == GmailConnection.id).where(
            GmailConnection.organization_id == organization_id,
            GmailConnection.inbox_type == gmail_inbox_type_filter,
        )

    tickets = db.scalars(statement.limit(limit).offset(offset)).all()
    connection_ids = {ticket.gmail_connection_id for ticket in tickets if ticket.gmail_connection_id}
    connections = {}
    if connection_ids:
        connections = {
            connection.id: connection
            for connection in db.scalars(
                select(GmailConnection).where(
                    GmailConnection.organization_id == organization_id,
                    GmailConnection.id.in_(connection_ids),
                )
            )
        }
    return [
        TicketListItem(
            id=ticket.id,
            customer_email=ticket.customer.email,
            customer_name=ticket.customer.name,
            gmail_connection_id=ticket.gmail_connection_id,
            gmail_connection_email=connections[ticket.gmail_connection_id].gmail_email if ticket.gmail_connection_id in connections else None,
            gmail_connection_display_name=connections[ticket.gmail_connection_id].display_name if ticket.gmail_connection_id in connections else None,
            gmail_connection_inbox_type=connections[ticket.gmail_connection_id].inbox_type if ticket.gmail_connection_id in connections else None,
            gmail_connection_shared_address=connections[ticket.gmail_connection_id].shared_address if ticket.gmail_connection_id in connections else None,
            gmail_message_id=ticket.gmail_message_id,
            gmail_thread_id=ticket.gmail_thread_id,
            subject=ticket.subject,
            status=ticket.status,
            category=ticket.category,
            priority=ticket.priority,
            sentiment=ticket.sentiment,
            assigned_to_user_id=ticket.assigned_to_user_id,
            triage_status=ticket.triage_status,
            triage_error_message=ticket.triage_error_message,
            first_review_due_at=ticket.first_review_due_at,
            resolution_due_at=ticket.resolution_due_at,
            sla_status=refresh_ticket_sla_status(ticket),
            received_at=ticket.received_at,
            updated_at=ticket.updated_at,
        )
        for ticket in tickets
    ]


def get_ticket_or_404(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
) -> Ticket:
    require_membership(db, organization_id, actor)
    ticket = db.scalar(
        select(Ticket)
        .options(selectinload(Ticket.customer), selectinload(Ticket.attachments))
        .where(Ticket.organization_id == organization_id, Ticket.id == ticket_id)
    )
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


def update_ticket(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
    payload: TicketUpdate,
) -> Ticket:
    ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
    changes: dict[str, dict[str, str | None]] = {}
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        next_value = value.value if hasattr(value, "value") else value
        previous_value = getattr(ticket, field)
        if previous_value != next_value:
            changes[field] = {"from": previous_value, "to": next_value}
            if field == "status":
                transition_ticket_status(ticket, next_value)
            else:
                setattr(ticket, field, next_value)

    if changes:
        write_ticket_event(db, ticket, actor, "ticket.updated", {"changes": changes})
    refresh_ticket_sla_status(ticket)
    db.commit()
    return get_ticket_or_404(db, organization_id, ticket_id, actor)


def assign_ticket(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
    payload: TicketAssign,
) -> Ticket:
    ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
    assigned_to_user_id = payload.assigned_to_user_id

    if assigned_to_user_id is not None:
        assignee = db.scalar(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == assigned_to_user_id,
                OrganizationMember.status == MemberStatus.ACTIVE.value,
            )
        )
        if assignee is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee is not an active member")

    previous_assignee = ticket.assigned_to_user_id
    ticket.assigned_to_user_id = assigned_to_user_id
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.assigned",
        {"from": previous_assignee, "to": assigned_to_user_id},
    )
    db.commit()
    return get_ticket_or_404(db, organization_id, ticket_id, actor)


def mark_ticket_spam(db: Session, organization_id: str, ticket_id: str, actor: AuthenticatedUser) -> Ticket:
    ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
    previous_status = ticket.status
    transition_ticket_status(ticket, TicketStatus.SPAM.value)
    ticket.category = TicketCategory.SPAM.value
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.marked_spam",
        {"previous_status": previous_status},
    )
    db.commit()
    return get_ticket_or_404(db, organization_id, ticket_id, actor)


def resolve_ticket(db: Session, organization_id: str, ticket_id: str, actor: AuthenticatedUser) -> Ticket:
    ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
    previous_status = ticket.status
    transition_ticket_status(ticket, TicketStatus.RESOLVED.value)
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.resolved",
        {"previous_status": previous_status},
    )
    db.commit()
    return get_ticket_or_404(db, organization_id, ticket_id, actor)


def list_ticket_events(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
) -> list[TicketEvent]:
    get_ticket_or_404(db, organization_id, ticket_id, actor)
    return list(
        db.scalars(
            select(TicketEvent)
            .where(TicketEvent.organization_id == organization_id, TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.created_at.asc())
        )
    )
