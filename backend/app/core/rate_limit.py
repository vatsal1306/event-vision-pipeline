"""Redis-backed sliding window rate limiter."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import redis.asyncio as redis
from fastapi import Depends, Request

from app.api.deps import get_redis_dep
from app.config import get_settings
from app.core.exceptions import RateLimitedError


class RateLimiter:
    """Redis-backed sliding window rate limiter."""

    def __init__(self, redis_client: redis.Redis) -> None:
        self.redis = redis_client

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        now = time.time()
        pipe = self.redis.pipeline()

        # Remove old requests
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Count requests in window
        pipe.zcard(key)
        # Extend key expiry
        pipe.expire(key, window_seconds)

        results = await pipe.execute()
        request_count = results[2]

        return int(request_count) <= limit


def get_client_ip(request: Request) -> str:
    """Extract client IP respecting trusted proxies."""
    settings = get_settings()
    forwarded_for = request.headers.get("X-Forwarded-For")

    if forwarded_for and request.client and request.client.host in settings.trusted_proxies:
        # X-Forwarded-For can contain multiple IPs. The left-most is the original client.
        return forwarded_for.split(",")[0].strip()

    return request.client.host if request.client else "127.0.0.1"


def rate_limit(group: str, limit: int, window: int) -> Callable[..., Any]:
    """Dependency that enforces rate limits."""

    async def _dependency(
        request: Request,
        redis_client: redis.Redis = Depends(get_redis_dep),
    ) -> None:
        limiter = RateLimiter(redis_client)
        client_ip = get_client_ip(request)

        # Try to extract the photographer subject directly from the auth header, if present
        subject = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                from app.core.security import decode_jwt

                payload = decode_jwt(token)
                if payload.get("type") == "access":
                    subject = payload.get("sub")
            except Exception:
                pass  # Do not fail on invalid tokens here; let the actual auth dependency handle it

        key = f"rl:{group}:{subject or client_ip}"

        if not await limiter.check(key, limit, window):
            raise RateLimitedError(f"Rate limit exceeded for {group}")

    return _dependency
