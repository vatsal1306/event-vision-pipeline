"""Integration tests for photos (BE-007)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_redis_dep
from app.core.database import get_db
from app.core.redis_client import create_redis_client
from app.main import app
from app.models.enums import ProcessingStatus
from app.models.event import Event
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.services.sms_service import SMSService
from app.utils.otp import OTPService

VALID_PASSWORD = "Password1!"
PRIMARY_REGISTER = {
    "email": "photos-primary@example.com",
    "password": VALID_PASSWORD,
    "studio_name": "Photos Studio",
    "phone": "+919876543111",
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
            "name": "Photo Test Event",
            "date_start": "2026-11-15",
            "date_end": "2026-11-17",
            "event_type": "wedding",
            "description": "Photo testing",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_list_photos(authed_client: AsyncClient, db_session) -> None:
    """List photos with pagination and folder filtering."""
    event = await _create_event(authed_client)
    event_id = uuid.UUID(event["id"])

    # Create folder
    f_resp = await authed_client.post(
        f"/api/v1/events/{event_id}/folders", json={"name": "Folder 1"}
    )
    folder_id = uuid.UUID(f_resp.json()["id"])

    # Create photos
    photo1 = Photo(
        event_id=event_id,
        folder_id=None,
        filename="root.jpg",
        original_s3_key="root.jpg",
        proxy_s3_key="root_proxy.jpg",
        file_size_bytes=1000,
        mime_type="image/jpeg",
        processing_status=ProcessingStatus.COMPLETED,
    )
    photo2 = Photo(
        event_id=event_id,
        folder_id=folder_id,
        filename="folder.jpg",
        original_s3_key="folder.jpg",
        file_size_bytes=1000,
        mime_type="image/jpeg",
        processing_status=ProcessingStatus.PENDING,
    )
    db_session.add_all([photo1, photo2])
    await db_session.flush()

    # List all photos
    resp = await authed_client.get(f"/api/v1/events/{event_id}/photos")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Check signed preview URL is set for completed and pending photos
    completed_photo = next(p for p in data["items"] if p["id"] == str(photo1.id))
    assert completed_photo["proxy_url"] is not None
    assert "/preview?" in completed_photo["proxy_url"]

    pending_photo = next(p for p in data["items"] if p["id"] == str(photo2.id))
    assert pending_photo["proxy_url"] is not None
    assert "/preview?" in pending_photo["proxy_url"]

    # List photos in folder
    resp = await authed_client.get(f"/api/v1/events/{event_id}/photos?folder_id={folder_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(photo2.id)


@pytest.mark.asyncio
async def test_move_photos(authed_client: AsyncClient, db_session) -> None:
    """Move photos between folders."""
    event = await _create_event(authed_client)
    event_id = uuid.UUID(event["id"])

    f_resp = await authed_client.post(
        f"/api/v1/events/{event_id}/folders", json={"name": "Folder 1"}
    )
    folder_id = uuid.UUID(f_resp.json()["id"])

    photo1 = Photo(
        event_id=event_id,
        folder_id=None,
        filename="root.jpg",
        original_s3_key="root.jpg",
        file_size_bytes=1000,
        mime_type="image/jpeg",
    )
    db_session.add(photo1)
    await db_session.flush()

    # Move to folder
    resp = await authed_client.post(
        f"/api/v1/events/{event_id}/photos/move",
        json={"photo_ids": [str(photo1.id)], "folder_id": str(folder_id)},
    )
    assert resp.status_code == 204

    await db_session.refresh(photo1)
    assert photo1.folder_id == folder_id

    # Move back to root
    resp = await authed_client.post(
        f"/api/v1/events/{event_id}/photos/move",
        json={"photo_ids": [str(photo1.id)], "folder_id": None},
    )
    assert resp.status_code == 204

    await db_session.refresh(photo1)
    assert photo1.folder_id is None

    # Move to invalid folder
    resp = await authed_client.post(
        f"/api/v1/events/{event_id}/photos/move",
        json={"photo_ids": [str(photo1.id)], "folder_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404

    # Move invalid photo
    resp = await authed_client.post(
        f"/api/v1/events/{event_id}/photos/move",
        json={"photo_ids": [str(uuid.uuid4())], "folder_id": None},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_photo(authed_client: AsyncClient, db_session) -> None:
    """Delete a single photo."""
    event = await _create_event(authed_client)
    event_id = uuid.UUID(event["id"])

    photo = Photo(
        event_id=event_id,
        folder_id=None,
        filename="test.jpg",
        original_s3_key="test.jpg",
        file_size_bytes=1000,
        mime_type="image/jpeg",
    )
    db_session.add(photo)
    await db_session.flush()

    # Set initial counters
    event_db = await db_session.get(Event, event_id)
    event_db.total_photos = 1
    photographer = await db_session.get(Photographer, event_db.photographer_id)
    photographer.storage_used_bytes = 1000
    await db_session.flush()

    # Delete the photo
    resp = await authed_client.delete(f"/api/v1/events/{event_id}/photos/{photo.id}")
    assert resp.status_code == 204

    assert await db_session.get(Photo, photo.id) is None

    # Verify counters decremented
    await db_session.refresh(event_db)
    assert event_db.total_photos == 0
    await db_session.refresh(photographer)
    assert photographer.storage_used_bytes == 0

    # Delete non-existent photo
    resp = await authed_client.delete(f"/api/v1/events/{event_id}/photos/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_download_photo_url(authed_client: AsyncClient, db_session) -> None:
    """Get a short-lived download URL for a photo."""
    event = await _create_event(authed_client)
    event_id = uuid.UUID(event["id"])

    photo = Photo(
        event_id=event_id,
        folder_id=None,
        filename="test.jpg",
        original_s3_key="original_image_123.jpg",
        file_size_bytes=1000,
        mime_type="image/jpeg",
    )
    db_session.add(photo)
    await db_session.flush()

    mock_storage = AsyncMock()
    mock_storage.generate_presigned_url.return_value = (
        "https://mock-s3.local/download/original_image_123.jpg?expires=3600"
    )

    with patch("app.services.photo_service.get_storage_service", return_value=mock_storage):
        resp = await authed_client.get(f"/api/v1/events/{event_id}/photos/{photo.id}/download")

    assert resp.status_code == 200
    data = resp.json()
    assert data["url"] == "https://mock-s3.local/download/original_image_123.jpg?expires=3600"
    mock_storage.generate_presigned_url.assert_awaited_once()
    extra_params = mock_storage.generate_presigned_url.await_args.kwargs["extra_params"]
    assert extra_params["ResponseContentDisposition"] == 'attachment; filename="test.jpg"'


def _jpeg_bytes() -> bytes:
    """Return a tiny valid JPEG payload for upload tests."""
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=(200, 40, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_direct_upload_creates_photo_and_preview(
    authed_client: AsyncClient, tmp_path
) -> None:
    """POST /photos stores the original and returns a signed preview URL."""
    from pathlib import Path
    from unittest.mock import patch
    from urllib.parse import parse_qs, urlparse

    from app.services.storage_service import LocalStorageService

    event = await _create_event(authed_client)
    event_id = event["id"]
    payload = _jpeg_bytes()

    storage = LocalStorageService()
    storage.base_dir = Path(tmp_path)

    with (
        patch("app.services.photo_service.get_storage_service", return_value=storage),
        patch("app.tasks.photo_tasks.process_uploaded_photo.delay"),
    ):
        resp = await authed_client.post(
            f"/api/v1/events/{event_id}/photos",
            files={"file": ("reception.jpg", payload, "image/jpeg")},
        )

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["filename"] == "reception.jpg"
        assert body["file_size_bytes"] == len(payload)
        assert "/preview?" in body["proxy_url"]

        listed = await authed_client.get(f"/api/v1/events/{event_id}/photos")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

        preview_url = body["proxy_url"]
        parsed = urlparse(preview_url)
        query = parse_qs(parsed.query)
        preview = await authed_client.get(
            parsed.path,
            params={"expires": query["expires"][0], "sig": query["sig"][0]},
        )
        assert preview.status_code == 200
        assert preview.content == payload


@pytest.mark.asyncio
async def test_direct_upload_rejects_unsupported_type(authed_client: AsyncClient) -> None:
    """Reject non-image uploads at the ingest boundary."""
    event = await _create_event(authed_client)
    resp = await authed_client.post(
        f"/api/v1/events/{event['id']}/photos",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 422
