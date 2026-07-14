from datetime import UTC, datetime
from re import sub
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.ai_triage_result import AITriageResult
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.gmail_connection import GmailConnection
from app.models.gmail_draft import GmailDraft
from app.models.job_run import JobRun
from app.models.member import MemberRole, MemberStatus, OrganizationMember
from app.models.organization import Organization
from app.models.reply_approval import ReplyApproval
from app.models.ticket import Ticket
from app.models.ticket_attachment import TicketAttachment
from app.models.workspace_settings import WorkspaceSettings
from app.schemas.organization import OrganizationDeletionRequestCreate, UserOrganizationRead
from app.services.audit_log_service import create_audit_log
from app.services.rbac_service import require_role


def make_slug(name: str) -> str:
    base = sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return base or "organization"


def unique_slug(db: Session, name: str) -> str:
    base = make_slug(name)
    slug = base
    suffix = 2
    while db.scalar(select(Organization).where(Organization.slug == slug)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def create_organization(db: Session, user: AuthenticatedUser, name: str) -> Organization:
    organization = Organization(name=name.strip(), slug=unique_slug(db, name))
    db.add(organization)
    db.flush()

    member = OrganizationMember(
        organization_id=organization.id,
        user_id=user.id,
        email=user.email or "unknown@example.local",
        role=MemberRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    db.add(member)
    db.commit()
    db.refresh(organization)
    return organization


def list_user_organizations(db: Session, user: AuthenticatedUser) -> list[UserOrganizationRead]:
    rows = db.execute(
        select(Organization, OrganizationMember)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.status == MemberStatus.ACTIVE.value,
        )
        .order_by(Organization.created_at.desc())
    ).all()
    return [
        UserOrganizationRead(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            role=member.role,
        )
        for organization, member in rows
    ]


def get_organization(db: Session, organization_id: str) -> Organization | None:
    return db.get(Organization, organization_id)


def placeholder_user_id_for_email(email: str) -> str:
    normalized = email.strip().lower()
    return f"invited:{normalized}:{uuid4()}"


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def _count(db: Session, model, organization_id: str) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(model.organization_id == organization_id)) or 0)


