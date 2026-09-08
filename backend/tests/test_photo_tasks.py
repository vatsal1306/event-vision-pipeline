"""Tests for photo processing tasks and services (BE-010)."""

from __future__ import annotations

import io
import uuid
from unittest.mock import patch

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventStatus, ProcessingStatus
from app.models.event import Event
from app.models.photo import Photo
from app.models.photographer import Photographer
from app.services.image_processing_service import ImageProcessingService
from app.services.storage_service import LocalStorageService
from app.services.watermark_service import WatermarkService
from app.tasks.photo_tasks import _process_uploaded_photo_async


async def create_photographer(
    db_session: AsyncSession, email: str, watermark: bool = False
) -> Photographer:
    p = Photographer(
        email=email,
        password_hash="hash",
        studio_name="Test Studio",
        phone=f"+91{uuid.uuid4().hex[:10]}",
        phone_verified=True,
    )
    if watermark:
        p.watermark_url = f"watermarks/{p.id}.png"
    db_session.add(p)
    await db_session.commit()
    return p


async def create_event(db_session: AsyncSession, photographer_id: uuid.UUID) -> Event:
    e = Event(
        photographer_id=photographer_id,
        name="Test Event processing",
        slug=f"test-slug-{uuid.uuid4().hex[:8]}",
        status=EventStatus.PROCESSING,
        total_photos=1,
    )
    db_session.add(e)
    await db_session.commit()
    return e


async def create_photo(db_session: AsyncSession, event_id: uuid.UUID, s3_key: str) -> Photo:
    p = Photo(
        event_id=event_id,
        filename="test.jpg",
        file_size_bytes=1000,
        mime_type="image/jpeg",
        tus_upload_id=f"upload-{uuid.uuid4().hex[:8]}",
        original_s3_key=s3_key,
        processing_status=ProcessingStatus.PENDING,
    )
    db_session.add(p)
    await db_session.commit()
    return p


