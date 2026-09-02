import base64
from datetime import UTC, datetime
from email.message import EmailMessage

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.integrations.gmail.client import create_gmail_draft, refresh_gmail_access_token
from app.models.ai_triage_result import AITriageResult
from app.models.gmail_connection import GmailConnection
from app.models.gmail_draft import GmailDraft
from app.models.reply_approval import ReplyApproval, ReplyApprovalStatus
from app.models.ticket import TicketStatus
from app.schemas.reply_approval import ReplyApprovalUpdate
from app.services.audit_log_service import create_audit_log
from app.services.gmail_token_service import refresh_connection_access_token
from app.services.pilot_control_service import ensure_draft_creation_enabled
from app.services.ticket_lifecycle_service import ensure_ticket_allows_draft, transition_ticket_status
from app.services.ticket_service import get_ticket_or_404, write_ticket_event


def list_reply_approvals(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
) -> list[ReplyApproval]:
    ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
    approvals = list(
        db.scalars(
            select(ReplyApproval)
            .where(ReplyApproval.organization_id == organization_id, ReplyApproval.ticket_id == ticket_id)
            .order_by(ReplyApproval.created_at.desc())
        )
    )
    if approvals:
        return approvals

    latest_triage = db.scalar(
        select(AITriageResult)
        .where(AITriageResult.organization_id == organization_id, AITriageResult.ticket_id == ticket_id)
        .order_by(AITriageResult.created_at.desc())
    )
    if latest_triage is None:
        return []

    approval = ReplyApproval(
        organization_id=organization_id,
        ticket_id=ticket_id,
        ai_triage_result_id=latest_triage.id,
        gmail_connection_id=ticket.gmail_connection_id,
        suggested_reply=latest_triage.draft_reply,
        final_reply=latest_triage.draft_reply,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return [approval]


def update_reply_approval(
    db: Session,
    organization_id: str,
    ticket_id: str,
    approval_id: str,
    actor: AuthenticatedUser,
    payload: ReplyApprovalUpdate,
) -> ReplyApproval:
    ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
    approval = _get_approval_or_404(db, organization_id, ticket_id, approval_id)
    if approval.status == ReplyApprovalStatus.DRAFT_CREATED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Draft-created reply cannot be edited")
    if approval.final_reply != payload.final_reply:
        approval.reply_version += 1
    approval.final_reply = payload.final_reply
    approval.status = ReplyApprovalStatus.PENDING.value
    approval.approved_by_user_id = None
    approval.approved_at = None
    approval.approved_reply_version = None
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.reply_approval_edited",
        {"reply_approval_id": approval.id, "reply_version": approval.reply_version},
    )
    db.commit()
    db.refresh(approval)
    return approval


def approve_reply_suggestion(
    db: Session,
    organization_id: str,
    suggestion_id: str,
    actor: AuthenticatedUser,
    payload: ReplyApprovalUpdate | None = None,
) -> ReplyApproval:
    approval = _get_suggestion_or_404(db, organization_id, suggestion_id)
    ticket = get_ticket_or_404(db, organization_id, approval.ticket_id, actor)
    if approval.status == ReplyApprovalStatus.DRAFT_CREATED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply suggestion already has a Gmail draft")

    final_reply = payload.final_reply if payload else approval.final_reply or approval.suggested_reply
    if not final_reply.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Final reply is required")
    if approval.final_reply != final_reply:
        approval.reply_version += 1

    approval.final_reply = final_reply
    approval.status = ReplyApprovalStatus.APPROVED.value
    approval.approved_by_user_id = actor.id
    approval.approved_at = datetime.now(UTC)
    approval.approved_reply_version = approval.reply_version
    create_audit_log(
        db,
        organization_id=organization_id,
        actor_user_id=actor.id,
        action="reply_suggestion.approved",
        resource_type="reply_approval",
        resource_id=approval.id,
        metadata={
            "ticket_id": approval.ticket_id,
            "ai_triage_result_id": approval.ai_triage_result_id,
            "reply_version": approval.reply_version,
        },
    )
    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.reply_approval_approved",
        {"reply_approval_id": approval.id, "reply_version": approval.reply_version},
    )
    db.commit()
    db.refresh(approval)
    return approval


