from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.ticket import Ticket, TicketStatus
from app.models.workspace_settings import WorkspaceSettings

SLA_ON_TRACK = "on_track"
SLA_WARNING = "warning"
SLA_BREACHED = "breached"
SLA_PAUSED = "paused"
PAUSED_STATUSES = {TicketStatus.PENDING.value, TicketStatus.RESOLVED.value, TicketStatus.SPAM.value}


def utc_now() -> datetime:
    return datetime.now(UTC)


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _business_window(settings: WorkspaceSettings, local_dt: datetime) -> tuple[datetime, datetime] | None:
    hours = settings.business_hours or {}
    day_key = str(local_dt.weekday())
    day_hours = hours.get(day_key) or hours.get(local_dt.strftime("%A").lower())
    if day_hours is None:
        if local_dt.weekday() >= 5:
            return None
        day_hours = {"start": "09:00", "end": "17:00"}

    start_text = day_hours.get("start", "09:00")
    end_text = day_hours.get("end", "17:00")
    start_hour, start_minute = [int(part) for part in start_text.split(":", 1)]
    end_hour, end_minute = [int(part) for part in end_text.split(":", 1)]
    start_at = local_dt.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    end_at = local_dt.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    if end_at <= start_at:
        return None
    return start_at, end_at


def add_business_minutes(start_at: datetime, minutes: int, settings: WorkspaceSettings) -> datetime:
    if minutes <= 0:
        return start_at

    tz = _timezone(settings.business_timezone)
    local_at = start_at.astimezone(tz)
    remaining = minutes
    cursor = local_at

    while remaining > 0:
        window = _business_window(settings, cursor)
        if window is None:
            cursor = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            continue

        opens_at, closes_at = window
        if cursor < opens_at:
            cursor = opens_at
        if cursor >= closes_at:
            cursor = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            continue

        available = int((closes_at - cursor).total_seconds() // 60)
        if remaining <= available:
            return (cursor + timedelta(minutes=remaining)).astimezone(UTC)
        remaining -= available
        cursor = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    return cursor.astimezone(UTC)


def initialize_ticket_sla(ticket: Ticket, settings: WorkspaceSettings) -> None:
    start_at = ticket.received_at or utc_now()
    ticket.first_review_due_at = add_business_minutes(start_at, settings.first_review_target_minutes, settings)
    ticket.resolution_due_at = add_business_minutes(start_at, settings.resolution_target_minutes, settings)
    ticket.sla_status = compute_sla_status(ticket)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def compute_sla_status(ticket: Ticket, now: datetime | None = None) -> str:
    if ticket.status in PAUSED_STATUSES:
        return SLA_PAUSED
    now = _as_utc(now or utc_now())
    due_dates = [_as_utc(due) for due in [ticket.first_review_due_at, ticket.resolution_due_at] if due is not None]
    if not due_dates:
        return SLA_ON_TRACK
    nearest_due = min(due_dates)
    if now >= nearest_due:
        return SLA_BREACHED
    warning_at = nearest_due - timedelta(minutes=30)
    if now >= warning_at:
        return SLA_WARNING
    return SLA_ON_TRACK


def refresh_ticket_sla_status(ticket: Ticket, now: datetime | None = None) -> str:
    ticket.sla_status = compute_sla_status(ticket, now)
    return ticket.sla_status

