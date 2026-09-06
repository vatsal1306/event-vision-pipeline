"""Upload webhook tests (BE-009)."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event, EventStatus
from app.models.photo import Photo
from app.models.photographer import Photographer


async def create_photographer(
    db_session: AsyncSession, email: str, storage_limit: int = 1000000000
) -> Photographer:
    p = Photographer(
        email=email,
        password_hash="hash",
        studio_name="Test Studio",
        phone=f"+91{uuid.uuid4().hex[:10]}",
        phone_verified=True,
        storage_limit_bytes=storage_limit,
    )
    db_session.add(p)
    await db_session.commit()
    return p


async def create_event(db_session: AsyncSession, photographer_id: uuid.UUID, name: str) -> Event:
    e = Event(
        photographer_id=photographer_id,
        name=name,
        slug=f"test-slug-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(e)
    await db_session.commit()
    return e


@pytest.fixture
def mock_delay():
    with patch("app.tasks.photo_tasks.process_uploaded_photo.delay") as mock:
        yield mock


@pytest.mark.asyncio
async def test_tusd_hook_pre_create_success(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Pre-create hook should accept valid uploads within quota."""
    photographer = await create_photographer(
        db_session, email="tusd1@example.com", storage_limit=1000
    )
    event = await create_event(db_session, photographer.id, "Test Event")

    payload = {
        "Type": "pre-create",
        "Event": {
            "Upload": {
                "ID": "upload-123",
                "Size": 500,
                "Offset": 0,
                "Storage": {},
                "MetaData": {
                    "event_id": str(event.id),
                    "photographer_id": str(photographer.id),
                    "filetype": "image/jpeg",
                },
            }
        },
    }

    response = await db_client.post("/api/v1/upload/hook", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_tusd_hook_pre_create_quota_exceeded(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Pre-create hook should reject uploads exceeding quota."""
    photographer = await create_photographer(
        db_session, email="tusd2@example.com", storage_limit=100
    )
    event = await create_event(db_session, photographer.id, "Test Event 2")

    payload = {
        "Type": "pre-create",
        "Event": {
            "Upload": {
                "ID": "upload-456",
                "Size": 200,  # Exceeds 100
                "Offset": 0,
                "Storage": {},
                "MetaData": {
                    "event_id": str(event.id),
                    "photographer_id": str(photographer.id),
                    "filetype": "image/jpeg",
                },
            }
        },
    }

    response = await db_client.post("/api/v1/upload/hook", json=payload)
    assert response.status_code == 402
    assert response.json()["code"] == "STORAGE_LIMIT"


@pytest.mark.asyncio
async def test_tusd_hook_pre_create_invalid_mime(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Pre-create hook should reject invalid MIME types."""
    photographer = await create_photographer(
        db_session, email="tusd_mime@example.com", storage_limit=1000
    )
    event = await create_event(db_session, photographer.id, "Test Event Mime")

    payload = {
        "Type": "pre-create",
        "Event": {
            "Upload": {
                "ID": "upload-mime",
                "Size": 200,
                "Offset": 0,
                "Storage": {},
                "MetaData": {
                    "event_id": str(event.id),
                    "photographer_id": str(photographer.id),
                    "filetype": "application/pdf",
                },
            }
        },
    }

    response = await db_client.post("/api/v1/upload/hook", json=payload)
    assert response.status_code == 422
    assert "not allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_tusd_hook_post_finish_success(
    db_client: AsyncClient, db_session: AsyncSession, mock_delay
) -> None:
    """Post-finish hook should create Photo and enqueue task."""
    photographer = await create_photographer(db_session, email="tusd3@example.com")
    event = await create_event(db_session, photographer.id, "Test Event 3")

    payload = {
        "Type": "post-finish",
        "Event": {
            "Upload": {
                "ID": "upload-789",
                "Size": 500,
                "Offset": 500,
                "Storage": {"Key": "originals/upload-789"},
                "MetaData": {
                    "event_id": str(event.id),
                    "photographer_id": str(photographer.id),
                    "filename": "test.jpg",
                    "filetype": "image/jpeg",
                },
            }
        },
    }

    response = await db_client.post("/api/v1/upload/hook", json=payload)
    assert response.status_code == 200

    # Verify photo created
    stmt = select(Photo).where(Photo.tus_upload_id == "upload-789")
    photo = (await db_session.execute(stmt)).scalar_one_or_none()
    assert photo is not None
    assert photo.event_id == event.id
    assert photo.filename == "test.jpg"

    # Verify event updated
    await db_session.refresh(event)
    assert event.total_photos == 1
    assert event.status == EventStatus.PROCESSING

    # Verify quota updated
    await db_session.refresh(photographer)
    assert photographer.storage_used_bytes == 500

    # Verify celery task queued
    mock_delay.assert_called_once_with(str(photo.id), "originals/upload-789", str(event.id))


@pytest.mark.asyncio
async def test_tusd_hook_post_finish_idempotency(
    db_client: AsyncClient, db_session: AsyncSession, mock_delay
) -> None:
    """Post-finish hook should be idempotent."""
    photographer = await create_photographer(db_session, email="tusd4@example.com")
    event = await create_event(db_session, photographer.id, "Test Event 4")

    payload = {
        "Type": "post-finish",
        "Event": {
            "Upload": {
                "ID": "upload-abc",
                "Size": 500,
                "Offset": 500,
                "Storage": {"Key": "originals/upload-abc"},
                "MetaData": {
                    "event_id": str(event.id),
                    "photographer_id": str(photographer.id),
                    "filename": "test2.jpg",
                    "filetype": "image/jpeg",
                },
            }
        },
    }

    # First call
    response = await db_client.post("/api/v1/upload/hook", json=payload)
    assert response.status_code == 200
    assert mock_delay.call_count == 1

    # Second call
    response2 = await db_client.post("/api/v1/upload/hook", json=payload)
    assert response2.status_code == 200
    assert response2.json()["note"] == "already processed"

    # Task should not be queued again
    assert mock_delay.call_count == 1


@pytest.mark.asyncio
async def test_tusd_hook_post_finish_unauthorized(
    db_client: AsyncClient, db_session: AsyncSession, mock_delay
) -> None:
    """Post-finish hook should reject mismatched event/photographer IDs."""
    photographer1 = await create_photographer(db_session, email="tusd5@example.com")
    photographer2 = await create_photographer(db_session, email="tusd6@example.com")
    event = await create_event(db_session, photographer1.id, "Test Event 5")

    payload = {
        "Type": "post-finish",
        "Event": {
            "Upload": {
                "ID": "upload-unauth",
                "Size": 500,
                "Offset": 500,
                "Storage": {"Key": "originals/upload-unauth"},
                "MetaData": {
                    "event_id": str(event.id),
                    "photographer_id": str(photographer2.id),  # Mismatched owner
                    "filename": "test.jpg",
                    "filetype": "image/jpeg",
                },
            }
        },
    }

    response = await db_client.post("/api/v1/upload/hook", json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tusd_hook_post_finish_missing_s3_key(
    db_client: AsyncClient, db_session: AsyncSession, mock_delay
) -> None:
    """Post-finish hook should reject missing S3 key."""
    photographer = await create_photographer(db_session, email="tusd7@example.com")
    event = await create_event(db_session, photographer.id, "Test Event 6")

    payload = {
        "Type": "post-finish",
        "Event": {
            "Upload": {
                "ID": "upload-nokey",
                "Size": 500,
                "Offset": 500,
                "Storage": {},  # Missing Key
                "MetaData": {
                    "event_id": str(event.id),
                    "photographer_id": str(photographer.id),
                    "filename": "test.jpg",
                    "filetype": "image/jpeg",
                },
            }
        },
    }

    response = await db_client.post("/api/v1/upload/hook", json=payload)
    assert response.status_code == 422
