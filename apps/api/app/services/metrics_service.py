from __future__ import annotations

from datetime import UTC, datetime
from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AuthenticatedUser
from app.models.ai_triage_result import AITriageResult
from app.models.gmail_connection import GmailConnection
from app.models.gmail_sync_event import GmailSyncEvent
from app.models.job_run import JobRun
from app.models.member import MemberRole
from app.models.reply_suggestion import ReplySuggestion
from app.models.ticket import Ticket, TicketStatus, TicketTriageStatus
from app.models.ticket_event import TicketEvent
from app.schemas.metrics import (
    AIQualityAnalyticsRead,
    AdminAnalyticsRead,
    AgentWorkloadRead,
    GmailSyncAnalyticsRead,
    MetricsOverviewRead,
    SupportPerformanceAnalyticsRead,
)
from app.services.rbac_service import require_membership, require_role

ACTIVE_STATUSES = {
    TicketStatus.NEW.value,
    TicketStatus.OPEN.value,
    TicketStatus.PENDING.value,
    TicketStatus.AWAITING_APPROVAL.value,
    TicketStatus.DRAFT_CREATED.value,
}
FIRST_REVIEW_EVENTS = {
    "ticket.updated",
    "ticket.assigned",
    "ticket.reply_suggestion_edited",
    "ticket.reply_suggestion_approved",
    "ticket.reply_suggestion_rejected",
    "ticket.reply_draft_created",
    "ticket.resolved",
    "ticket.marked_spam",
}


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _minutes_between(start: datetime | None, end: datetime | None) -> float | None:
    start = _aware(start)
    end = _aware(end)
    if start is None or end is None or end < start:
        return None
    return round((end - start).total_seconds() / 60, 2)


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _count_rows(rows: list[tuple[Any, int]]) -> dict[str, int]:
    return {str(key): int(count) for key, count in rows if key is not None}


def get_metrics_overview(db: Session, organization_id: str, actor: AuthenticatedUser) -> MetricsOverviewRead:
    require_membership(db, organization_id, actor)

    status_rows = db.execute(
        select(Ticket.status, func.count(Ticket.id))
        .where(Ticket.organization_id == organization_id)
        .group_by(Ticket.status)
    ).all()
    priority_rows = db.execute(
        select(Ticket.priority, func.count(Ticket.id))
        .where(Ticket.organization_id == organization_id)
        .group_by(Ticket.priority)
    ).all()

    by_status = _count_rows(status_rows)
    by_priority = _count_rows(priority_rows)

    return MetricsOverviewRead(
        total_tickets=sum(by_status.values()),
        active_tickets=sum(by_status.get(status, 0) for status in ACTIVE_STATUSES),
        resolved_tickets=by_status.get(TicketStatus.RESOLVED.value, 0),
        spam_tickets=by_status.get(TicketStatus.SPAM.value, 0),
        critical_tickets=by_priority.get("critical", 0),
        high_priority_tickets=by_priority.get("high", 0),
        draft_created_tickets=by_status.get(TicketStatus.DRAFT_CREATED.value, 0),
        by_status=by_status,
        by_priority=by_priority,
    )


def get_admin_analytics(db: Session, organization_id: str, actor: AuthenticatedUser) -> AdminAnalyticsRead:
    require_role(db, organization_id, actor, {MemberRole.OWNER, MemberRole.ADMIN})
    return AdminAnalyticsRead(
        support=_support_performance(db, organization_id),
        ai_quality=_ai_quality(db, organization_id),
        gmail_sync=_gmail_sync(db, organization_id),
        notes=[
            "AI quality metrics describe workflow quality signals, not model accuracy against a labeled evaluation set.",
            "Average change level is derived from reply suggestion edit status until exact text-distance tracking is added.",
        ],
    )


