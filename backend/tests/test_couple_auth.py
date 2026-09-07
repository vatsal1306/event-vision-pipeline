"""Tests for couple authentication (BE-012)."""

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
from app.models.couple_session import CoupleSession
from app.models.enums import EventStatus
from app.models.event import Event
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


async def create_test_event(db: AsyncSession, master_link_active: bool = True) -> Event:
    photographer = Photographer(
        email=f"coupleauth_{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        studio_name="Couple Auth Studio",
        phone=f"+9199{uuid.uuid4().hex[:8]}",
        phone_verified=True,
    )
    db.add(photographer)
    await db.commit()
    await db.refresh(photographer)

    event = Event(
        photographer_id=photographer.id,
        name="Test Couple Auth Event",
        slug=f"coupleauth-{uuid.uuid4().hex[:8]}",
        status=EventStatus.READY,
        guest_link_active=True,
        master_link_active=master_link_active,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    return event


@pytest.mark.asyncio
async def test_couple_request_auth_success(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: redis.Redis,
) -> None:
    """Test successful OTP request for couple."""
    event = await create_test_event(db_session)
    phone = "+919988776655"

    response = await api_client.post(
        f"/api/v1/event/{event.slug}/master/auth",
        json={"name": "Test Couple", "phone": phone},
    )
    assert response.status_code == 204

    # Check OTP is in Redis
    otp = await redis_client.get(f"otp:{phone}:couple_auth")
    assert otp is not None


@pytest.mark.asyncio
async def test_couple_request_auth_inactive_link(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test OTP request fails if master link is inactive."""
    event = await create_test_event(db_session, master_link_active=False)

    response = await api_client.post(
        f"/api/v1/event/{event.slug}/master/auth",
        json={"name": "Test Couple", "phone": "+919988776655"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Master link is inactive"


@pytest.mark.asyncio
async def test_couple_verify_auth_success(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: redis.Redis,
) -> None:
    """Test successful OTP verification and token issuance for couple."""
    event = await create_test_event(db_session)
    phone = "+919988776655"

    # Step 1: Request auth
    await api_client.post(
        f"/api/v1/event/{event.slug}/master/auth",
        json={"name": "Test Couple", "phone": phone},
    )

    otp = await redis_client.get(f"otp:{phone}:couple_auth")
    assert otp is not None
    otp_val = str(otp)

    # Step 2: Verify auth
    response = await api_client.post(
        f"/api/v1/event/{event.slug}/master/verify",
        json={"name": "Test Couple", "phone": phone, "otp": otp_val},
    )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data

    # Check session is created and verified
    from sqlalchemy import select

    result = await db_session.execute(select(CoupleSession).where(CoupleSession.phone == phone))
    session = result.scalar_one()
    assert session.name == "Test Couple"
    assert session.phone_verified is True


@pytest.mark.asyncio
async def test_couple_verify_auth_invalid_otp(
    api_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test OTP verification fails with incorrect OTP."""
    event = await create_test_event(db_session)
    phone = "+919988776655"

    await api_client.post(
        f"/api/v1/event/{event.slug}/master/auth",
        json={"name": "Test Couple", "phone": phone},
    )

    response = await api_client.post(
        f"/api/v1/event/{event.slug}/master/verify",
        json={"name": "Test Couple", "phone": phone, "otp": "000000"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "AUTH_FAILED"
