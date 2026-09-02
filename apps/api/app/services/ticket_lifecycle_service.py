from fastapi import HTTPException, status

from app.models.ticket import Ticket, TicketStatus

TERMINAL_STATUSES = {TicketStatus.RESOLVED.value, TicketStatus.SPAM.value}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    TicketStatus.NEW.value: {
        TicketStatus.OPEN.value,
        TicketStatus.PENDING.value,
        TicketStatus.AWAITING_APPROVAL.value,
        TicketStatus.DRAFT_CREATED.value,
        TicketStatus.RESOLVED.value,
        TicketStatus.SPAM.value,
    },
    TicketStatus.OPEN.value: {
        TicketStatus.PENDING.value,
        TicketStatus.AWAITING_APPROVAL.value,
        TicketStatus.DRAFT_CREATED.value,
        TicketStatus.RESOLVED.value,
        TicketStatus.SPAM.value,
    },
    TicketStatus.PENDING.value: {
        TicketStatus.OPEN.value,
        TicketStatus.AWAITING_APPROVAL.value,
        TicketStatus.DRAFT_CREATED.value,
        TicketStatus.RESOLVED.value,
        TicketStatus.SPAM.value,
    },
    TicketStatus.AWAITING_APPROVAL.value: {
        TicketStatus.OPEN.value,
        TicketStatus.PENDING.value,
        TicketStatus.DRAFT_CREATED.value,
        TicketStatus.RESOLVED.value,
        TicketStatus.SPAM.value,
    },
    TicketStatus.DRAFT_CREATED.value: {
        TicketStatus.PENDING.value,
        TicketStatus.RESOLVED.value,
        TicketStatus.SPAM.value,
    },
    TicketStatus.RESOLVED.value: set(),
    TicketStatus.SPAM.value: set(),
}


def transition_ticket_status(ticket: Ticket, next_status: str) -> None:
    if ticket.status == next_status:
        return
    if next_status not in {status.value for status in TicketStatus}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ticket status")
    allowed = ALLOWED_TRANSITIONS.get(ticket.status, set())
    if next_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ticket cannot move from {ticket.status} to {next_status}",
        )
    ticket.status = next_status


def ensure_ticket_allows_draft(ticket: Ticket) -> None:
    if ticket.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Closed tickets cannot create Gmail drafts")

def ensure_ticket_allows_direct_send(ticket: Ticket) -> None:
    if ticket.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Closed tickets cannot send Gmail replies")
