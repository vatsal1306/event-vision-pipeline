"""Tests for the URLs handed to gallery clients."""

from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

import pytest

from app.config import get_settings
from app.models.enums import PhotoVariant, ProcessingStatus
from app.models.photo import Photo
from app.services.gallery_url_service import GalleryUrlBuilder
from app.services.storage_service import LocalStorageService, S3StorageService


def _photo(
    *,
    proxy_s3_key: str | None = None,
    thumb_s3_key: str | None = None,
    preview_s3_key: str | None = None,
) -> Photo:
    """Build an unpersisted photo with the given rendition keys."""
    return Photo(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        filename="IMG_0001.JPG",
        original_s3_key="originals/IMG_0001.JPG",
        proxy_s3_key=proxy_s3_key,
        thumb_s3_key=thumb_s3_key,
        preview_s3_key=preview_s3_key,
        file_size_bytes=1000,
        mime_type="image/jpeg",
        processing_status=ProcessingStatus.COMPLETED,
    )


def test_urls_point_at_the_matching_rendition() -> None:
    """Each rendition resolves to its own object so grids stay lightweight."""
    photo = _photo(
        proxy_s3_key="proxies/e/p.webp",
        thumb_s3_key="proxies/e/p-thumb.webp",
        preview_s3_key="proxies/e/p-preview.webp",
    )

    urls = GalleryUrlBuilder(storage=S3StorageService()).urls_for(photo)

    assert "p-thumb.webp" in (urls.thumb or "")
    assert "p-preview.webp" in (urls.preview or "")
    assert urlparse(urls.full or "").path.endswith("/proxies/e/p.webp")


def test_urls_fall_back_to_the_proxy_when_derivatives_are_missing() -> None:
    """Photos uploaded before the rendition ladder must still render."""
    photo = _photo(proxy_s3_key="proxies/e/legacy.webp")

    urls = GalleryUrlBuilder(storage=S3StorageService()).urls_for(photo)

    assert urls.thumb == urls.preview == urls.full
    assert "legacy.webp" in (urls.thumb or "")


def test_urls_are_none_when_nothing_is_stored_yet() -> None:
    """A row created before its upload finishes has no gallery object."""
    urls = GalleryUrlBuilder(storage=S3StorageService()).urls_for(_photo())

    assert (urls.thumb, urls.preview, urls.full) == (None, None, None)


def test_s3_urls_carry_cache_headers_for_the_browser() -> None:
    """S3 must echo Cache-Control so repeat views come from the disk cache."""
    photo = _photo(thumb_s3_key="proxies/e/p-thumb.webp")
    settings = get_settings()

    url = GalleryUrlBuilder(storage=S3StorageService()).urls_for(photo).thumb

    query = parse_qs(urlparse(url or "").query)
    assert query["response-content-type"] == ["image/webp"]
    assert (
        f"max-age={settings.gallery_url_cache_bucket_seconds}"
        in (query["response-cache-control"][0])
    )
    # Two bucket widths, so a URL minted late in a bucket is still usable.
    assert query["X-Amz-Expires"] == [str(settings.gallery_url_cache_bucket_seconds * 2)]


def test_local_storage_falls_back_to_the_signed_preview_route(tmp_path) -> None:
    """Local development has no servable object store, so the API streams bytes."""
    storage = LocalStorageService()
    storage.base_dir = tmp_path
    photo = _photo(
        proxy_s3_key="proxies/e/p.webp",
        thumb_s3_key="proxies/e/p-thumb.webp",
        preview_s3_key="proxies/e/p-preview.webp",
    )

    urls = GalleryUrlBuilder(storage=storage).urls_for(photo)

    assert f"variant={PhotoVariant.THUMB.value}" in (urls.thumb or "")
    assert f"variant={PhotoVariant.PREVIEW.value}" in (urls.preview or "")
    assert f"variant={PhotoVariant.FULL.value}" in (urls.full or "")
    assert all("/preview?" in (url or "") for url in (urls.thumb, urls.preview, urls.full))


@pytest.mark.parametrize(
    ("variant", "expected_key"),
    [
        (PhotoVariant.THUMB, "proxies/e/p-thumb.webp"),
        (PhotoVariant.PREVIEW, "proxies/e/p-preview.webp"),
        (PhotoVariant.FULL, "proxies/e/p.webp"),
    ],
)
def test_resolve_storage_key_picks_the_requested_rendition(
    variant: PhotoVariant, expected_key: str
) -> None:
    """The preview route and the URL builder must agree on which object to serve."""
    photo = _photo(
        proxy_s3_key="proxies/e/p.webp",
        thumb_s3_key="proxies/e/p-thumb.webp",
        preview_s3_key="proxies/e/p-preview.webp",
    )

    builder = GalleryUrlBuilder(storage=S3StorageService())

    assert builder.resolve_storage_key(photo, variant) == expected_key


def test_gallery_urls_do_not_change_within_a_cache_bucket() -> None:
    """Stable URLs are what let a returning couple load the grid from cache."""
    photo = _photo(thumb_s3_key="proxies/e/p-thumb.webp")
    builder = GalleryUrlBuilder(storage=S3StorageService())

    assert builder.urls_for(photo).thumb == builder.urls_for(photo).thumb
