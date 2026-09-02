from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.member import MemberRole
from app.models.response_template import ResponseTemplate
from app.models.reply_suggestion import ReplySuggestionCreatedBy, ReplySuggestionStatus
from app.schemas.response_template import ResponseTemplateCreate, ResponseTemplateInsert, ResponseTemplateUpdate
from app.schemas.reply_suggestion import ReplySuggestionCreate
from app.services.audit_log_service import create_audit_log
from app.services.rbac_service import require_membership, require_role
from app.services.reply_suggestion_service import create_agent_reply_suggestion



def _normalized_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _ensure_unique_active_template_name(db: Session, organization_id: str, name: str, template_id: str | None = None) -> None:
    normalized = _normalized_name(name)
    templates = list(
        db.scalars(
            select(ResponseTemplate).where(
                ResponseTemplate.organization_id == organization_id,
                ResponseTemplate.archived_at.is_(None),
            )
        )
    )
    for template in templates:
        if template_id is not None and template.id == template_id:
            continue
        if _normalized_name(template.name) == normalized:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An active response template with this name already exists")

def _normalize_tags(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        clean = tag.strip().lower()
        if clean and clean not in normalized:
            normalized.append(clean)
    return normalized


def list_response_templates(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    search: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
) -> list[ResponseTemplate]:
    require_membership(db, organization_id, actor)
    statement = select(ResponseTemplate).where(ResponseTemplate.organization_id == organization_id)
    if not include_archived:
        statement = statement.where(ResponseTemplate.archived_at.is_(None))
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(or_(ResponseTemplate.name.ilike(pattern), ResponseTemplate.body.ilike(pattern)))
    templates = list(db.scalars(statement.order_by(ResponseTemplate.name.asc())))
    if tag:
        wanted = tag.strip().lower()
        templates = [template for template in templates if wanted in (template.category_tags or [])]
    return templates


def create_response_template(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    payload: ResponseTemplateCreate,
) -> ResponseTemplate:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    _ensure_unique_active_template_name(db, organization_id, payload.name)
    template = ResponseTemplate(
        organization_id=organization_id,
        name=payload.name.strip(),
        body=payload.body,
        category_tags=_normalize_tags(payload.category_tags),
        created_by_user_id=actor.id,
    )
    db.add(template)
    create_audit_log(
        db,
        organization_id,
        actor.id,
        "response_template.created",
        "response_template",
        template.id,
        metadata={"name": template.name, "category_tags": template.category_tags},
    )
    db.commit()
    db.refresh(template)
    return template


def update_response_template(
    db: Session,
    organization_id: str,
    template_id: str,
    actor: AuthenticatedUser,
    payload: ResponseTemplateUpdate,
) -> ResponseTemplate:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    template = db.get(ResponseTemplate, template_id)
    if template is None or template.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response template not found")
    changed = False
    if payload.name is not None and payload.name.strip() != template.name:
        _ensure_unique_active_template_name(db, organization_id, payload.name, template.id)
        template.name = payload.name.strip()
        changed = True
    if payload.body is not None and payload.body != template.body:
        template.body = payload.body
        changed = True
    if payload.category_tags is not None:
        tags = _normalize_tags(payload.category_tags)
        if tags != template.category_tags:
            template.category_tags = tags
            changed = True
    if payload.archived is not None:
        template.archived_at = datetime.now(UTC) if payload.archived else None
        changed = True
    if changed:
        template.version += 1
        template.updated_by_user_id = actor.id
        create_audit_log(
            db,
            organization_id,
            actor.id,
            "response_template.updated",
            "response_template",
            template.id,
            metadata={"version": template.version},
        )
    db.commit()
    db.refresh(template)
    return template


def insert_template_into_reply_suggestion(
    db: Session,
    organization_id: str,
    template_id: str,
    actor: AuthenticatedUser,
    payload: ResponseTemplateInsert,
):
    require_membership(db, organization_id, actor)
    template = db.get(ResponseTemplate, template_id)
    if template is None or template.organization_id != organization_id or template.archived_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Response template not found")
    suggestion = create_agent_reply_suggestion(
        db,
        organization_id,
        payload.ticket_id,
        actor,
        ReplySuggestionCreate(body=template.body),
    )
    suggestion.status = ReplySuggestionStatus.SUGGESTED.value
    suggestion.created_by = ReplySuggestionCreatedBy.AGENT.value
    create_audit_log(
        db,
        organization_id,
        actor.id,
        "response_template.inserted",
        "response_template",
        template.id,
        metadata={"ticket_id": payload.ticket_id, "reply_suggestion_id": suggestion.id, "template_version": template.version},
    )
    db.commit()
    db.refresh(template)
    db.refresh(suggestion)
    return template, suggestion

