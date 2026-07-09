from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.saved_view import SavedViewCreate, SavedViewRead, SavedViewUpdate
from app.services.saved_view_service import create_saved_view, delete_saved_view, list_saved_views, update_saved_view

router = APIRouter(prefix="/orgs/{organization_id}/saved-views", tags=["saved-views"])


@router.get("", response_model=list[SavedViewRead])
def read_saved_views(organization_id: str, db: DbSession, current_user: CurrentUser):
    return list_saved_views(db, organization_id, current_user)


@router.post("", response_model=SavedViewRead, status_code=status.HTTP_201_CREATED)
def create_org_saved_view(organization_id: str, payload: SavedViewCreate, db: DbSession, current_user: CurrentUser):
    return create_saved_view(db, organization_id, current_user, payload)


@router.patch("/{view_id}", response_model=SavedViewRead)
def update_org_saved_view(organization_id: str, view_id: str, payload: SavedViewUpdate, db: DbSession, current_user: CurrentUser):
    return update_saved_view(db, organization_id, view_id, current_user, payload)


@router.delete("/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org_saved_view(organization_id: str, view_id: str, db: DbSession, current_user: CurrentUser):
    delete_saved_view(db, organization_id, view_id, current_user)
