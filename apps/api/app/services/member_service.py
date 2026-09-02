from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.member import MemberRole, MemberStatus, OrganizationMember
from app.models.organization import Organization
from app.models.ticket import Ticket, TicketStatus
from app.schemas.member import MemberInvite, MemberUpdate
from app.services.email_service import invite_signup_url, send_teammate_invite_email
from app.services.organization_service import placeholder_user_id_for_email
from app.services.rbac_service import can_manage_role, require_role


def _ticket_counts_for_member(db: Session, organization_id: str, user_id: str) -> dict[str, int]:
    counts = {ticket_status.value: 0 for ticket_status in TicketStatus}
    rows = db.execute(
        select(Ticket.status, func.count())
        .where(
            Ticket.organization_id == organization_id,
            Ticket.assigned_to_user_id == user_id,
        )
        .group_by(Ticket.status)
    ).all()
    for ticket_status, count in rows:
        counts[str(ticket_status)] = int(count)
    counts["total"] = sum(counts.values())
    return counts


def list_members(db: Session, organization_id: str, actor: AuthenticatedUser) -> list[OrganizationMember]:
    actor_membership = require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    members = list(
        db.scalars(
            select(OrganizationMember)
            .where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.status != MemberStatus.DISABLED.value,
            )
            .order_by(OrganizationMember.created_at.asc())
        )
    )
    if actor_membership.role == MemberRole.ADMIN.value:
        members = [member for member in members if member.role == MemberRole.AGENT.value or member.user_id == actor.id]
    for member in members:
        setattr(member, "ticket_counts", _ticket_counts_for_member(db, organization_id, member.user_id))
    return members


def active_owner_count(db: Session, organization_id: str) -> int:
    return len(
        list(
            db.scalars(
                select(OrganizationMember).where(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.role == MemberRole.OWNER.value,
                    OrganizationMember.status == MemberStatus.ACTIVE.value,
                )
            )
        )
    )


def ensure_owner_will_remain(db: Session, organization_id: str, member: OrganizationMember) -> None:
    if member.role != MemberRole.OWNER.value or member.status != MemberStatus.ACTIVE.value:
        return
    if active_owner_count(db, organization_id) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A workspace must keep at least one active owner")

def invite_member(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    payload: MemberInvite,
) -> OrganizationMember:
    actor_membership = require_role(
        db,
        organization_id,
        actor,
        {MemberRole.OWNER, MemberRole.ADMIN},
    )
    if not can_manage_role(actor_membership.role, payload.role.value):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign that role")

    email = payload.email.strip().lower()
    existing = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.email == email,
            OrganizationMember.status != MemberStatus.DISABLED.value,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Member already exists")

    member = OrganizationMember(
        organization_id=organization_id,
        user_id=placeholder_user_id_for_email(email),
        email=email,
        role=payload.role.value,
        status=MemberStatus.INVITED.value,
    )
    db.add(member)
    db.flush()

    organization = db.get(Organization, organization_id)
    invite_url = invite_signup_url(email, organization_id, payload.role.value)
    delivery = send_teammate_invite_email(
        to_email=email,
        organization_name=organization.name if organization else "your Sift workspace",
        organization_id=organization_id,
        role=payload.role.value,
        invited_by_email=actor.email,
    )
    setattr(member, "invite_email_delivery_status", delivery.status)
    setattr(member, "invite_email_delivery_detail", delivery.detail)
    setattr(member, "invite_url", invite_url)

    db.commit()
    db.refresh(member)
    setattr(member, "invite_email_delivery_status", delivery.status)
    setattr(member, "invite_email_delivery_detail", delivery.detail)
    setattr(member, "invite_url", invite_url)
    return member


def update_member(
    db: Session,
    organization_id: str,
    member_id: str,
    actor: AuthenticatedUser,
    payload: MemberUpdate,
) -> OrganizationMember:
    actor_membership = require_role(
        db,
        organization_id,
        actor,
        {MemberRole.OWNER, MemberRole.ADMIN},
    )
    member = db.get(OrganizationMember, member_id)
    if member is None or member.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member.user_id == actor.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot modify your own membership")
    if member.role == MemberRole.OWNER.value and actor_membership.role != MemberRole.OWNER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot modify owner")

    next_role = payload.role.value if payload.role else member.role
    if next_role != MemberRole.OWNER.value:
        ensure_owner_will_remain(db, organization_id, member)
    if not can_manage_role(actor_membership.role, next_role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot assign that role")

    if payload.role is not None:
        member.role = payload.role.value
    if payload.status is not None:
        member.status = payload.status.value

    db.commit()
    db.refresh(member)
    return member


def remove_member(db: Session, organization_id: str, member_id: str, actor: AuthenticatedUser) -> None:
    actor_membership = require_role(
        db,
        organization_id,
        actor,
        {MemberRole.OWNER, MemberRole.ADMIN},
    )
    member = db.get(OrganizationMember, member_id)
    if member is None or member.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member.user_id == actor.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot remove yourself")
    if member.role == MemberRole.OWNER.value:
        ensure_owner_will_remain(db, organization_id, member)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot remove owner")
    if not can_manage_role(actor_membership.role, member.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot remove that member")

    member.status = MemberStatus.DISABLED.value
    db.commit()
