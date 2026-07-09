from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.response_template import (
    ResponseTemplateCreate,
    ResponseTemplateInsert,
    ResponseTemplateRead,
    ResponseTemplateUpdate,
    TemplateInsertResult,
)
from app.services.response_template_service import (
    create_response_template,
    insert_template_into_reply_suggestion,
    list_response_templates,
    update_response_template,
)

router = APIRouter(prefix="/orgs/{organization_id}/response-templates", tags=["response-templates"])


@router.get("", response_model=list[ResponseTemplateRead])
def read_response_templates(
    organization_id: str,
    db: DbSession,
    current_user: CurrentUser,
    search: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
):
    return list_response_templates(db, organization_id, current_user, search, tag, include_archived)


@router.post("", response_model=ResponseTemplateRead, status_code=status.HTTP_201_CREATED)
def create_org_response_template(
    organization_id: str,
    payload: ResponseTemplateCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    return create_response_template(db, organization_id, current_user, payload)


@router.patch("/{template_id}", response_model=ResponseTemplateRead)
def update_org_response_template(
    organization_id: str,
    template_id: str,
    payload: ResponseTemplateUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return update_response_template(db, organization_id, template_id, current_user, payload)


@router.post("/{template_id}/insert", response_model=TemplateInsertResult)
def insert_org_response_template(
    organization_id: str,
    template_id: str,
    payload: ResponseTemplateInsert,
    db: DbSession,
    current_user: CurrentUser,
):
    template, suggestion = insert_template_into_reply_suggestion(db, organization_id, template_id, current_user, payload)
    return {"template": template, "suggestion": suggestion}
