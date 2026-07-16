"""Lightweight in-memory rate limiter.

# ponytail: in-memory, single-process only; move to a shared store if gunicorn workers > 1

Provides:
  * rate_limit decorator for per-route overrides
  * should_rate_limit(key, limit, window) primitive
  * integration helpers for Flask before_request

Design:
  - Fixed window counters (epoch // window) stored in dict.
  - Thread-safe via Lock (sufficient for eventlet/gevent monkey-patched threads in this project).
  - Not persistent; resets on process restart (acceptable for abuse throttling baseline).
  - Keys include user id (if authenticated) else remote addr to reduce cross-user impact.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from functools import wraps
from threading import Lock
from typing import Callable, Optional

_lock = Lock()
_counters: dict[tuple[str, int], int] = {}


@dataclass
class RateLimitSpec:
    limit: int
    window: int  # seconds


def _bucket(now: float, window: int) -> int:
    return int(now // window)


def should_rate_limit(key: str, limit: int, window: int) -> tuple[bool, int]:
    """Increment and evaluate limit state.

    Returns (limited, remaining_seconds_till_reset)
    """
    now = time.time()
    bucket = _bucket(now, window)
    k = (key, bucket)
    with _lock:
        count = _counters.get(k, 0) + 1
        _counters[k] = count
        # Opportunistic cleanup of previous bucket to keep dict bounded
        old_k = (key, bucket - 1)
        _counters.pop(old_k, None)
    limited = count > limit
    reset_in = window - int(now - bucket * window)
    if reset_in < 0:
        reset_in = 0
    return limited, reset_in


def rate_limit(limit: int, window: int):
    """Decorator to set a custom rate limit spec on a view function."""

    def decorator(fn: Callable):
        setattr(fn, "_rate_limit_spec", RateLimitSpec(limit=limit, window=window))

        @wraps(fn)
        def wrapper(*args, **kwargs):  # pragma: no cover - actual limiting done in before_request
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def resolve_spec(view_func) -> Optional[RateLimitSpec]:  # pragma: no cover - trivial
    return getattr(view_func, "_rate_limit_spec", None)
