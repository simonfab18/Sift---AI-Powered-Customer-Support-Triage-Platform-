from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, DbSession
from app.api.rate_limits import limit_member_invite
from app.models.member import MemberRole
from app.schemas.member import MemberInvite, MemberRead, MemberUpdate
from app.services.member_service import invite_member, list_members, remove_member, update_member
from app.services.rbac_service import require_role

router = APIRouter(prefix="/orgs/{organization_id}/members", tags=["members"])


@router.get("", response_model=list[MemberRead])
def read_members(organization_id: str, db: DbSession, current_user: CurrentUser):
    return list_members(db, organization_id, current_user)


@router.post("/invite", response_model=MemberRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(limit_member_invite)])
def invite_org_member(
    organization_id: str,
    payload: MemberInvite,
    db: DbSession,
    current_user: CurrentUser,
):
    return invite_member(db, organization_id, current_user, payload)


@router.patch("/{member_id}", response_model=MemberRead)
def update_org_member(
    organization_id: str,
    member_id: str,
    payload: MemberUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return update_member(db, organization_id, member_id, current_user, payload)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org_member(
    organization_id: str,
    member_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    require_role(db, organization_id, current_user, {MemberRole.OWNER, MemberRole.ADMIN})
    remove_member(db, organization_id, member_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
