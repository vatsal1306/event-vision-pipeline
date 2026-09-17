"""Resolution of the image URLs handed to gallery clients.

Galleries fetch image bytes straight from S3 using presigned URLs embedded in
the photo list response. The API is therefore involved once per page of photos
rather than once per image, which is what keeps a 50-tile grid from opening 50
connections, 50 database checkouts, and 50 rate-limiter round trips.

When S3 is not configured (local development and tests) presigned URLs point at
an unservable host, so the builder falls back to the HMAC-signed
``/preview`` route that streams bytes from the local filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger
from app.models.enums import PhotoVariant
from app.models.photo import Photo
from app.services.s3_presigner import bucket_expiry_seconds
from app.services.storage_service import S3StorageService, StorageService, get_storage_service
from app.utils.media_tokens import build_photo_preview_url

logger = get_logger()

_WEBP_MEDIA_TYPE = "image/webp"
# S3 echoes this back on the object response, letting the browser reuse the
# bytes for the life of the presigned URL instead of refetching on every view.
_GALLERY_CACHE_CONTROL = "private, max-age={max_age}, immutable"


@dataclass(frozen=True)
class PhotoUrls:
    """Per-rendition URLs for one photo.

    ``thumb`` and ``preview`` fall back to larger renditions when a photo
    predates the derivative ladder, so galleries always render something.
    """

    thumb: str | None
    preview: str | None
    full: str | None


class GalleryUrlBuilder:
    """Builds the image URLs returned in photo list responses.

    Instantiate once per request and reuse across every photo in the page; the
    storage lookup and settings read are then done once rather than per photo.
    """

    def __init__(self, storage: StorageService | None = None) -> None:
        """Resolve the active storage backend and cache the signing parameters.

        Args:
            storage: Override for the process-wide storage service. Intended
                for tests.
        """
        self.settings = get_settings()
        self.storage = storage if storage is not None else get_storage_service()
        self.serves_direct_from_s3 = isinstance(self.storage, S3StorageService)
        self.expires_in = bucket_expiry_seconds(self.settings.gallery_url_cache_bucket_seconds)

    def urls_for(self, photo: Photo) -> PhotoUrls:
        """Return the renditions available for a photo.

        Args:
            photo: Photo row with its derivative keys loaded.

        Returns:
            URLs per rendition. Every field is ``None`` only when the photo has
            no stored object at all, which happens between the database insert
            and the end of the upload.
        """
        return PhotoUrls(
            thumb=self._url_for_variant(photo, PhotoVariant.THUMB),
            preview=self._url_for_variant(photo, PhotoVariant.PREVIEW),
            full=self._url_for_variant(photo, PhotoVariant.FULL),
        )

    def _url_for_variant(self, photo: Photo, variant: PhotoVariant) -> str | None:
        """Resolve one rendition, degrading to the next larger object.

        Args:
            photo: Photo row with its derivative keys loaded.
            variant: Requested rendition.

        Returns:
            A URL the browser can load, or ``None`` when nothing is stored yet.
        """
        key = self.resolve_storage_key(photo, variant)
        if key is None:
            return None
        if not self.serves_direct_from_s3:
            return build_photo_preview_url(photo.event_id, photo.id, variant=variant)
        return self._presign(key)

    def resolve_storage_key(self, photo: Photo, variant: PhotoVariant) -> str | None:
        """Pick the best stored object for a rendition.

        Preference runs smallest-adequate first and then upward, so a photo
        that has only the legacy 2048px proxy still renders in the grid.

        Args:
            photo: Photo row with its derivative keys loaded.
            variant: Requested rendition.

        Returns:
            An S3 key in the proxies bucket, or ``None``.
        """
        if variant is PhotoVariant.THUMB:
            candidates = (photo.thumb_s3_key, photo.preview_s3_key, photo.proxy_s3_key)
        elif variant is PhotoVariant.PREVIEW:
            candidates = (photo.preview_s3_key, photo.proxy_s3_key, photo.thumb_s3_key)
        else:
            candidates = (photo.proxy_s3_key, photo.preview_s3_key, photo.thumb_s3_key)
        return next((key for key in candidates if key), None)

    def _presign(self, key: str) -> str | None:
        """Sign a proxies-bucket object for direct browser access.

        Args:
            key: S3 key inside the proxies bucket.

        Returns:
            A presigned URL, or ``None`` if signing failed. A missing URL
            degrades one tile to its blurhash placeholder; raising here would
            fail the whole gallery page.
        """
        max_age = self.settings.gallery_url_cache_bucket_seconds
        try:
            return self.storage.build_presigned_url(
                bucket=self.settings.s3_bucket_proxies,
                key=key,
                client_method="get_object",
                expires_in=self.expires_in,
                extra_params={
                    "ResponseContentType": _WEBP_MEDIA_TYPE,
                    "ResponseCacheControl": _GALLERY_CACHE_CONTROL.format(max_age=max_age),
                },
            )
        except StorageError as exc:
            logger.warning("Failed to sign gallery URL", s3_key=key, exc_info=exc)
            return None