def _support_performance(db: Session, organization_id: str) -> SupportPerformanceAnalyticsRead:
    tickets = list(db.scalars(select(Ticket).where(Ticket.organization_id == organization_id)))
    ticket_ids = [ticket.id for ticket in tickets]
    category_rows = db.execute(
        select(Ticket.category, func.count(Ticket.id))
        .where(Ticket.organization_id == organization_id)
        .group_by(Ticket.category)
    ).all()
    priority_rows = db.execute(
        select(Ticket.priority, func.count(Ticket.id))
        .where(Ticket.organization_id == organization_id)
        .group_by(Ticket.priority)
    ).all()

    first_review_by_ticket: dict[str, datetime] = {}
    resolved_by_ticket: dict[str, datetime] = {}
    reopened_ticket_ids: set[str] = set()
    if ticket_ids:
        events = list(
            db.scalars(
                select(TicketEvent)
                .where(TicketEvent.organization_id == organization_id, TicketEvent.ticket_id.in_(ticket_ids))
                .order_by(TicketEvent.created_at.asc())
            )
        )
        for event in events:
            if event.event_type in FIRST_REVIEW_EVENTS and event.ticket_id not in first_review_by_ticket:
                first_review_by_ticket[event.ticket_id] = event.created_at
            if event.event_type == "ticket.resolved" and event.ticket_id not in resolved_by_ticket:
                resolved_by_ticket[event.ticket_id] = event.created_at
            changes = event.event_metadata.get("changes", {}) if isinstance(event.event_metadata, dict) else {}
            status_change = changes.get("status") if isinstance(changes, dict) else None
            if isinstance(status_change, dict) and status_change.get("from") == TicketStatus.RESOLVED.value:
                reopened_ticket_ids.add(event.ticket_id)

    first_review_minutes = [
        value
        for ticket in tickets
        if (value := _minutes_between(ticket.created_at, first_review_by_ticket.get(ticket.id))) is not None
    ]
    resolution_minutes = [
        value
        for ticket in tickets
        if ticket.status == TicketStatus.RESOLVED.value
        if (value := _minutes_between(ticket.created_at, resolved_by_ticket.get(ticket.id) or ticket.updated_at)) is not None
    ]

    suggestions = list(
        db.scalars(select(ReplySuggestion).where(ReplySuggestion.organization_id == organization_id))
    )
    approval_wait_minutes = [
        value
        for suggestion in suggestions
        if suggestion.approved_at is not None
        if (value := _minutes_between(suggestion.created_at, suggestion.approved_at)) is not None
    ]

    resolved_tickets = [ticket for ticket in tickets if ticket.status == TicketStatus.RESOLVED.value]
    sla_met = sum(
        1
        for ticket in resolved_tickets
        if ticket.resolution_due_at is None or (_aware(ticket.updated_at) is not None and _aware(ticket.updated_at) <= _aware(ticket.resolution_due_at))
    )

    workload_rows = db.execute(
        select(Ticket.assigned_to_user_id, func.count(Ticket.id))
        .where(Ticket.organization_id == organization_id, Ticket.assigned_to_user_id.is_not(None))
        .group_by(Ticket.assigned_to_user_id)
    ).all()
    active_workload_rows = db.execute(
        select(Ticket.assigned_to_user_id, func.count(Ticket.id))
        .where(
            Ticket.organization_id == organization_id,
            Ticket.assigned_to_user_id.is_not(None),
            Ticket.status.in_(ACTIVE_STATUSES),
        )
        .group_by(Ticket.assigned_to_user_id)
    ).all()
    active_workload = {str(user_id): int(count) for user_id, count in active_workload_rows if user_id is not None}
    workload = [
        AgentWorkloadRead(
            user_id=str(user_id),
            total_assigned_tickets=int(total),
            open_tickets=active_workload.get(str(user_id), 0),
        )
        for user_id, total in workload_rows
        if user_id is not None
    ]

    return SupportPerformanceAnalyticsRead(
        ticket_volume=len(tickets),
        by_category=_count_rows(category_rows),
        by_priority=_count_rows(priority_rows),
        first_review_time_avg_minutes=round(mean(first_review_minutes), 2) if first_review_minutes else None,
        resolution_time_avg_minutes=round(mean(resolution_minutes), 2) if resolution_minutes else None,
        approval_wait_time_avg_minutes=round(mean(approval_wait_minutes), 2) if approval_wait_minutes else None,
        sla_attainment_rate=_rate(sla_met, len(resolved_tickets)) if resolved_tickets else None,
        agent_workload=workload,
        reopen_rate=_rate(len(reopened_ticket_ids), len(tickets)),
        reopened_tickets=len(reopened_ticket_ids),
    )


