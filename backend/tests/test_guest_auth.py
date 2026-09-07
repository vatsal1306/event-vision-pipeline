"""Tests for guest authentication (BE-012)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import redis.asyncio as redis
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis_dep
from app.core.redis_client import create_redis_client
from app.main import app
from app.models.enums import EventStatus
from app.models.event import Event
from app.models.guest_session import GuestSession
from app.models.photographer import Photographer


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[redis.Redis]:
    client = create_redis_client()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def api_client(
    db_client: AsyncClient, redis_client: redis.Redis
) -> AsyncIterator[AsyncClient]:
    async def override_get_redis() -> AsyncIterator[redis.Redis]:
        yield redis_client

    app.dependency_overrides[get_redis_dep] = override_get_redis
    yield db_client
    app.dependency_overrides.pop(get_redis_dep, None)


async def create_test_event(db: AsyncSession, guest_link_active: bool = True) -> Event:
    photographer = Photographer(
        email=f"guestauth_{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        studio_name="Guest Auth Studio",
        phone=f"+9199{uuid.uuid4().hex[:8]}",
        phone_verified=True,
    )
    db.add(photographer)
    await db.commit()
    await db.refresh(photographer)

    event = Event(
        photographer_id=photographer.id,
        name="Test Guest Auth Event",
        slug=f"guestauth-{uuid.uuid4().hex[:8]}",
        status=EventStatus.READY,
        guest_link_active=guest_link_active,
        master_link_active=True,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    return event


@pytest.mark.asyncio
async def test_guest_request_auth_success(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: redis.Redis,
) -> None:
    """Test successful OTP request for guest."""
    event = await create_test_event(db_session)
    phone = "+919988776655"

    response = await api_client.post(
        f"/api/v1/event/{event.slug}/auth",
        json={"name": "Test Guest", "phone": phone},
    )
    assert response.status_code == 204

    # Check OTP is in Redis
    otp = await redis_client.get(f"otp:{phone}:guest_auth")
    assert otp is not None


@pytest.mark.asyncio
async def test_guest_request_auth_inactive_link(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test OTP request fails if guest link is inactive."""
    event = await create_test_event(db_session, guest_link_active=False)

    response = await api_client.post(
        f"/api/v1/event/{event.slug}/auth",
        json={"name": "Test Guest", "phone": "+919988776655"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Guest link is inactive"


@pytest.mark.asyncio
async def test_guest_verify_auth_success(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: redis.Redis,
) -> None:
    """Test successful OTP verification and token issuance for guest."""
    event = await create_test_event(db_session)
    phone = "+919988776655"

    # Step 1: Request auth
    await api_client.post(
        f"/api/v1/event/{event.slug}/auth",
        json={"name": "Test Guest", "phone": phone},
    )

    otp = await redis_client.get(f"otp:{phone}:guest_auth")
    assert otp is not None
    otp_val = str(otp)

    # Step 2: Verify auth
    response = await api_client.post(
        f"/api/v1/event/{event.slug}/auth/verify",
        json={"phone": phone, "otp": otp_val},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["needs_selfie"] is True

    # Check session is created and verified
    from sqlalchemy import select

    result = await db_session.execute(select(GuestSession).where(GuestSession.phone == phone))
    session = result.scalar_one()
    assert session.name == "Test Guest"
    assert session.phone_verified is True
