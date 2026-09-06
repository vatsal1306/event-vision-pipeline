"""Image processing service for proxies and blurhash."""

from __future__ import annotations

import io
import uuid

from blurhash import encode as blurhash_encode  # type: ignore[import-untyped]
from PIL import Image, ImageOps

from app.config import get_settings
from app.services.storage_service import StorageService


class ImageProcessingService:
    """Generates web-optimized proxy images from originals."""

    PROXY_MAX_DIMENSION = 2048
    PROXY_QUALITY_WEBP = 82
    PROXY_TARGET_SIZE_KB = 500

    def __init__(self, storage_service: StorageService) -> None:
        """Initialize with storage service."""
        self.storage = storage_service
        self.settings = get_settings()

    async def generate_web_proxy(self, original_s3_key: str, event_id: str) -> str:
        """Download original, generate optimized proxy, upload to hot storage."""
        original_bucket = self.settings.s3_bucket_originals
        proxy_bucket = self.settings.s3_bucket_proxies
        image_bytes = await self.storage.get_object(original_bucket, original_s3_key)
        image_file = Image.open(io.BytesIO(image_bytes))

        # Handle EXIF orientation
        image: Image.Image = ImageOps.exif_transpose(image_file)

        # Resize (maintain aspect ratio)
        image.thumbnail(
            (self.PROXY_MAX_DIMENSION, self.PROXY_MAX_DIMENSION),
            Image.Resampling.LANCZOS,
        )

        # Convert to RGB (handle RGBA, CMYK, etc.)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Encode as WebP (primary) with fallback quality reduction
        proxy_buffer = io.BytesIO()
        image.save(proxy_buffer, format="WEBP", quality=self.PROXY_QUALITY_WEBP)

        # If WebP output is too large, reduce quality iteratively
        quality = self.PROXY_QUALITY_WEBP
        while proxy_buffer.tell() > self.PROXY_TARGET_SIZE_KB * 1024 and quality > 50:
            quality -= 5
            proxy_buffer = io.BytesIO()
            image.save(proxy_buffer, format="WEBP", quality=quality)

        proxy_s3_key = f"proxies/{event_id}/{uuid.uuid4()}.webp"
        await self.storage.put_object(
            bucket=proxy_bucket,
            key=proxy_s3_key,
            data=proxy_buffer.getvalue(),
            content_type="image/webp",
            storage_class="STANDARD",
        )

        return proxy_s3_key

    async def generate_blurhash_and_dimensions(self, proxy_s3_key: str) -> tuple[str, int, int]:
        """Download proxy, generate blurhash and return dimensions."""
        proxy_bucket = self.settings.s3_bucket_proxies
        image_bytes = await self.storage.get_object(proxy_bucket, proxy_s3_key)
        image = Image.open(io.BytesIO(image_bytes))
        width, height = image.size

        small = image.copy()
        small.thumbnail((32, 32))
        blurhash = blurhash_encode(
            small.convert("RGB"),
            x_components=4,
            y_components=3,
        )
        return blurhash, width, height
