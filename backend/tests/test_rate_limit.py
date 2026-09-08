"""Tests for the Redis-backed sliding window rate limiter."""

from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import RateLimiter, rate_limit


@pytest_asyncio.fixture
async def fake_redis() -> FakeRedis:
    """Provide an isolated fake redis instance for testing the limiter."""
    client = FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.mark.asyncio
async def test_rate_limiter_logic(fake_redis: FakeRedis) -> None:
    """Test that the sliding window limiter correctly allows and blocks requests."""
    limiter = RateLimiter(fake_redis)
    key = "rl:test:127.0.0.1"
    limit = 3
    window = 1  # 1 second

    # First 3 requests should pass
    assert await limiter.check(key, limit, window) is True
    assert await limiter.check(key, limit, window) is True
    assert await limiter.check(key, limit, window) is True

    # 4th request in the same window should be blocked
    assert await limiter.check(key, limit, window) is False

    # Wait for the window to expire
    await asyncio.sleep(1.1)

    # Should be allowed again
    assert await limiter.check(key, limit, window) is True


@pytest.mark.asyncio
async def test_rate_limiter_dependency_integration(fake_redis: FakeRedis) -> None:
    """Test that the rate_limit dependency integrates with FastAPI correctly."""
    app = FastAPI()
    from app.core.exception_handlers import register_exception_handlers

    register_exception_handlers(app)

    # Override the get_redis_dep inside the rate_limit closure
    # For this test, we construct the route with a customized dependency
    @app.get("/test", dependencies=[Depends(rate_limit("test_group", limit=2, window=1))])
    async def test_route() -> dict[str, str]:
        return {"status": "ok"}

    # We need to override get_redis_dep globally since the rate_limit dependency calls get_redis_dep
    from app.api.deps import get_redis_dep

    app.dependency_overrides[get_redis_dep] = lambda: fake_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        # Request 1 (allowed)
        resp1 = await client.get("/test")
        assert resp1.status_code == 200

        # Request 2 (allowed)
        resp2 = await client.get("/test")
        assert resp2.status_code == 200

        # Request 3 (rate limited)
        resp3 = await client.get("/test")
        assert resp3.status_code == 429
        assert resp3.json()["code"] == "RATE_LIMITED"
