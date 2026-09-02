from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.internal_note import (
    InternalNoteCreate,
    InternalNoteEditRead,
    InternalNoteMentionRead,
    InternalNoteRead,
    InternalNoteUpdate,
)
from app.services.internal_note_service import (
    create_internal_note,
    delete_internal_note,
    list_internal_note_edits,
    list_internal_note_mentions,
    list_internal_notes,
    update_internal_note,
)

router = APIRouter(prefix="/orgs/{organization_id}", tags=["internal-notes"])


@router.get("/tickets/{ticket_id}/internal-notes", response_model=list[InternalNoteRead])
def read_internal_notes(organization_id: str, ticket_id: str, db: DbSession, current_user: CurrentUser):
    return list_internal_notes(db, organization_id, ticket_id, current_user)


@router.post("/tickets/{ticket_id}/internal-notes", response_model=InternalNoteRead, status_code=status.HTTP_201_CREATED)
def create_org_internal_note(
    organization_id: str,
    ticket_id: str,
    payload: InternalNoteCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    return create_internal_note(db, organization_id, ticket_id, current_user, payload)


@router.patch("/internal-notes/{note_id}", response_model=InternalNoteRead)
def update_org_internal_note(organization_id: str, note_id: str, payload: InternalNoteUpdate, db: DbSession, current_user: CurrentUser):
    return update_internal_note(db, organization_id, note_id, current_user, payload)


@router.delete("/internal-notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org_internal_note(organization_id: str, note_id: str, db: DbSession, current_user: CurrentUser):
    delete_internal_note(db, organization_id, note_id, current_user)


@router.get("/internal-notes/{note_id}/edits", response_model=list[InternalNoteEditRead])
def read_internal_note_edits(organization_id: str, note_id: str, db: DbSession, current_user: CurrentUser):
    return list_internal_note_edits(db, organization_id, note_id, current_user)


@router.get("/internal-notes/{note_id}/mentions", response_model=list[InternalNoteMentionRead])
def read_internal_note_mentions(organization_id: str, note_id: str, db: DbSession, current_user: CurrentUser):
    return list_internal_note_mentions(db, organization_id, note_id, current_user)
