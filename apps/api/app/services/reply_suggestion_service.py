import base64
from datetime import UTC, datetime
from email.message import EmailMessage

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.core.config import settings
from app.integrations.gmail.client import create_gmail_draft, refresh_gmail_access_token, send_gmail_message
from app.models.ai_triage_result import AITriageResult
from app.models.gmail_connection import GmailConnection
from app.models.gmail_draft import GmailDraft
from app.models.gmail_sent_message import GmailSentMessage
from app.models.reply_suggestion import (
    ReplySuggestion,
    ReplySuggestionCreatedBy,
    ReplySuggestionStatus,
)
from app.models.ticket import TicketStatus
from app.schemas.reply_approval import GmailDirectSendRequest
from app.schemas.reply_suggestion import ReplySuggestionCreate, ReplySuggestionUpdate
from app.services.audit_log_service import create_audit_log
from app.services.collaboration_lock_service import ensure_resource_not_locked_by_other
from app.services.gmail_token_service import refresh_connection_access_token
from app.services.pilot_control_service import ensure_direct_send_enabled, ensure_draft_creation_enabled
from app.services.ticket_service import get_ticket_or_404, write_ticket_event
from app.services.ticket_lifecycle_service import ensure_ticket_allows_direct_send, ensure_ticket_allows_draft, transition_ticket_status



def _expected_reply_subject(subject: str) -> str:
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


def _normalize_confirmation_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.strip().splitlines())

def list_reply_suggestions(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
) -> list[ReplySuggestion]:
    get_ticket_or_404(db, organization_id, ticket_id, actor)
    return list(
        db.scalars(
            select(ReplySuggestion)
            .where(ReplySuggestion.organization_id == organization_id, ReplySuggestion.ticket_id == ticket_id)
            .order_by(ReplySuggestion.created_at.desc())
        )
    )


def create_agent_reply_suggestion(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
    payload: ReplySuggestionCreate,
) -> ReplySuggestion:
    ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
    suggestion = ReplySuggestion(
        organization_id=organization_id,
        ticket_id=ticket.id,
        gmail_connection_id=ticket.gmail_connection_id,
        body=payload.body,
        status=ReplySuggestionStatus.SUGGESTED.value,
        created_by=ReplySuggestionCreatedBy.AGENT.value,
        created_by_user_id=actor.id,
    )
    db.add(suggestion)
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.reply_suggestion_created",
        {"reply_suggestion_id": suggestion.id, "created_by": suggestion.created_by},
    )
    db.commit()
    db.refresh(suggestion)
    return suggestion


def update_reply_suggestion(
    db: Session,
    organization_id: str,
    suggestion_id: str,
    actor: AuthenticatedUser,
    payload: ReplySuggestionUpdate,
) -> ReplySuggestion:
    suggestion = get_reply_suggestion_or_404(db, organization_id, suggestion_id)
    ensure_resource_not_locked_by_other(db, organization_id, actor, "reply_suggestion", suggestion_id)
    ticket = get_ticket_or_404(db, organization_id, suggestion.ticket_id, actor)
    if suggestion.status in {ReplySuggestionStatus.APPROVED.value, ReplySuggestionStatus.REJECTED.value, ReplySuggestionStatus.DRAFT_CREATED.value}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply suggestion is already finalized")

    suggestion.edited_body = payload.edited_body
    suggestion.status = ReplySuggestionStatus.EDITED.value
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.reply_suggestion_edited",
        {"reply_suggestion_id": suggestion.id, "reply_version": suggestion.reply_version},
    )
    db.commit()
    db.refresh(suggestion)
    return suggestion


def approve_reply_suggestion(
    db: Session,
    organization_id: str,
    suggestion_id: str,
    actor: AuthenticatedUser,
) -> ReplySuggestion:
    suggestion = get_reply_suggestion_or_404(db, organization_id, suggestion_id)
    ticket = get_ticket_or_404(db, organization_id, suggestion.ticket_id, actor)
    if suggestion.status == ReplySuggestionStatus.REJECTED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rejected suggestion cannot be approved")
    if suggestion.status == ReplySuggestionStatus.DRAFT_CREATED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply suggestion already has a Gmail draft")

    suggestion.status = ReplySuggestionStatus.APPROVED.value
    suggestion.approved_by_user_id = actor.id
    suggestion.approved_at = datetime.now(UTC)
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.reply_suggestion_approved",
        {"reply_suggestion_id": suggestion.id, "reply_version": suggestion.reply_version},
    )
    create_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="reply_suggestion.approved",
        resource_type="reply_suggestion",
        resource_id=suggestion.id,
        metadata={"ticket_id": suggestion.ticket_id, "ai_triage_result_id": suggestion.ai_triage_result_id, "reply_version": suggestion.reply_version},
    )
    db.commit()
    db.refresh(suggestion)
    return suggestion


