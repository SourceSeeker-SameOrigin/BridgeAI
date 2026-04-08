"""
Rate limiting middleware using Redis token bucket algorithm.

Tiers:
  - free:       60 requests/minute
  - pro:       300 requests/minute
  - enterprise: 1000 requests/minute
  - default:    60 requests/minute (no API key / unknown tier)

Rate limiting is applied per API key (from Authorization header) or per
client IP when no API key is present.
"""

import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Tier -> (max_tokens, refill_rate_per_second)
_TIER_LIMITS: dict[str, tuple[int, float]] = {
    "free": (60, 1.0),           # 60 req/min -> 1/sec
    "pro": (300, 5.0),           # 300 req/min -> 5/sec
    "enterprise": (1000, 16.67), # 1000 req/min -> ~16.67/sec
}

_DEFAULT_LIMIT = _TIER_LIMITS["free"]

# Paths exempt from rate limiting
_EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based token bucket rate limiter.

    Uses two Redis keys per client:
      - ratelimit:{key}:tokens  (remaining tokens as float)
      - ratelimit:{key}:ts      (last refill timestamp)

    On each request, tokens are refilled based on elapsed time,
    then 1 token is consumed. If tokens < 0, return 429.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path.rstrip("/") or "/"

        # Skip rate limiting for exempt paths
        if path in _EXEMPT_PATHS:
            return await call_next(request)

        # Determine rate limit key and tier
        rate_key, tier = self._resolve_key_and_tier(request)
        max_tokens, refill_rate = _TIER_LIMITS.get(tier, _DEFAULT_LIMIT)

        # Try Redis-based rate limiting
        try:
            from app.core.redis import get_redis
            redis = await get_redis()
            allowed, remaining = await self._check_rate_limit(
                redis, rate_key, max_tokens, refill_rate,
            )
        except Exception as e:
            # If Redis is unavailable, allow the request (fail-open)
            logger.warning("Rate limit check failed (allowing request): %s", e)
            return await call_next(request)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": "请求过于频繁，请稍后重试",
                    "data": None,
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(max_tokens),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_tokens)
        response.headers["X-RateLimit-Remaining"] = str(max(0, int(remaining)))
        return response

    def _resolve_key_and_tier(self, request: Request) -> tuple[str, str]:
        """Resolve the rate limit key and tier from the request.

        Uses API key from Authorization header if present,
        otherwise falls back to client IP.
        """
        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # Use a hash prefix for the key to avoid storing full tokens
            key = f"apikey:{token[:16]}"
            # Tier detection: check request state set by auth middleware
            tier = getattr(request.state, "tier", "free") if hasattr(request, "state") else "free"
            return key, tier

        # Fallback to client IP
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        return f"ip:{client_ip}", "free"

    async def _check_rate_limit(
        self,
        redis: Any,
        key: str,
        max_tokens: int,
        refill_rate: float,
    ) -> tuple[bool, float]:
        """Token bucket algorithm via Redis.

        Returns (allowed: bool, remaining_tokens: float).
        """
        now = time.time()
        tokens_key = f"ratelimit:{key}:tokens"
        ts_key = f"ratelimit:{key}:ts"

        # Use a Redis pipeline for atomicity
        pipe = redis.pipeline(transaction=True)
        pipe.get(tokens_key)
        pipe.get(ts_key)
        results = await pipe.execute()

        stored_tokens = float(results[0]) if results[0] is not None else float(max_tokens)
        last_ts = float(results[1]) if results[1] is not None else now

        # Refill tokens based on elapsed time
        elapsed = now - last_ts
        tokens = min(max_tokens, stored_tokens + elapsed * refill_rate)

        # Consume 1 token
        if tokens < 1.0:
            # Not enough tokens -- update Redis and reject
            pipe2 = redis.pipeline(transaction=True)
            pipe2.set(tokens_key, str(tokens), ex=120)
            pipe2.set(ts_key, str(now), ex=120)
            await pipe2.execute()
            return False, tokens

        tokens -= 1.0

        # Update Redis
        pipe2 = redis.pipeline(transaction=True)
        pipe2.set(tokens_key, str(tokens), ex=120)
        pipe2.set(ts_key, str(now), ex=120)
        await pipe2.execute()

        return True, tokens
