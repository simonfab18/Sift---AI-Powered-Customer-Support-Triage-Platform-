from collections.abc import Callable

from fastapi import Request

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.rate_limit import enforce_rate_limit


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown-client"


def _organization_key(request: Request) -> str:
    return str(request.path_params.get("organization_id") or "no-org")


def sensitive_rate_limit(action: str, *, scope: str = "user") -> Callable:
    def dependency(request: Request, current_user: CurrentUser) -> None:
        org_id = _organization_key(request)
        if scope == "organization":
            subject = org_id
        else:
            subject = f"{org_id}:{current_user.id}"
        enforce_rate_limit(
            f"{action}:{scope}:{subject}",
            limit=settings.rate_limit_sensitive_limit,
            window_seconds=settings.rate_limit_sensitive_window_seconds,
        )

    return dependency


def oauth_callback_rate_limit(request: Request) -> None:
    enforce_rate_limit(
        f"gmail_oauth_callback:ip:{_client_key(request)}",
        limit=settings.rate_limit_sensitive_limit,
        window_seconds=settings.rate_limit_sensitive_window_seconds,
    )


def oauth_start_rate_limit(request: Request, current_user: CurrentUser) -> None:
    enforce_rate_limit(
        f"gmail_oauth_start:user:{_organization_key(request)}:{current_user.id}",
        limit=settings.rate_limit_sensitive_limit,
        window_seconds=settings.rate_limit_sensitive_window_seconds,
    )


limit_gmail_sync = sensitive_rate_limit("gmail_sync", scope="organization")
limit_gmail_watch = sensitive_rate_limit("gmail_watch", scope="organization")
limit_triage = sensitive_rate_limit("triage", scope="organization")
limit_retry = sensitive_rate_limit("retry", scope="organization")
limit_draft_creation = sensitive_rate_limit("draft_creation", scope="organization")
limit_member_invite = sensitive_rate_limit("member_invite", scope="organization")