def reject_reply_suggestion(
    db: Session,
    organization_id: str,
    suggestion_id: str,
    actor: AuthenticatedUser,
) -> ReplySuggestion:
    suggestion = get_reply_suggestion_or_404(db, organization_id, suggestion_id)
    ticket = get_ticket_or_404(db, organization_id, suggestion.ticket_id, actor)
    if suggestion.status == ReplySuggestionStatus.DRAFT_CREATED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Draft-created suggestion cannot be rejected")

    suggestion.status = ReplySuggestionStatus.REJECTED.value
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.reply_suggestion_rejected",
        {"reply_suggestion_id": suggestion.id, "reply_version": suggestion.reply_version},
    )
    db.commit()
    db.refresh(suggestion)
    return suggestion


async def create_gmail_draft_from_reply_suggestion(
    db: Session,
    organization_id: str,
    suggestion_id: str,
    actor: AuthenticatedUser,
) -> tuple[ReplySuggestion, GmailDraft]:
    suggestion = get_reply_suggestion_or_404(db, organization_id, suggestion_id)
    ticket = get_ticket_or_404(db, organization_id, suggestion.ticket_id, actor)
    ensure_draft_creation_enabled(db, organization_id)
    existing_draft = db.scalar(
        select(GmailDraft).where(GmailDraft.organization_id == organization_id, GmailDraft.ticket_id == ticket.id)
    )
    if existing_draft is not None:
        if suggestion.status != ReplySuggestionStatus.DRAFT_CREATED.value:
            suggestion.status = ReplySuggestionStatus.DRAFT_CREATED.value
            suggestion.gmail_draft_id = existing_draft.gmail_draft_id
            db.commit()
            db.refresh(suggestion)
        return suggestion, existing_draft
    ensure_ticket_allows_draft(ticket)
    if suggestion.status == ReplySuggestionStatus.REJECTED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rejected suggestion cannot create Gmail draft")
    if suggestion.status != ReplySuggestionStatus.APPROVED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply suggestion must be approved first")
    if suggestion.approved_reply_version is not None and suggestion.approved_reply_version != suggestion.reply_version:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply approval is stale and must be approved again")
    if not ticket.gmail_connection_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ticket is not linked to a Gmail connection")

    connection = db.get(GmailConnection, ticket.gmail_connection_id)
    if connection is None or connection.organization_id != organization_id or connection.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Active Gmail connection not found")

    access_token, expires_at = await refresh_connection_access_token(db, connection, refresh_func=refresh_gmail_access_token)
    raw_message = build_reply_raw_message(
        to_email=ticket.customer.email,
        subject=ticket.subject,
        body=suggestion.edited_body or suggestion.body,
    )
    try:
        draft = await create_gmail_draft(access_token, raw_message, ticket.gmail_thread_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gmail draft creation failed; suggestion remains approved",
        ) from exc
    draft_id = draft.get("id")
    if not draft_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail did not return a draft id")

    gmail_draft = GmailDraft(
        organization_id=organization_id,
        ticket_id=ticket.id,
        reply_suggestion_id=suggestion.id,
        gmail_draft_id=draft_id,
        gmail_thread_id=ticket.gmail_thread_id,
        created_by_user_id=actor.id,
    )
    db.add(gmail_draft)
    connection.access_token_expires_at = expires_at
    suggestion.status = ReplySuggestionStatus.DRAFT_CREATED.value
    suggestion.gmail_draft_id = draft_id
    transition_ticket_status(ticket, TicketStatus.DRAFT_CREATED.value)
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.reply_draft_created",
        {"reply_suggestion_id": suggestion.id, "gmail_draft_id": draft_id, "reply_version": suggestion.reply_version},
    )
    create_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="gmail.draft.created",
        resource_type="gmail_draft",
        resource_id=gmail_draft.id,
        metadata={
            "ticket_id": ticket.id,
            "reply_suggestion_id": suggestion.id,
            "gmail_draft_id": draft_id,
            "gmail_thread_id": ticket.gmail_thread_id,
        },
    )
    db.commit()
    db.refresh(suggestion)
    db.refresh(gmail_draft)
    return suggestion, gmail_draft



