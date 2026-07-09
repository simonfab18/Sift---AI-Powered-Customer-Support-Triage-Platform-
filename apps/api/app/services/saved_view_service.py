from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.ticket import TicketPriority, TicketStatus
from app.models.ticket_saved_view import TicketSavedView
from app.schemas.saved_view import SavedViewCreate, SavedViewUpdate
from app.services.rbac_service import require_membership

ALLOWED_FILTER_KEYS = {"status", "priority", "assigned_to", "triage_status"}
ALLOWED_STATUSES = {item.value for item in TicketStatus} | {"all"}
ALLOWED_PRIORITIES = {item.value for item in TicketPriority}


def sanitize_saved_view_filters(filters: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in filters.items():
        if key not in ALLOWED_FILTER_KEYS or value in (None, ""):
            continue
        if key == "status" and value not in ALLOWED_STATUSES:
            continue
        if key == "priority" and value not in ALLOWED_PRIORITIES:
            continue
        sanitized[key] = value
    return sanitized


def list_saved_views(db: Session, organization_id: str, actor: AuthenticatedUser) -> list[TicketSavedView]:
    require_membership(db, organization_id, actor)
    return list(
        db.scalars(
            select(TicketSavedView)
            .where(TicketSavedView.organization_id == organization_id, TicketSavedView.user_id == actor.id)
            .order_by(TicketSavedView.name.asc())
        )
    )


def create_saved_view(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    payload: SavedViewCreate,
) -> TicketSavedView:
    require_membership(db, organization_id, actor)
    view = TicketSavedView(
        organization_id=organization_id,
        user_id=actor.id,
        name=payload.name.strip(),
        filters=sanitize_saved_view_filters(payload.filters),
    )
    db.add(view)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Saved view name already exists") from exc
    db.refresh(view)
    return view


def update_saved_view(
    db: Session,
    organization_id: str,
    view_id: str,
    actor: AuthenticatedUser,
    payload: SavedViewUpdate,
) -> TicketSavedView:
    view = db.get(TicketSavedView, view_id)
    if view is None or view.organization_id != organization_id or view.user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    require_membership(db, organization_id, actor)
    if payload.name is not None:
        view.name = payload.name.strip()
    if payload.filters is not None:
        view.filters = sanitize_saved_view_filters(payload.filters)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Saved view name already exists") from exc
    db.refresh(view)
    return view


def delete_saved_view(db: Session, organization_id: str, view_id: str, actor: AuthenticatedUser) -> None:
    view = db.get(TicketSavedView, view_id)
    if view is None or view.organization_id != organization_id or view.user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved view not found")
    require_membership(db, organization_id, actor)
    db.delete(view)
    db.commit()