def create_test_image_bytes(
    width: int = 100, height: int = 100, color: str = "blue", format: str = "JPEG"
) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def create_test_watermark_bytes() -> bytes:
    img = Image.new("RGBA", (50, 50), color=(255, 255, 255, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def storage():
    # Use local storage service which writes to .data/s3
    return LocalStorageService()


@pytest.mark.asyncio
async def test_image_processing_service(storage: LocalStorageService) -> None:
    """Test generating a web proxy and blurhash from a JPEG."""
    service = ImageProcessingService(storage)
    event_id = str(uuid.uuid4())
    s3_key = f"originals/{event_id}/test_image.jpg"

    # Put test image in storage
    img_bytes = create_test_image_bytes(3000, 2000, "red")
    await storage.put_object(service.settings.s3_bucket_originals, s3_key, img_bytes, "image/jpeg")

    # Generate proxy
    proxy_key = await service.generate_web_proxy(s3_key, event_id)
    assert proxy_key.startswith(f"proxies/{event_id}/")
    assert proxy_key.endswith(".webp")

    # Generate blurhash and dims
    blurhash, width, height = await service.generate_blurhash_and_dimensions(proxy_key)
    assert len(blurhash) > 10

    # Original was 3000x2000. Proxy max dim is 2048, so should be 2048x1365
    assert width == 2048
    assert height == 1365


@pytest.mark.asyncio
async def test_watermark_service(storage: LocalStorageService) -> None:
    """Test applying a watermark to a proxy image."""
    service = WatermarkService(storage)
    proxy_key = "proxies/test_wm/proxy.webp"
    wm_key = "watermarks/logo.png"

    proxy_bytes = create_test_image_bytes(1000, 1000, "white", "WEBP")
    wm_bytes = create_test_watermark_bytes()

    await storage.put_object(
        service.settings.s3_bucket_proxies, proxy_key, proxy_bytes, "image/webp"
    )
    await storage.put_object(service.settings.s3_bucket_assets, wm_key, wm_bytes, "image/png")

    await service.apply_watermark(proxy_key, wm_key)

    # Should overwrite the proxy with watermarked version
    result_bytes = await storage.get_object(service.settings.s3_bucket_proxies, proxy_key)

    # Just verify it's a valid image
    img = Image.open(io.BytesIO(result_bytes))
    assert img.size == (1000, 1000)
    assert img.format == "WEBP"


@pytest.mark.asyncio
async def test_process_uploaded_photo_success(
    db_session: AsyncSession, storage: LocalStorageService
) -> None:
    """Test the full processing pipeline for a photo (no watermark)."""
    photographer = await create_photographer(db_session, "process1@test.com")
    event = await create_event(db_session, photographer.id)
    s3_key = f"originals/{event.id}/test_process.jpg"
    photo = await create_photo(db_session, event.id, s3_key)

    img_bytes = create_test_image_bytes()
    await storage.put_object("platform-originals", s3_key, img_bytes, "image/jpeg")

    # Process
    with patch("app.tasks.photo_tasks.async_session_factory") as mock_db, \
         patch("app.tasks.notification_tasks.notify_processing_complete_task.delay"):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_session():
            yield db_session

        mock_db.side_effect = mock_session
        await _process_uploaded_photo_async(str(photo.id), s3_key, str(event.id))

    # Verify db update
    await db_session.refresh(photo)
    assert photo.processing_status == ProcessingStatus.COMPLETED
    assert photo.proxy_s3_key is not None
    assert photo.blurhash is not None
    assert photo.width == 100
    assert photo.height == 100
    assert photo.processing_error is None

    # Verify event status updated to READY because 1 of 1 completed
    await db_session.refresh(event)
    assert event.status == EventStatus.READY


@pytest.mark.asyncio
async def test_process_uploaded_photo_with_watermark(
    db_session: AsyncSession, storage: LocalStorageService
) -> None:
    """Test pipeline when photographer has a watermark."""
    photographer = await create_photographer(db_session, "process2@test.com", watermark=True)
    event = await create_event(db_session, photographer.id)
    s3_key = f"originals/{event.id}/test_process_wm.jpg"
    photo = await create_photo(db_session, event.id, s3_key)

    img_bytes = create_test_image_bytes()
    wm_bytes = create_test_watermark_bytes()
    await storage.put_object("platform-originals", s3_key, img_bytes, "image/jpeg")
    await storage.put_object(
        "platform-assets", str(photographer.watermark_url), wm_bytes, "image/png"
    )

    # Process
    with patch("app.tasks.photo_tasks.async_session_factory") as mock_db, \
         patch("app.tasks.notification_tasks.notify_processing_complete_task.delay"):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_session():
            yield db_session

        mock_db.side_effect = mock_session
        await _process_uploaded_photo_async(str(photo.id), s3_key, str(event.id))

    await db_session.refresh(photo)
    assert photo.processing_status == ProcessingStatus.COMPLETED


@pytest.mark.asyncio
async def test_process_uploaded_photo_failure(
    db_session: AsyncSession, storage: LocalStorageService
) -> None:
    """Test pipeline sets failure status on exception."""
    photographer = await create_photographer(db_session, "process3@test.com")
    event = await create_event(db_session, photographer.id)
    s3_key = f"originals/{event.id}/test_fail.jpg"
    photo = await create_photo(db_session, event.id, s3_key)

    # Put invalid image data to cause cv2.imdecode to fail (which raises ValueError -> FAILED)
    await storage.put_object("platform-originals", s3_key, b"not an image", "image/jpeg")

    with patch("app.tasks.photo_tasks.async_session_factory") as mock_db, \
         patch("app.tasks.notification_tasks.notify_processing_complete_task.delay"):
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_session():
            yield db_session

        mock_db.side_effect = mock_session
        await _process_uploaded_photo_async(str(photo.id), s3_key, str(event.id))

    await db_session.refresh(photo)
    assert photo.processing_status == ProcessingStatus.FAILED
    assert "failed to decode" in str(photo.processing_error).lower()


@pytest.mark.asyncio
async def test_image_processing_heic(storage: LocalStorageService) -> None:
    """Test HEIC proxy generation via mocked pillow_heif."""
    service = ImageProcessingService(storage)
    event_id = str(uuid.uuid4())
    s3_key = f"originals/{event_id}/test.heic"

    await storage.put_object(
        service.settings.s3_bucket_originals, s3_key, b"fake heic", "image/heic"
    )

    with patch("app.services.image_processing_service.read_heif") as mock_read_heif:
        with patch("app.services.image_processing_service.np.asarray") as mock_asarray:
            import numpy as np

            mock_asarray.return_value = np.zeros((10, 10, 3), dtype=np.uint8)
            proxy_key = await service.generate_web_proxy(s3_key, event_id)

    assert proxy_key.endswith(".webp")
    assert mock_read_heif.called
