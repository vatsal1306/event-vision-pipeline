"""Integration tests for photographer event CRUD and settings."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.deps import get_redis_dep
from app.core.database import get_db
from app.core.redis_client import create_redis_client
from app.main import app
from app.models.event import Event
from app.models.folder import Folder
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

VALID_PASSWORD = "Password1!"
PRIMARY_REGISTER = {
    "email": "events-primary@example.com",
    "password": VALID_PASSWORD,
    "studio_name": "Primary Studio",
    "phone": "+919876543220",
}
SECONDARY_REGISTER = {
    "email": "events-secondary@example.com",
    "password": VALID_PASSWORD,
    "studio_name": "Secondary Studio",
    "phone": "+919876543221",
}


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator:
    """Dedicated Redis client flushed before each event test."""
    client = create_redis_client()
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


async def _verify_registration(
    client: AsyncClient,
    redis_client,
    payload: dict,
) -> dict:
    """Register a photographer and complete OTP verification."""
    register = await client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    otp_service = OTPService(redis_client, SMSService())
    otp = await otp_service.peek_otp(payload["phone"], "registration")
    assert otp is not None

    verify = await client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": payload["phone"], "otp": otp, "purpose": "registration"},
    )
    assert verify.status_code == 200, verify.text
    return verify.json()


@pytest_asyncio.fixture
async def authed_client(db_session, redis_client) -> AsyncIterator[AsyncClient]:
    """Authenticated HTTP client for the primary photographer."""

    async def override_get_db() -> AsyncIterator:
        yield db_session

    async def override_get_redis() -> AsyncIterator:
        yield redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_dep] = override_get_redis
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        tokens = await _verify_registration(http_client, redis_client, PRIMARY_REGISTER)
        http_client.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})
        yield http_client
    app.dependency_overrides.clear()


async def _create_event(client: AsyncClient, *, name: str = "Sample Event") -> dict:
    """Create an event and return the JSON body."""
    response = await client.post(
        "/api/v1/events",
        json={
            "name": name,
            "date_start": "2026-11-15",
            "date_end": "2026-11-17",
            "event_type": "wedding",
            "description": "Outdoor ceremony",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_event_sets_defaults_and_share_urls(authed_client: AsyncClient) -> None:
    """Create returns draft status, zero counters, defaults, and share URLs."""
    body = await _create_event(authed_client)

    assert body["status"] == "draft"
    assert body["download_enabled"] is True
    assert body["master_link_active"] is True
    assert body["guest_link_active"] is True
    assert body["total_photos"] == 0
    assert body["processed_photos"] == 0
    assert body["total_faces"] == 0
    assert body["slug"]
    assert body["archive_at"]
    assert body["master_link_url"].endswith(f"/event/{body['slug']}/master")
    assert body["guest_link_url"].endswith(f"/event/{body['slug']}/guest")


@pytest.mark.asyncio
async def test_create_rejects_end_date_before_start(authed_client: AsyncClient) -> None:
    """Invalid date ranges are rejected at the API boundary."""
    response = await authed_client.post(
        "/api/v1/events",
        json={
            "name": "Bad Dates Event",
            "date_start": "2026-11-20",
            "date_end": "2026-11-15",
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_update_rejects_end_date_before_start(authed_client: AsyncClient) -> None:
    """Partial updates validate the resulting date range."""
    created = await _create_event(authed_client, name="Date Update Event")
    response = await authed_client.put(
        f"/api/v1/events/{created['id']}",
        json={"date_end": "2026-11-01"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_rename_keeps_slug(authed_client: AsyncClient) -> None:
    """Renaming an event does not change its public slug."""
    created = await _create_event(authed_client, name="Original Name")
    original_slug = created["slug"]

    updated = await authed_client.put(
        f"/api/v1/events/{created['id']}",
        json={"name": "Updated Name"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["name"] == "Updated Name"
    assert body["slug"] == original_slug


@pytest.mark.asyncio
async def test_other_photographer_event_returns_404(
    db_session,
    redis_client,
) -> None:
    """Accessing another photographer's event returns 404, not 403."""

    async def override_get_db() -> AsyncIterator:
        yield db_session

    async def override_get_redis() -> AsyncIterator:
        yield redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_dep] = override_get_redis
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            primary_tokens = await _verify_registration(client, redis_client, PRIMARY_REGISTER)
            client.headers.update({"Authorization": f"Bearer {primary_tokens['access_token']}"})
            created = await _create_event(client, name="Private Event")

            secondary_tokens = await _verify_registration(client, redis_client, SECONDARY_REGISTER)
            client.headers.update({"Authorization": f"Bearer {secondary_tokens['access_token']}"})

            response = await client.get(f"/api/v1/events/{created['id']}")
            assert response.status_code == 404
            assert response.json()["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_events_only_own(
    db_session,
    redis_client,
) -> None:
    """Listing events should only return the events owned by the authenticated photographer."""
    async def override_get_db() -> AsyncIterator:
        yield db_session

    async def override_get_redis() -> AsyncIterator:
        yield redis_client

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_dep] = override_get_redis
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            primary_tokens = await _verify_registration(client, redis_client, PRIMARY_REGISTER)
            client.headers.update({"Authorization": f"Bearer {primary_tokens['access_token']}"})
            
            own_event = await _create_event(client, name="Own Event")

            secondary_tokens = await _verify_registration(client, redis_client, SECONDARY_REGISTER)
            client.headers.update({"Authorization": f"Bearer {secondary_tokens['access_token']}"})
            
            other_event = await _create_event(client, name="Other Event")

            # Restore primary auth to check list
            client.headers.update({"Authorization": f"Bearer {primary_tokens['access_token']}"})

            response = await client.get("/api/v1/events")
            assert response.status_code == 200
            data = response.json()
            assert len(data["events"]) == 1
            assert data["events"][0]["id"] == str(own_event["id"])
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_supports_status_filter_and_sort(authed_client: AsyncClient) -> None:
    """List endpoint filters by status and sorts by name."""
    await _create_event(authed_client, name="Zulu Wedding")
    await _create_event(authed_client, name="Alpha Wedding")

    sorted_response = await authed_client.get(
        "/api/v1/events",
        params={"sort_by": "name", "sort_order": "asc"},
    )
    assert sorted_response.status_code == 200
    names = [event["name"] for event in sorted_response.json()["events"]]
    assert names == ["Alpha Wedding", "Zulu Wedding"]

    filtered = await authed_client.get("/api/v1/events", params={"status": "draft"})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 2