def _ai_quality(db: Session, organization_id: str) -> AIQualityAnalyticsRead:
    total_tickets = db.scalar(select(func.count(Ticket.id)).where(Ticket.organization_id == organization_id)) or 0
    triaged_tickets = db.scalar(
        select(func.count(Ticket.id)).where(
            Ticket.organization_id == organization_id,
            Ticket.triage_status == TicketTriageStatus.TRIAGED.value,
        )
    ) or 0
    confidence_scores = list(
        db.scalars(select(AITriageResult.confidence_score).where(AITriageResult.organization_id == organization_id))
    )
    distribution = {"0-40": 0, "41-70": 0, "71-90": 0, "91-100": 0}
    for score in confidence_scores:
        if score <= 40:
            distribution["0-40"] += 1
        elif score <= 70:
            distribution["41-70"] += 1
        elif score <= 90:
            distribution["71-90"] += 1
        else:
            distribution["91-100"] += 1

    events = list(db.scalars(select(TicketEvent).where(TicketEvent.organization_id == organization_id)))
    category_corrections = 0
    priority_corrections = 0
    rejected_reasons: dict[str, int] = {}
    for event in events:
        metadata = event.event_metadata if isinstance(event.event_metadata, dict) else {}
        changes = metadata.get("changes") if isinstance(metadata, dict) else None
        if isinstance(changes, dict):
            if "category" in changes:
                category_corrections += 1
            if "priority" in changes:
                priority_corrections += 1
        if event.event_type == "ticket.reply_suggestion_rejected":
            reason = str(metadata.get("reason") or "unspecified")
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

    suggestions = list(db.scalars(select(ReplySuggestion).where(ReplySuggestion.organization_id == organization_id)))
    approved = sum(1 for suggestion in suggestions if suggestion.status in {"approved", "draft_created"})
    edited = sum(1 for suggestion in suggestions if suggestion.status == "edited" or suggestion.edited_body)
    rejected = sum(1 for suggestion in suggestions if suggestion.status == "rejected")
    if edited == 0:
        change_level = "none"
    elif edited / max(len(suggestions), 1) < 0.34:
        change_level = "low"
    elif edited / max(len(suggestions), 1) < 0.67:
        change_level = "medium"
    else:
        change_level = "high"
    if rejected and not rejected_reasons:
        rejected_reasons["unspecified"] = rejected

    latencies = [
        value
        for value in db.scalars(
            select(AITriageResult.latency_ms).where(
                AITriageResult.organization_id == organization_id,
                AITriageResult.latency_ms.is_not(None),
            )
        )
        if value is not None
    ]
    ai_jobs_total = db.scalar(
        select(func.count(JobRun.id)).where(JobRun.organization_id == organization_id, JobRun.job_type == "ai_triage")
    ) or 0
    ai_jobs_failed = db.scalar(
        select(func.count(JobRun.id)).where(
            JobRun.organization_id == organization_id,
            JobRun.job_type == "ai_triage",
            JobRun.status == "failed",
        )
    ) or 0

    return AIQualityAnalyticsRead(
        triage_completion_rate=_rate(int(triaged_tickets), int(total_tickets)),
        confidence_distribution=distribution,
        average_confidence_score=round(mean(confidence_scores), 2) if confidence_scores else None,
        agent_category_corrections=category_corrections,
        agent_priority_corrections=priority_corrections,
        reply_approval_rate=_rate(approved, len(suggestions)),
        average_change_level=change_level,
        rejected_suggestion_reasons=rejected_reasons,
        provider_latency_avg_ms=round(mean(latencies), 2) if latencies else None,
        provider_failure_rate=_rate(int(ai_jobs_failed), int(ai_jobs_total)),
    )


def _gmail_sync(db: Session, organization_id: str) -> GmailSyncAnalyticsRead:
    events = list(db.scalars(select(GmailSyncEvent).where(GmailSyncEvent.organization_id == organization_id)))
    by_status: dict[str, int] = {}
    for event in events:
        by_status[event.status] = by_status.get(event.status, 0) + 1

    durations = [event.duration_ms for event in events if event.duration_ms is not None]
    if not durations:
        durations = [
            int((_aware(event.completed_at) - _aware(event.started_at)).total_seconds() * 1000)
            for event in events
            if _aware(event.started_at) is not None and _aware(event.completed_at) is not None and _aware(event.completed_at) >= _aware(event.started_at)
        ]

    reauth_connections = db.scalar(
        select(func.count(GmailConnection.id)).where(
            GmailConnection.organization_id == organization_id,
            GmailConnection.status == "reauthorization_required",
        )
    ) or 0

    return GmailSyncAnalyticsRead(
        notifications_received=sum(1 for event in events if event.trigger_type == "pubsub_notification"),
        incremental_sync_success=sum(
            1 for event in events if event.trigger_type in {"history_sync", "pubsub_notification", "manual_history_sync"} and event.status == "succeeded"
        ),
        fallback_recoveries=sum(1 for event in events if event.trigger_type == "fallback_sync" and event.status == "succeeded"),
        reconciliation_count=sum(1 for event in events if event.trigger_type == "reconciliation"),
        duplicate_skip_count=sum(event.messages_skipped for event in events),
        sync_latency_avg_ms=round(mean(durations), 2) if durations else None,
        watch_renewal_success=sum(1 for event in events if event.trigger_type == "watch_renewal" and event.status == "succeeded"),
        reauthorization_count=int(reauth_connections),
        by_status=by_status,
    )
