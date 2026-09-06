"""Integration tests for profile and events list endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_redis_dep
from app.core.database import get_db
from app.core.redis_client import create_redis_client
from app.main import app
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

REGISTER_PAYLOAD = {
    "email": "events@example.com",
    "password": "Password1!",
    "studio_name": "Events Studio",
    "phone": "+919876543211",
}


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator:
    """Dedicated Redis client flushed before each test."""
    client = create_redis_client()
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest_asyncio.fixture
async def authed_client(db_session, redis_client) -> AsyncIterator[AsyncClient]:
    """Authenticated HTTP client after registration OTP verification."""

    async def override_get_db() -> AsyncIterator:
        yield db_session

    async def override_get_redis() -> AsyncIterator:
        yield redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_dep] = override_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        register = await http_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
        assert register.status_code == 201

        otp_service = OTPService(redis_client, SMSService())
        otp = await otp_service.peek_otp(REGISTER_PAYLOAD["phone"], "registration")
        assert otp is not None

        verify = await http_client.post(
            "/api/v1/auth/verify-otp",
            json={
                "phone": REGISTER_PAYLOAD["phone"],
                "otp": otp,
                "purpose": "registration",
            },
        )
        assert verify.status_code == 200
        tokens = verify.json()
        http_client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})
        yield http_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_profile_returns_authenticated_photographer(authed_client: AsyncClient) -> None:
    """Profile endpoint returns the logged-in photographer."""
    response = await authed_client.get("/api/v1/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]
    assert body["phone_verified"] is True


@pytest.mark.asyncio
async def test_create_list_and_get_event(authed_client: AsyncClient) -> None:
    """Photographers can create an event, list it, and fetch detail."""
    create = await authed_client.post(
        "/api/v1/events",
        json={
            "name": "Rahul & Priya Wedding",
            "date_start": "2026-11-15",
            "event_type": "wedding",
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["name"] == "Rahul & Priya Wedding"
    assert body["status"] == "draft"
    assert body["slug"]
    event_id = body["id"]

    listed = await authed_client.get("/api/v1/events")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["events"][0]["id"] == event_id

    detail = await authed_client.get(f"/api/v1/events/{event_id}")
    assert detail.status_code == 200
    assert "/event/" in detail.json()["master_link_url"]

    folders = await authed_client.get(f"/api/v1/events/{event_id}/folders")
    assert folders.status_code == 200
    assert folders.json()["folders"] == []

    photos = await authed_client.get(f"/api/v1/events/{event_id}/photos")
    assert photos.status_code == 200
    assert photos.json()["items"] == []
