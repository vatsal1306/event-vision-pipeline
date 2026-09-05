"""Async Redis client factory for OTP storage and JWT denylist."""

from __future__ import annotations

from collections.abc import AsyncIterator

import redis.asyncio as redis

from app.config import get_settings

_redis_client: redis.Redis | None = None


def create_redis_client(url: str | None = None) -> redis.Redis:
    """Create a Redis client with decoded string responses.

    Args:
        url: Optional Redis URL override.

    Returns:
        Async Redis client instance.
    """
    settings = get_settings()
    return redis.from_url(url or settings.redis_url, decode_responses=True)


async def get_redis() -> AsyncIterator[redis.Redis]:
    """Yield a shared Redis client for request-scoped dependencies."""
    global _redis_client
    if _redis_client is None:
        _redis_client = create_redis_client()
    yield _redis_client


async def close_redis() -> None:
    """Close the shared Redis client during application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
