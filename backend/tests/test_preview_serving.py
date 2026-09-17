"""Unit tests for gallery preview serving without buffering S3 objects."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.responses import RedirectResponse, Response

from app.services.photo_service import PreviewLocation, serve_preview_location
from app.services.storage_service import LocalStorageService, S3StorageService


class _RedirectingS3(S3StorageService):
    """S3 storage stub that only generates a presigned URL."""

    def __init__(self) -> None:
        """Skip aioboto3 session setup."""

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        client_method: str = "get_object",
        expires_in: int | None = None,
        extra_params: dict[str, object] | None = None,
    ) -> str:
        """Return a fake S3 URL and record the requested object."""
        self.last_bucket = bucket
        self.last_key = key
        self.last_extra_params = extra_params
        return "https://s3.example/proxies/grid.webp?sig=abc"


@pytest.mark.asyncio
async def test_serve_preview_redirects_for_s3() -> None:
    """Browsers should fetch proxy bytes from S3, not through FastAPI RAM."""
    storage = _RedirectingS3()
    location = PreviewLocation(
        bucket="platform-proxies",
        key="events/x/proxies/grid.webp",
        media_type="image/webp",
    )
    with patch("app.services.photo_service.get_storage_service", return_value=storage):
        response = await serve_preview_location(location)

    assert isinstance(response, RedirectResponse)
    assert response.status_code == 307
    assert response.headers["location"] == "https://s3.example/proxies/grid.webp?sig=abc"
    assert storage.last_bucket == "platform-proxies"
    assert storage.last_key == "events/x/proxies/grid.webp"
    assert storage.last_extra_params == {"ResponseContentType": "image/webp"}


@pytest.mark.asyncio
async def test_resolve_preview_location_honours_the_requested_variant() -> None:
    """The signed route must serve the asked-for size, not always the 2048px proxy."""
    from app.models.enums import PhotoVariant, ProcessingStatus
    from app.models.photo import Photo
    from app.services.photo_service import PhotoService

    photo = Photo(
        id=uuid4(),
        event_id=uuid4(),
        filename="IMG_1.JPG",
        original_s3_key="originals/IMG_1.JPG",
        proxy_s3_key="proxies/e/p.webp",
        thumb_s3_key="proxies/e/p-thumb.webp",
        preview_s3_key="proxies/e/p-preview.webp",
        file_size_bytes=1000,
        mime_type="image/jpeg",
        processing_status=ProcessingStatus.COMPLETED,
    )
    session = AsyncMock()
    session.get.return_value = photo
    service = PhotoService(session)

    expected = {
        PhotoVariant.THUMB: "proxies/e/p-thumb.webp",
        PhotoVariant.PREVIEW: "proxies/e/p-preview.webp",
        PhotoVariant.FULL: "proxies/e/p.webp",
    }

    for variant, key in expected.items():
        location = await service.resolve_preview_location(photo.event_id, photo.id, variant)
        assert location.key == key
        assert location.media_type == "image/webp"


@pytest.mark.asyncio
async def test_resolve_preview_location_falls_back_to_the_original() -> None:
    """A photo still being processed has no rendition, so stream the original."""
    from app.models.enums import ProcessingStatus
    from app.models.photo import Photo
    from app.services.photo_service import PhotoService

    photo = Photo(
        id=uuid4(),
        event_id=uuid4(),
        filename="IMG_2.JPG",
        original_s3_key="originals/IMG_2.JPG",
        file_size_bytes=1000,
        mime_type="image/jpeg",
        processing_status=ProcessingStatus.PENDING,
    )
    session = AsyncMock()
    session.get.return_value = photo

    location = await PhotoService(session).resolve_preview_location(photo.event_id, photo.id)

    assert location.key == "originals/IMG_2.JPG"
    assert location.media_type == "image/jpeg"


@pytest.mark.asyncio
async def test_serve_preview_returns_bytes_for_local_storage(tmp_path) -> None:
    """Local/dev storage still returns the object body."""
    storage = LocalStorageService()
    storage.base_dir = tmp_path
    await storage.put_object("platform-proxies", "grid.webp", b"webp-bytes", "image/webp")
    location = PreviewLocation(
        bucket="platform-proxies",
        key="grid.webp",
        media_type="image/webp",
    )
    with patch("app.services.photo_service.get_storage_service", return_value=storage):
        response = await serve_preview_location(location)

    assert isinstance(response, Response)
    assert not isinstance(response, RedirectResponse)
    assert response.status_code == 200
    assert response.body == b"webp-bytes"
    assert response.media_type == "image/webp"
