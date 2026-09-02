from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.collaboration_lock import CollaborationLockAcquire, CollaborationLockRead
from app.services.collaboration_lock_service import acquire_collaboration_lock, release_collaboration_lock

router = APIRouter(prefix="/orgs/{organization_id}/collaboration-locks", tags=["collaboration-locks"])


@router.post("", response_model=CollaborationLockRead, status_code=status.HTTP_201_CREATED)
def acquire_org_collaboration_lock(
    organization_id: str,
    payload: CollaborationLockAcquire,
    db: DbSession,
    current_user: CurrentUser,
):
    return acquire_collaboration_lock(db, organization_id, current_user, payload)


@router.delete("/{lock_id}", status_code=status.HTTP_204_NO_CONTENT)
def release_org_collaboration_lock(organization_id: str, lock_id: str, db: DbSession, current_user: CurrentUser):
    release_collaboration_lock(db, organization_id, lock_id, current_user)
