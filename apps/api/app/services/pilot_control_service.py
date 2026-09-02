from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.workspace_settings_service import get_or_create_workspace_settings

PILOT_NOT_ALLOWED_DETAIL = "Organization is not enabled for the pilot"
SYNC_DISABLED_DETAIL = "Gmail sync is disabled for this pilot workspace"
AUTO_TRIAGE_DISABLED_DETAIL = "Automatic triage is disabled for this pilot workspace"
DRAFT_DISABLED_DETAIL = "Gmail draft creation is disabled for this pilot workspace"
DIRECT_SEND_DISABLED_DETAIL = "Direct Gmail sending is disabled for this workspace"


def ensure_organization_pilot_allowed(organization_id: str) -> None:
    if settings.pilot_require_allowlist and organization_id not in settings.pilot_allowlist:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PILOT_NOT_ALLOWED_DETAIL)


def is_sync_enabled(db: Session, organization_id: str) -> bool:
    if settings.pilot_require_allowlist and organization_id not in settings.pilot_allowlist:
        return False
    workspace_settings = get_or_create_workspace_settings(db, organization_id)
    return settings.pilot_sync_enabled and workspace_settings.sync_enabled


def ensure_sync_enabled(db: Session, organization_id: str) -> None:
    ensure_organization_pilot_allowed(organization_id)
    workspace_settings = get_or_create_workspace_settings(db, organization_id)
    if not settings.pilot_sync_enabled or not workspace_settings.sync_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=SYNC_DISABLED_DETAIL)


def is_auto_triage_enabled(db: Session, organization_id: str) -> bool:
    if settings.pilot_require_allowlist and organization_id not in settings.pilot_allowlist:
        return False
    workspace_settings = get_or_create_workspace_settings(db, organization_id)
    return settings.pilot_auto_triage_enabled and workspace_settings.auto_triage_enabled


def ensure_auto_triage_enabled(db: Session, organization_id: str) -> None:
    ensure_organization_pilot_allowed(organization_id)
    workspace_settings = get_or_create_workspace_settings(db, organization_id)
    if not settings.pilot_auto_triage_enabled or not workspace_settings.auto_triage_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=AUTO_TRIAGE_DISABLED_DETAIL)


def ensure_draft_creation_enabled(db: Session, organization_id: str) -> None:
    ensure_organization_pilot_allowed(organization_id)
    workspace_settings = get_or_create_workspace_settings(db, organization_id)
    if not settings.pilot_draft_creation_enabled or not workspace_settings.draft_creation_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=DRAFT_DISABLED_DETAIL)



def ensure_direct_send_enabled(db: Session, organization_id: str) -> None:
    ensure_organization_pilot_allowed(organization_id)
    workspace_settings = get_or_create_workspace_settings(db, organization_id)
    if not settings.direct_send_enabled or not workspace_settings.direct_send_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=DIRECT_SEND_DISABLED_DETAIL)
