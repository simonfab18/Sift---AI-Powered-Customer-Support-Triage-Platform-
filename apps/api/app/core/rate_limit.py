from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from threading import Lock

from fastapi import HTTPException, status

from app.core.config import settings


@dataclass
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._buckets: dict[str, tuple[float, int]] = {}

    def check(self, key: str, *, limit: int, window_seconds: int) -> RateLimitResult:
        if not settings.rate_limit_enabled:
            return RateLimitResult(allowed=True, retry_after_seconds=0)
        now = monotonic()
        with self._lock:
            window_start, count = self._buckets.get(key, (now, 0))
            elapsed = now - window_start
            if elapsed >= window_seconds:
                self._buckets[key] = (now, 1)
                return RateLimitResult(allowed=True, retry_after_seconds=0)
            if count >= limit:
                retry_after = max(1, int(window_seconds - elapsed))
                return RateLimitResult(allowed=False, retry_after_seconds=retry_after)
            self._buckets[key] = (window_start, count + 1)
            return RateLimitResult(allowed=True, retry_after_seconds=0)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = InMemoryRateLimiter()


def enforce_rate_limit(
    key: str,
    *,
    limit: int | None = None,
    window_seconds: int | None = None,
) -> None:
    resolved_limit = limit or settings.rate_limit_default_limit
    resolved_window = window_seconds or settings.rate_limit_default_window_seconds
    result = rate_limiter.check(key, limit=resolved_limit, window_seconds=resolved_window)
    if result.allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Try again later.",
        headers={"Retry-After": str(result.retry_after_seconds)},
    )