@pytest.mark.asyncio
async def test_update_settings_and_toggle_links(authed_client: AsyncClient) -> None:
    """Settings and link toggles update persisted flags."""
    created = await _create_event(authed_client, name="Settings Event")

    settings = await authed_client.put(
        f"/api/v1/events/{created['id']}/settings",
        json={"download_enabled": False, "guest_link_active": False},
    )
    assert settings.status_code == 200
    body = settings.json()
    assert body["download_enabled"] is False
    assert body["guest_link_active"] is False
    assert body["master_link_active"] is True

    toggle = await authed_client.put(f"/api/v1/events/{created['id']}/links/master/toggle")
    assert toggle.status_code == 200
    assert toggle.json()["master_link_active"] is False


@pytest.mark.asyncio
async def test_delete_event_cascades_child_rows(
    authed_client: AsyncClient,
    db_session,
) -> None:
    """Deleting an event removes nested folders via FK cascade."""
    created = await _create_event(authed_client, name="Delete Me")
    event_id = created["id"]

    folder = await authed_client.post(
        f"/api/v1/events/{event_id}/folders",
        json={"name": "Ceremony"},
    )
    assert folder.status_code == 201
    folder_id = folder.json()["id"]

    delete = await authed_client.delete(f"/api/v1/events/{event_id}")
    assert delete.status_code == 204

    remaining_event = await db_session.get(Event, event_id)
    assert remaining_event is None

    remaining_folder = await db_session.scalar(select(Folder).where(Folder.id == folder_id))
    assert remaining_folder is None


@pytest.mark.asyncio
async def test_unauthenticated_event_access_returns_401(client: AsyncClient) -> None:
    """Event routes require a valid access token."""
    response = await client.get(f"/api/v1/events/{uuid4()}")
    assert response.status_code == 401
