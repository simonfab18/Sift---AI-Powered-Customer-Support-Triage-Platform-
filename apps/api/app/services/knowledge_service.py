from dataclasses import dataclass
from datetime import UTC, datetime
import re

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.knowledge import KnowledgeSource, KnowledgeStatus, KnowledgeUsageEvent
from app.models.member import MemberRole
from app.schemas.knowledge import KnowledgeSourceCreate, KnowledgeSourceUpdate
from app.services.rbac_service import require_membership, require_role

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")


@dataclass(frozen=True)
class RetrievedKnowledgeSource:
    source: KnowledgeSource
    score: int
    matched_terms: list[str]

    def as_reference(self) -> dict:
        excerpt = self.source.body.strip().replace("\n", " ")[:240]
        return {
            "id": self.source.id,
            "title": self.source.title,
            "source_type": self.source.source_type,
            "score": self.score,
            "matched_terms": self.matched_terms,
            "excerpt": excerpt,
        }


def utc_now() -> datetime:
    return datetime.now(UTC)


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in TOKEN_PATTERN.finditer(text.lower())}


def _is_effective(source: KnowledgeSource, now: datetime) -> bool:
    if source.status != KnowledgeStatus.ACTIVE.value:
        return False
    if source.effective_from is not None and source.effective_from > now:
        return False
    if source.effective_until is not None and source.effective_until <= now:
        return False
    return True


def list_knowledge_sources(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    include_archived: bool = False,
) -> list[KnowledgeSource]:
    require_membership(db, organization_id, actor)
    statement = select(KnowledgeSource).where(KnowledgeSource.organization_id == organization_id)
    if not include_archived:
        statement = statement.where(KnowledgeSource.status == KnowledgeStatus.ACTIVE.value)
    return list(db.scalars(statement.order_by(KnowledgeSource.updated_at.desc())))


def create_knowledge_source(
    db: Session,
    organization_id: str,
    actor: AuthenticatedUser,
    payload: KnowledgeSourceCreate,
) -> KnowledgeSource:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    source = KnowledgeSource(
        organization_id=organization_id,
        title=payload.title,
        body=payload.body,
        source_type=payload.source_type,
        owner_user_id=actor.id,
        effective_from=payload.effective_from,
        effective_until=payload.effective_until,
        source_metadata=payload.source_metadata,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def update_knowledge_source(
    db: Session,
    organization_id: str,
    source_id: str,
    actor: AuthenticatedUser,
    payload: KnowledgeSourceUpdate,
) -> KnowledgeSource:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    source = db.get(KnowledgeSource, source_id)
    if source is None or source.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value.value if hasattr(value, "value") else value)
    if source.status == KnowledgeStatus.ARCHIVED.value and source.archived_at is None:
        source.archived_at = utc_now()
    if source.status == KnowledgeStatus.ACTIVE.value:
        source.archived_at = None
    db.commit()
    db.refresh(source)
    return source


def archive_knowledge_source(
    db: Session,
    organization_id: str,
    source_id: str,
    actor: AuthenticatedUser,
) -> KnowledgeSource:
    return update_knowledge_source(
        db,
        organization_id,
        source_id,
        actor,
        KnowledgeSourceUpdate(status=KnowledgeStatus.ARCHIVED),
    )


def retrieve_knowledge_sources(
    db: Session,
    organization_id: str,
    query: str,
    limit: int = 3,
) -> list[RetrievedKnowledgeSource]:
    now = utc_now()
    query_terms = _tokens(query)
    if not query_terms:
        return []

    candidates = db.scalars(
        select(KnowledgeSource).where(
            KnowledgeSource.organization_id == organization_id,
            KnowledgeSource.status == KnowledgeStatus.ACTIVE.value,
            or_(KnowledgeSource.effective_from.is_(None), KnowledgeSource.effective_from <= now),
            or_(KnowledgeSource.effective_until.is_(None), KnowledgeSource.effective_until > now),
        )
    ).all()
    ranked: list[RetrievedKnowledgeSource] = []
    for source in candidates:
        if not _is_effective(source, now):
            continue
        source_terms = _tokens(f"{source.title} {source.body}")
        matched_terms = sorted(query_terms & source_terms)
        if not matched_terms:
            continue
        title_terms = _tokens(source.title)
        score = len(matched_terms) + len(query_terms & title_terms)
        ranked.append(RetrievedKnowledgeSource(source=source, score=score, matched_terms=matched_terms))
    return sorted(ranked, key=lambda item: (-item.score, item.source.updated_at), reverse=False)[:limit]


def record_knowledge_usage(
    db: Session,
    ticket_id: str,
    ai_triage_result_id: str,
    prompt_version: str,
    retrieved_sources: list[RetrievedKnowledgeSource],
) -> None:
    for retrieved in retrieved_sources:
        db.add(
            KnowledgeUsageEvent(
                organization_id=retrieved.source.organization_id,
                knowledge_source_id=retrieved.source.id,
                ticket_id=ticket_id,
                ai_triage_result_id=ai_triage_result_id,
                prompt_version=prompt_version,
                score=retrieved.score,
                matched_terms=retrieved.matched_terms,
            )
        )
