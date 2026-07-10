from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.knowledge import KnowledgeSearchResponse, KnowledgeSourceCreate, KnowledgeSourceRead, KnowledgeSourceUpdate
from app.services.knowledge_service import (
    archive_knowledge_source,
    create_knowledge_source,
    list_knowledge_sources,
    retrieve_knowledge_sources,
    update_knowledge_source,
)

router = APIRouter(prefix="/orgs/{organization_id}/knowledge", tags=["knowledge"])


@router.get("", response_model=list[KnowledgeSourceRead])
def read_knowledge_sources(
    organization_id: str,
    db: DbSession,
    current_user: CurrentUser,
    include_archived: bool = Query(default=False),
):
    return list_knowledge_sources(db, organization_id, current_user, include_archived)


@router.post("", response_model=KnowledgeSourceRead, status_code=status.HTTP_201_CREATED)
def create_org_knowledge_source(
    organization_id: str,
    payload: KnowledgeSourceCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    return create_knowledge_source(db, organization_id, current_user, payload)


@router.patch("/{source_id}", response_model=KnowledgeSourceRead)
def update_org_knowledge_source(
    organization_id: str,
    source_id: str,
    payload: KnowledgeSourceUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    return update_knowledge_source(db, organization_id, source_id, current_user, payload)


@router.post("/{source_id}/archive", response_model=KnowledgeSourceRead)
def archive_org_knowledge_source(
    organization_id: str,
    source_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    return archive_knowledge_source(db, organization_id, source_id, current_user)


@router.get("/search", response_model=KnowledgeSearchResponse)
def search_org_knowledge_sources(
    organization_id: str,
    q: str,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=3, ge=1, le=10),
):
    list_knowledge_sources(db, organization_id, current_user)
    sources = [item.as_reference() for item in retrieve_knowledge_sources(db, organization_id, q, limit)]
    return {"sources": sources}
