# Spec: SEC-10 — Simple in-memory rate limiting middleware
"""Rate limiting for critical endpoints (login, DBA agent, NL2SQL).

Uses in-memory token bucket per IP. Resets on server restart.
For production, consider Redis/Valkey-backed limiter.
"""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Rate limits: (max_requests, window_seconds)
_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/auth/login": (5, 60),       # 5 per minute
    "/api/v1/auth/refresh": (10, 60),     # 10 per minute
    "/api/v1/dba/ask": (10, 60),          # 10 per minute
    "/api/v1/nl2sql/query": (20, 60),     # 20 per minute
}

# Token bucket: {ip:path -> (tokens, last_refill_time)}
_buckets: dict[str, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """SEC-10: Simple token bucket rate limiter."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        limit = _RATE_LIMITS.get(path)
        if limit is None:
            return await call_next(request)

        max_req, window = limit
        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{path}"
        now = time.monotonic()

        tokens, last_refill = _buckets[key]
        # Refill tokens
        elapsed = now - last_refill
        tokens = min(max_req, tokens + elapsed * (max_req / window))
        last_refill = now

        if tokens < 1:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )

        _buckets[key] = (tokens - 1, last_refill)
        return await call_next(request)
