from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.ticket_collaboration_lock import TicketCollaborationLock
from app.schemas.collaboration_lock import CollaborationLockAcquire
from app.services.rbac_service import require_membership
from app.services.ticket_service import get_ticket_or_404


def _now() -> datetime:
    return datetime.now(UTC)


def _is_active(lock: TicketCollaborationLock) -> bool:
    expires_at = lock.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at > _now()


def acquire_collaboration_lock(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    payload: CollaborationLockAcquire,
) -> TicketCollaborationLock:
    require_membership(db, organization_id, actor)
    get_ticket_or_404(db, organization_id, payload.ticket_id, actor)
    lock = db.scalar(
        select(TicketCollaborationLock).where(
            TicketCollaborationLock.organization_id == organization_id,
            TicketCollaborationLock.resource_type == payload.resource_type,
            TicketCollaborationLock.resource_id == payload.resource_id,
        )
    )
    expires_at = _now() + timedelta(seconds=payload.ttl_seconds)
    if lock is not None and _is_active(lock) and lock.locked_by_user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource is being edited by another agent")
    if lock is None:
        lock = TicketCollaborationLock(
            organization_id=organization_id,
            ticket_id=payload.ticket_id,
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            locked_by_user_id=actor.id,
            mode=payload.mode,
            expires_at=expires_at,
        )
        db.add(lock)
    else:
        lock.ticket_id = payload.ticket_id
        lock.locked_by_user_id = actor.id
        lock.mode = payload.mode
        lock.expires_at = expires_at
    db.commit()
    db.refresh(lock)
    return lock


def release_collaboration_lock(
    db: Session,
    organization_id: str,
    lock_id: str,
    actor: AuthenticatedUser,
) -> None:
    require_membership(db, organization_id, actor)
    lock = db.get(TicketCollaborationLock, lock_id)
    if lock is None or lock.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaboration lock not found")
    if lock.locked_by_user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the lock owner can release it")
    db.delete(lock)
    db.commit()


def ensure_resource_not_locked_by_other(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    resource_type: str,
    resource_id: str,
) -> None:
    lock = db.scalar(
        select(TicketCollaborationLock).where(
            TicketCollaborationLock.organization_id == organization_id,
            TicketCollaborationLock.resource_type == resource_type,
            TicketCollaborationLock.resource_id == resource_id,
        )
    )
    if lock is not None and _is_active(lock) and lock.locked_by_user_id != actor.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Resource is being edited by another agent")
