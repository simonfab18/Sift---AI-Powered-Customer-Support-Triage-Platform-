from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.audit_log import AuditLog
from app.models.member import MemberRole
from app.services.rbac_service import require_role

SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "authorization",
    "api_key",
    "apikey",
    "refresh",
    "access",
)
REDACTED = "[REDACTED]"


def redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_sensitive_values(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]
    return value


def create_audit_log(
    db: Session,
    organization_id: str,
    actor_user_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        audit_metadata=redact_sensitive_values(metadata or {}),
    )
    db.add(audit_log)
    return audit_log


def list_audit_logs(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    *,
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    statement = select(AuditLog).where(AuditLog.organization_id == organization_id)
    if action:
        statement = statement.where(AuditLog.action == action)
    if resource_type:
        statement = statement.where(AuditLog.resource_type == resource_type)
    if actor_user_id:
        statement = statement.where(AuditLog.actor_user_id == actor_user_id)
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                AuditLog.action.ilike(term),
                AuditLog.resource_type.ilike(term),
                AuditLog.resource_id.ilike(term),
                AuditLog.actor_user_id.ilike(term),
            )
        )
    return list(
        db.scalars(
            statement.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
        )
    )
