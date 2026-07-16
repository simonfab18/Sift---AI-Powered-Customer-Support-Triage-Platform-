from pydantic import BaseModel, Field


class MetricsOverviewRead(BaseModel):
    total_tickets: int
    active_tickets: int
    resolved_tickets: int
    spam_tickets: int
    critical_tickets: int
    high_priority_tickets: int
    draft_created_tickets: int
    average_confidence_score: float | None = None
    by_status: dict[str, int]
    by_priority: dict[str, int]
    by_active_priority: dict[str, int]


class AgentWorkloadRead(BaseModel):
    user_id: str
    open_tickets: int
    total_assigned_tickets: int


class SupportPerformanceAnalyticsRead(BaseModel):
    ticket_volume: int
    by_category: dict[str, int]
    by_priority: dict[str, int]
    by_active_priority: dict[str, int]
    first_review_time_avg_minutes: float | None = None
    resolution_time_avg_minutes: float | None = None
    approval_wait_time_avg_minutes: float | None = None
    sla_attainment_rate: float | None = None
    agent_workload: list[AgentWorkloadRead]
    reopen_rate: float
    reopened_tickets: int


class AIQualityAnalyticsRead(BaseModel):
    triage_completion_rate: float
    confidence_distribution: dict[str, int]
    average_confidence_score: float | None = None
    agent_category_corrections: int
    agent_priority_corrections: int
    reply_approval_rate: float
    average_change_level: str
    rejected_suggestion_reasons: dict[str, int]
    provider_latency_avg_ms: float | None = None
    provider_failure_rate: float


class GmailSyncAnalyticsRead(BaseModel):
    notifications_received: int
    incremental_sync_success: int
    fallback_recoveries: int
    reconciliation_count: int
    duplicate_skip_count: int
    sync_latency_avg_ms: float | None = None
    watch_renewal_success: int
    reauthorization_count: int
    by_status: dict[str, int]


class AdminAnalyticsRead(BaseModel):
    support: SupportPerformanceAnalyticsRead
    ai_quality: AIQualityAnalyticsRead
    gmail_sync: GmailSyncAnalyticsRead
    notes: list[str] = Field(default_factory=list)

