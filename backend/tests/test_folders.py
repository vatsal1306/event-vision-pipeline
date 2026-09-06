"""Integration tests for nested event folders (BE-006)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_redis_dep
from app.core.database import get_db
from app.core.redis_client import create_redis_client
from app.main import app
from app.models.folder import Folder
from app.models.photo import Photo
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

VALID_PASSWORD = "Password1!"
PRIMARY_REGISTER = {
    "email": "folders-primary@example.com",
    "password": VALID_PASSWORD,
    "studio_name": "Folders Studio",
    "phone": "+919876543110",
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


async def _create_event(client: AsyncClient) -> dict:
    """Create an event and return the JSON body."""
    response = await client.post(
        "/api/v1/events",
        json={
            "name": "Folder Test Event",
            "date_start": "2026-11-15",
            "date_end": "2026-11-17",
            "event_type": "wedding",
            "description": "Folder hierarchy testing",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_nested_folders(authed_client: AsyncClient) -> None:
    """Creates root and child folders, and verifies the nested tree structure."""
    event = await _create_event(authed_client)
    event_id = event["id"]

    root_resp = await authed_client.post(
        f"/api/v1/events/{event_id}/folders",
        json={"name": "Root Folder"},
    )
    assert root_resp.status_code == 201
    root = root_resp.json()
    assert root["parent_id"] is None
    assert root["name"] == "Root Folder"

    child_resp = await authed_client.post(
        f"/api/v1/events/{event_id}/folders",
        json={"name": "Child Folder", "parent_id": root["id"]},
    )
    assert child_resp.status_code == 201
    child = child_resp.json()
    assert child["parent_id"] == root["id"]
    assert child["name"] == "Child Folder"

    tree_resp = await authed_client.get(f"/api/v1/events/{event_id}/folders")
    assert tree_resp.status_code == 200
    tree = tree_resp.json()["folders"]

    assert len(tree) == 1
    assert tree[0]["id"] == root["id"]
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["id"] == child["id"]


@pytest.mark.asyncio
async def test_folder_unique_sibling_names(authed_client: AsyncClient) -> None:
    """Unique constraints enforce no duplicate names among siblings."""
    event = await _create_event(authed_client)
    event_id = event["id"]

    await authed_client.post(f"/api/v1/events/{event_id}/folders", json={"name": "Duplicates"})

    dup_root = await authed_client.post(
        f"/api/v1/events/{event_id}/folders",
        json={"name": "Duplicates"},
    )
    assert dup_root.status_code == 409
    assert dup_root.json()["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_folder_max_depth(authed_client: AsyncClient) -> None:
    """Prevents nesting beyond MAX_FOLDER_DEPTH (10)."""
    event = await _create_event(authed_client)
    event_id = event["id"]

    parent_id = None
    for i in range(10):
        resp = await authed_client.post(
            f"/api/v1/events/{event_id}/folders",
            json={"name": f"Level {i + 1}", "parent_id": parent_id},
        )
        assert resp.status_code == 201, resp.text
        parent_id = resp.json()["id"]

    # Level 11 should fail
    resp_fail = await authed_client.post(
        f"/api/v1/events/{event_id}/folders",
        json={"name": "Level 11", "parent_id": parent_id},
    )
    assert resp_fail.status_code == 409
    assert resp_fail.json()["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_folder_cycle_prevention(authed_client: AsyncClient) -> None:
    """Prevents reparenting a folder under its own descendant."""
    event = await _create_event(authed_client)
    event_id = event["id"]

    p = await authed_client.post(f"/api/v1/events/{event_id}/folders", json={"name": "Parent"})
    parent_id = p.json()["id"]

    c = await authed_client.post(
        f"/api/v1/events/{event_id}/folders",
        json={"name": "Child", "parent_id": parent_id},
    )
    child_id = c.json()["id"]

    # Try to reparent Parent under Child
    update = await authed_client.put(
        f"/api/v1/events/{event_id}/folders/{parent_id}",
        json={"parent_id": child_id},
    )
    assert update.status_code == 409
    assert update.json()["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_delete_folder_photos_null(authed_client: AsyncClient, db_session) -> None:
    """Deleting folder without delete_photos sets photos.folder_id to NULL."""
    event = await _create_event(authed_client)
    event_id = uuid.UUID(event["id"])

    f_resp = await authed_client.post(
        f"/api/v1/events/{event_id}/folders",
        json={"name": "To Delete"},
    )
    folder_id = uuid.UUID(f_resp.json()["id"])

    photo = Photo(
        event_id=event_id,
        folder_id=folder_id,
        filename="test.jpg",
        original_s3_key="orig.jpg",
        file_size_bytes=1000,
        mime_type="image/jpeg",
    )
    db_session.add(photo)
    await db_session.flush()

    delete_resp = await authed_client.delete(f"/api/v1/events/{event_id}/folders/{folder_id}")
    assert delete_resp.status_code == 204

    # The photo should still exist but have folder_id=None
    await db_session.refresh(photo)
    assert photo.folder_id is None


@pytest.mark.asyncio
async def test_delete_folder_photos_true_recursive(authed_client: AsyncClient, db_session) -> None:
    """Deleting folder with delete_photos=true deletes photos recursively in descendants."""
    event = await _create_event(authed_client)
    event_id = uuid.UUID(event["id"])

    p_resp = await authed_client.post(f"/api/v1/events/{event_id}/folders", json={"name": "Parent"})
    parent_id = uuid.UUID(p_resp.json()["id"])

    c_resp = await authed_client.post(
        f"/api/v1/events/{event_id}/folders",
        json={"name": "Child", "parent_id": str(parent_id)},
    )
    child_id = uuid.UUID(c_resp.json()["id"])

    photo_parent = Photo(
        event_id=event_id,
        folder_id=parent_id,
        filename="parent.jpg",
        original_s3_key="p.jpg",
        file_size_bytes=1000,
        mime_type="image/jpeg",
    )
    photo_child = Photo(
        event_id=event_id,
        folder_id=child_id,
        filename="child.jpg",
        original_s3_key="c.jpg",
        file_size_bytes=1000,
        mime_type="image/jpeg",
    )
    db_session.add_all([photo_parent, photo_child])
    await db_session.flush()
    photo_parent_id = photo_parent.id
    photo_child_id = photo_child.id

    delete_resp = await authed_client.delete(
        f"/api/v1/events/{event_id}/folders/{parent_id}?delete_photos=true"
    )
    assert delete_resp.status_code == 204

    # Folders should be deleted
    assert await db_session.get(Folder, parent_id) is None
    assert await db_session.get(Folder, child_id) is None

    # Photos should be deleted!
    assert await db_session.get(Photo, photo_parent_id) is None
    assert await db_session.get(Photo, photo_child_id) is None
