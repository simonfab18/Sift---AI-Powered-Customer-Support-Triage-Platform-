import re
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.member import MemberStatus, OrganizationMember
from app.models.ticket_internal_note import TicketInternalNote, TicketInternalNoteEdit, TicketInternalNoteMention
from app.schemas.internal_note import InternalNoteCreate, InternalNoteUpdate
from app.services.audit_log_service import create_audit_log
from app.services.rbac_service import require_membership
from app.services.ticket_service import get_ticket_or_404, write_ticket_event

MENTION_RE = re.compile(r"@([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def _now() -> datetime:
    return datetime.now(UTC)


def _mentioned_user_ids(db: Session, organization_id: str, body: str) -> list[str]:
    emails = {match.group(1).lower() for match in MENTION_RE.finditer(body)}
    if not emails:
        return []
    members = db.scalars(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.status == MemberStatus.ACTIVE.value,
            OrganizationMember.email.in_(emails),
        )
    )
    return [member.user_id for member in members]


def _replace_mentions(db: Session, organization_id: str, note: TicketInternalNote) -> None:
    existing = list(
        db.scalars(
            select(TicketInternalNoteMention).where(
                TicketInternalNoteMention.organization_id == organization_id,
                TicketInternalNoteMention.note_id == note.id,
            )
        )
    )
    for mention in existing:
        db.delete(mention)
    for user_id in _mentioned_user_ids(db, organization_id, note.body):
        db.add(TicketInternalNoteMention(organization_id=organization_id, note_id=note.id, mentioned_user_id=user_id))


def list_internal_notes(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
) -> list[TicketInternalNote]:
    get_ticket_or_404(db, organization_id, ticket_id, actor)
    return list(
        db.scalars(
            select(TicketInternalNote)
            .where(
                TicketInternalNote.organization_id == organization_id,
                TicketInternalNote.ticket_id == ticket_id,
                TicketInternalNote.deleted_at.is_(None),
            )
            .order_by(TicketInternalNote.created_at.asc())
        )
    )


def create_internal_note(
    db: Session,
    organization_id: str,
    ticket_id: str,
    actor: AuthenticatedUser,
    payload: InternalNoteCreate,
) -> TicketInternalNote:
    ticket = get_ticket_or_404(db, organization_id, ticket_id, actor)
    note = TicketInternalNote(
        organization_id=organization_id,
        ticket_id=ticket_id,
        body=payload.body,
        created_by_user_id=actor.id,
    )
    db.add(note)
    db.flush()
    _replace_mentions(db, organization_id, note)
    write_ticket_event(db, ticket, actor, "ticket.internal_note_created", {"note_id": note.id})
    create_audit_log(db, organization_id, actor.id, "internal_note.created", "ticket_internal_note", note.id, metadata={"ticket_id": ticket_id})
    db.commit()
    db.refresh(note)
    return note


def update_internal_note(
    db: Session,
    organization_id: str,
    note_id: str,
    actor: AuthenticatedUser,
    payload: InternalNoteUpdate,
) -> TicketInternalNote:
    require_membership(db, organization_id, actor)
    note = db.get(TicketInternalNote, note_id)
    if note is None or note.organization_id != organization_id or note.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal note not found")
    ticket = get_ticket_or_404(db, organization_id, note.ticket_id, actor)
    previous_body = note.body
    note.body = payload.body
    note.version += 1
    note.updated_by_user_id = actor.id
    db.add(
        TicketInternalNoteEdit(
            organization_id=organization_id,
            note_id=note.id,
            edited_by_user_id=actor.id,
            previous_body=previous_body,
            new_body=payload.body,
            version=note.version,
        )
    )
    _replace_mentions(db, organization_id, note)
    write_ticket_event(db, ticket, actor, "ticket.internal_note_edited", {"note_id": note.id, "version": note.version})
    create_audit_log(db, organization_id, actor.id, "internal_note.edited", "ticket_internal_note", note.id, metadata={"ticket_id": note.ticket_id, "version": note.version})
    db.commit()
    db.refresh(note)
    return note


def delete_internal_note(db: Session, organization_id: str, note_id: str, actor: AuthenticatedUser) -> None:
    require_membership(db, organization_id, actor)
    note = db.get(TicketInternalNote, note_id)
    if note is None or note.organization_id != organization_id or note.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal note not found")
    ticket = get_ticket_or_404(db, organization_id, note.ticket_id, actor)
    note.deleted_at = _now()
    write_ticket_event(db, ticket, actor, "ticket.internal_note_deleted", {"note_id": note.id})
    create_audit_log(db, organization_id, actor.id, "internal_note.deleted", "ticket_internal_note", note.id, metadata={"ticket_id": note.ticket_id})
    db.commit()


def list_internal_note_edits(db: Session, organization_id: str, note_id: str, actor: AuthenticatedUser) -> list[TicketInternalNoteEdit]:
    require_membership(db, organization_id, actor)
    note = db.get(TicketInternalNote, note_id)
    if note is None or note.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal note not found")
    return list(
        db.scalars(
            select(TicketInternalNoteEdit)
            .where(TicketInternalNoteEdit.organization_id == organization_id, TicketInternalNoteEdit.note_id == note_id)
            .order_by(TicketInternalNoteEdit.created_at.asc())
        )
    )


def list_internal_note_mentions(db: Session, organization_id: str, note_id: str, actor: AuthenticatedUser) -> list[TicketInternalNoteMention]:
    require_membership(db, organization_id, actor)
    note = db.get(TicketInternalNote, note_id)
    if note is None or note.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internal note not found")
    return list(
        db.scalars(
            select(TicketInternalNoteMention)
            .where(TicketInternalNoteMention.organization_id == organization_id, TicketInternalNoteMention.note_id == note_id)
            .order_by(TicketInternalNoteMention.created_at.asc())
        )
    )