def export_organization_data(db: Session, organization_id: str, actor: AuthenticatedUser) -> dict:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    organization = get_organization(db, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    settings = db.scalar(select(WorkspaceSettings).where(WorkspaceSettings.organization_id == organization_id))
    members = list(db.scalars(select(OrganizationMember).where(OrganizationMember.organization_id == organization_id).order_by(OrganizationMember.created_at.asc())))
    connections = list(db.scalars(select(GmailConnection).where(GmailConnection.organization_id == organization_id).order_by(GmailConnection.created_at.asc())))
    customers = list(db.scalars(select(Customer).where(Customer.organization_id == organization_id).order_by(Customer.created_at.asc())))
    tickets = list(db.scalars(select(Ticket).where(Ticket.organization_id == organization_id).order_by(Ticket.created_at.asc())))
    attachments = list(db.scalars(select(TicketAttachment).where(TicketAttachment.organization_id == organization_id).order_by(TicketAttachment.created_at.asc())))
    approvals = list(db.scalars(select(ReplyApproval).where(ReplyApproval.organization_id == organization_id).order_by(ReplyApproval.created_at.asc())))
    audit_logs = list(db.scalars(select(AuditLog).where(AuditLog.organization_id == organization_id).order_by(AuditLog.created_at.desc()).limit(500)))

    create_audit_log(
        db,
        organization_id,
        actor.id,
        "organization.export.generated",
        "organization",
        organization_id,
        metadata={"counts_included": True},
    )
    db.commit()

    return {
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "created_at": _iso(organization.created_at),
            "updated_at": _iso(organization.updated_at),
        },
        "generated_at": datetime.now(UTC).isoformat(),
        "generated_by_user_id": actor.id,
        "counts": {
            "members": len(members),
            "gmail_connections": len(connections),
            "customers": len(customers),
            "tickets": len(tickets),
            "attachments": len(attachments),
            "reply_approvals": len(approvals),
            "ai_triage_results": _count(db, AITriageResult, organization_id),
            "gmail_drafts": _count(db, GmailDraft, organization_id),
            "job_runs": _count(db, JobRun, organization_id),
            "audit_logs_included": len(audit_logs),
        },
        "workspace_settings": None if settings is None else {
            "sync_enabled": settings.sync_enabled,
            "auto_triage_enabled": settings.auto_triage_enabled,
            "draft_creation_enabled": settings.draft_creation_enabled,
            "draft_requires_approval": settings.draft_requires_approval,
            "pilot_feedback_contact": settings.pilot_feedback_contact,
            "business_timezone": settings.business_timezone,
            "business_hours": settings.business_hours,
            "first_review_target_minutes": settings.first_review_target_minutes,
            "resolution_target_minutes": settings.resolution_target_minutes,
            "updated_at": _iso(settings.updated_at),
        },
        "members": [
            {"id": member.id, "user_id": member.user_id, "email": member.email, "role": member.role, "status": member.status, "created_at": _iso(member.created_at)}
            for member in members
        ],
        "gmail_connections": [
            {
                "id": connection.id,
                "gmail_email": connection.gmail_email,
                "display_name": connection.display_name,
                "inbox_type": connection.inbox_type,
                "shared_address": connection.shared_address,
                "channel_notes": connection.channel_notes,
                "status": connection.status,
                "sync_status": connection.sync_status,
                "watch_status": connection.watch_status,
                "last_successful_sync_at": _iso(connection.last_successful_sync_at),
                "watch_expires_at": _iso(connection.watch_expires_at),
                "created_at": _iso(connection.created_at),
            }
            for connection in connections
        ],
        "customers": [
            {"id": customer.id, "email": customer.email, "name": customer.name, "created_at": _iso(customer.created_at)}
            for customer in customers
        ],
        "tickets": [
            {
                "id": ticket.id,
                "customer_id": ticket.customer_id,
                "gmail_connection_id": ticket.gmail_connection_id,
                "subject": ticket.subject,
                "message_text": ticket.message_text,
                "status": ticket.status,
                "category": ticket.category,
                "priority": ticket.priority,
                "sentiment": ticket.sentiment,
                "triage_status": ticket.triage_status,
                "received_at": _iso(ticket.received_at),
                "created_at": _iso(ticket.created_at),
            }
            for ticket in tickets
        ],
        "attachments": [
            {
                "id": attachment.id,
                "ticket_id": attachment.ticket_id,
                "filename": attachment.filename,
                "mime_type": attachment.mime_type,
                "size_bytes": attachment.size_bytes,
                "policy_status": attachment.policy_status,
                "storage_status": attachment.storage_status,
                "scan_status": attachment.scan_status,
                "created_at": _iso(attachment.created_at),
            }
            for attachment in attachments
        ],
        "reply_approvals": [
            {
                "id": approval.id,
                "ticket_id": approval.ticket_id,
                "status": approval.status,
                "reply_version": approval.reply_version,
                "approved_by_user_id": approval.approved_by_user_id,
                "approved_at": _iso(approval.approved_at),
                "created_at": _iso(approval.created_at),
            }
            for approval in approvals
        ],
        "audit_logs": [
            {
                "id": log.id,
                "actor_user_id": log.actor_user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "metadata": log.audit_metadata,
                "created_at": _iso(log.created_at),
            }
            for log in audit_logs
        ],
    }


def request_organization_deletion(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    payload: OrganizationDeletionRequestCreate,
) -> dict:
    require_role(db, organization_id, actor, {MemberRole.OWNER})
    organization = get_organization(db, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if not payload.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deletion request confirmation is required")

    settings = db.scalar(select(WorkspaceSettings).where(WorkspaceSettings.organization_id == organization_id))
    if settings is None:
        settings = WorkspaceSettings(organization_id=organization_id)
        db.add(settings)
        db.flush()
    settings.sync_enabled = False
    settings.auto_triage_enabled = False
    settings.draft_creation_enabled = False

    requested_at = datetime.now(UTC)
    create_audit_log(
        db,
        organization_id,
        actor.id,
        "organization.deletion_requested",
        "organization",
        organization_id,
        metadata={
            "reason": payload.reason,
            "sync_paused": True,
            "auto_triage_paused": True,
            "draft_creation_paused": True,
        },
    )
    db.commit()

    return {
        "organization_id": organization_id,
        "status": "requested",
        "requested_by_user_id": actor.id,
        "requested_at": requested_at.isoformat(),
        "sync_paused": True,
        "auto_triage_paused": True,
        "draft_creation_paused": True,
    }