async def approve_reply_and_create_draft(
    db: Session,
    organization_id: str,
    ticket_id: str,
    approval_id: str,
    actor: AuthenticatedUser,
    payload: ReplyApprovalUpdate | None = None,
) -> tuple[ReplyApproval, GmailDraft]:
    approval = approve_reply_suggestion(db, organization_id, approval_id, actor, payload)
    return await create_gmail_draft_from_approved_suggestion(db, organization_id, approval.id, actor)


async def create_gmail_draft_from_approved_suggestion(
    db: Session,
    organization_id: str,
    suggestion_id: str,
    actor: AuthenticatedUser,
) -> tuple[ReplyApproval, GmailDraft]:
    approval = _get_suggestion_or_404(db, organization_id, suggestion_id)
    ticket = get_ticket_or_404(db, organization_id, approval.ticket_id, actor)
    ensure_draft_creation_enabled(db, organization_id)
    existing_draft = get_gmail_draft_for_ticket(db, organization_id, ticket.id, actor, raise_not_found=False)
    if existing_draft is not None:
        if approval.status != ReplyApprovalStatus.DRAFT_CREATED.value:
            approval.status = ReplyApprovalStatus.DRAFT_CREATED.value
            approval.gmail_draft_id = existing_draft.gmail_draft_id
            db.commit()
            db.refresh(approval)
        return approval, existing_draft

    ensure_ticket_allows_draft(ticket)
    if approval.status != ReplyApprovalStatus.APPROVED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply suggestion must be approved first")
    if approval.approved_reply_version is not None and approval.approved_reply_version != approval.reply_version:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply approval is stale and must be approved again")
    if approval.approved_reply_version is None:
        approval.approved_reply_version = approval.reply_version

    if not ticket.gmail_connection_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ticket is not linked to a Gmail connection")

    connection = db.get(GmailConnection, ticket.gmail_connection_id)
    if connection is None or connection.organization_id != organization_id or connection.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Active Gmail connection not found")

    final_reply = approval.final_reply or approval.suggested_reply
    access_token, expires_at = await refresh_connection_access_token(db, connection, refresh_func=refresh_gmail_access_token)
    raw_message = build_reply_raw_message(
        to_email=ticket.customer.email,
        subject=ticket.subject,
        body=final_reply,
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
        reply_suggestion_id=approval.id,
        gmail_draft_id=draft_id,
        gmail_thread_id=ticket.gmail_thread_id,
        created_by_user_id=actor.id,
    )
    db.add(gmail_draft)
    connection.access_token_expires_at = expires_at
    approval.status = ReplyApprovalStatus.DRAFT_CREATED.value
    approval.gmail_draft_id = draft_id
    transition_ticket_status(ticket, TicketStatus.DRAFT_CREATED.value)

    write_ticket_event(
        db,
        ticket,
        actor,
        "ticket.reply_draft_created",
        {"reply_suggestion_id": approval.id, "gmail_draft_id": draft_id, "reply_version": approval.reply_version},
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
            "reply_suggestion_id": approval.id,
            "gmail_draft_id": draft_id,
            "gmail_thread_id": ticket.gmail_thread_id,
            "reply_version": approval.reply_version,
        },
    )
    db.commit()
    db.refresh(approval)
    db.refresh(gmail_draft)
    return approval, gmail_draft


def get_gmail_draft_for_ticket(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
    raise_not_found: bool = True,
) -> GmailDraft | None:
    get_ticket_or_404(db, organization_id, ticket_id, actor)
    draft = db.scalar(
        select(GmailDraft)
        .where(GmailDraft.organization_id == organization_id, GmailDraft.ticket_id == ticket_id)
        .order_by(GmailDraft.created_at.desc())
    )
    if draft is None and raise_not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gmail draft not found")
    return draft


def build_reply_raw_message(to_email: str, subject: str, body: str) -> str:
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")


def _get_approval_or_404(
    db: Session,
    organization_id: str,
    ticket_id: str,
    approval_id: str,
) -> ReplyApproval:
    approval = db.get(ReplyApproval, approval_id)
    if approval is None or approval.organization_id != organization_id or approval.ticket_id != ticket_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply suggestion not found")
    return approval


def _get_suggestion_or_404(db: Session, organization_id: str, suggestion_id: str) -> ReplyApproval:
    approval = db.get(ReplyApproval, suggestion_id)
    if approval is None or approval.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply suggestion not found")
    return approval