async def send_approved_reply_suggestion(
    db: Session,
    organization_id: str,
    suggestion_id: str,
    actor: AuthenticatedUser,
    payload: GmailDirectSendRequest,
) -> tuple[ReplySuggestion, GmailSentMessage]:
    ensure_direct_send_enabled(db, organization_id)
    suggestion = get_reply_suggestion_or_404(db, organization_id, suggestion_id)
    ticket = get_ticket_or_404(db, organization_id, suggestion.ticket_id, actor)
    ensure_ticket_allows_direct_send(ticket)

    existing_sent = db.scalar(
        select(GmailSentMessage).where(
            GmailSentMessage.organization_id == organization_id,
            GmailSentMessage.reply_suggestion_id == suggestion.id,
        )
    )
    if existing_sent is not None:
        return suggestion, existing_sent

    if suggestion.status not in {ReplySuggestionStatus.APPROVED.value, ReplySuggestionStatus.DRAFT_CREATED.value}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply suggestion must be approved before sending")
    if suggestion.approved_reply_version is None or suggestion.approved_reply_version != suggestion.reply_version:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply approval is stale and must be approved again")
    if payload.reply_version != suggestion.reply_version:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmed reply version does not match the approved reply")
    if not ticket.gmail_connection_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ticket is not linked to a Gmail connection")

    final_body = suggestion.edited_body or suggestion.body
    expected_subject = _expected_reply_subject(ticket.subject)
    if payload.confirm_recipient_email.strip().lower() != ticket.customer.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmed recipient does not match the ticket customer")
    if payload.confirm_subject.strip() != expected_subject:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmed subject does not match the outgoing reply")
    if _normalize_confirmation_text(payload.confirm_body) != _normalize_confirmation_text(final_body):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmed body does not match the approved reply")

    connection = db.get(GmailConnection, ticket.gmail_connection_id)
    if connection is None or connection.organization_id != organization_id or connection.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Active Gmail connection not found")

    raw_message = build_reply_raw_message(
        to_email=ticket.customer.email,
        subject=ticket.subject,
        body=final_body,
    )
    test_mode = settings.direct_send_test_mode
    if test_mode:
        sent = {"id": f"test-send-{suggestion.id}", "threadId": ticket.gmail_thread_id}
        expires_at = connection.access_token_expires_at
    else:
        access_token, expires_at = await refresh_connection_access_token(db, connection, refresh_func=refresh_gmail_access_token)
        try:
            sent = await send_gmail_message(access_token, raw_message, ticket.gmail_thread_id)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Gmail message send failed; reply remains approved",
            ) from exc

    message_id = sent.get("id")
    if not message_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail did not return a message id")

    sent_message = GmailSentMessage(
        organization_id=organization_id,
        ticket_id=ticket.id,
        reply_suggestion_id=suggestion.id,
        gmail_message_id=message_id,
        gmail_thread_id=sent.get("threadId") or ticket.gmail_thread_id,
        reply_version=suggestion.reply_version,
        sent_by_user_id=actor.id,
        test_mode=test_mode,
    )
    db.add(sent_message)
    db.flush()
    connection.access_token_expires_at = expires_at
    transition_ticket_status(ticket, TicketStatus.RESOLVED.value)
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.reply_sent",
        {"reply_suggestion_id": suggestion.id, "gmail_message_id": message_id, "reply_version": suggestion.reply_version, "test_mode": test_mode},
    )
    create_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="gmail.message.sent",
        resource_type="gmail_sent_message",
        resource_id=sent_message.id,
        metadata={
            "ticket_id": ticket.id,
            "reply_suggestion_id": suggestion.id,
            "gmail_message_id": message_id,
            "gmail_thread_id": sent_message.gmail_thread_id,
            "reply_version": suggestion.reply_version,
            "test_mode": test_mode,
        },
    )
    db.commit()
    db.refresh(suggestion)
    db.refresh(sent_message)
    return suggestion, sent_message

def build_reply_raw_message(to_email: str, subject: str, body: str) -> str:
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")


def create_ai_reply_suggestion_from_triage(
    db: Session,
    ticket_id: str,
    result: AITriageResult,
    gmail_connection_id: str | None,
) -> ReplySuggestion:
    suggestion = ReplySuggestion(
        organization_id=result.organization_id,
        ticket_id=ticket_id,
        ai_triage_result_id=result.id,
        gmail_connection_id=gmail_connection_id,
        body=result.draft_reply,
        status=ReplySuggestionStatus.SUGGESTED.value,
        created_by=ReplySuggestionCreatedBy.AI.value,
    )
    db.add(suggestion)
    return suggestion


def get_reply_suggestion_or_404(db: Session, organization_id: str, suggestion_id: str) -> ReplySuggestion:
    suggestion = db.get(ReplySuggestion, suggestion_id)
    if suggestion is None or suggestion.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply suggestion not found")
    return suggestion
