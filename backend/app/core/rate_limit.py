"""Small in-memory rate limiter for the public demo deployment."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import HTTPException, status

from backend.app.core.runtime_config import rate_limit_window_seconds

_BUCKETS: dict[tuple[str, str], Deque[float]] = defaultdict(deque)


def check_rate_limit(action: str, user_id: str, limit: int) -> None:
    """Raise 429 when a user exceeds an action limit in the configured window."""
    if limit <= 0:
        return

    now = time.time()
    window = rate_limit_window_seconds()
    key = (action, user_id)
    bucket = _BUCKETS[key]

    while bucket and now - bucket[0] >= window:
        bucket.popleft()

    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {action}. Please try again later.",
        )

    bucket.append(now)


def reset_rate_limits() -> None:
    _BUCKETS.clear()
