"""Image processing service for proxies and blurhash."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from blurhash import encode as blurhash_encode  # type: ignore[import-untyped]
from PIL import Image
from pillow_heif import read_heif  # type: ignore

from app.config import get_settings
from app.core.exceptions import ProcessingError
from app.models.enums import PhotoVariant
from app.services.storage_service import StorageService


@dataclass(frozen=True)
class DerivativeSet:
    """S3 keys and total byte size for the smaller gallery renditions."""

    thumb_s3_key: str
    micro_thumb_s3_key: str
    total_bytes: int


class ImageProcessingService:
    """Generates web-optimized proxy images from originals."""

    PROXY_TARGET_SIZE_KB = 500

    def __init__(self, storage_service: StorageService) -> None:
        """Initialize with storage service."""
        self.storage = storage_service
        self.settings = get_settings()

    async def generate_web_proxy(
        self,
        original_s3_key: str,
        event_id: str,
        interpolation: int = cv2.INTER_LANCZOS4,
        original_filename: str | None = None,
        mime_type: str | None = None,
    ) -> tuple[str, int]:
        """Download original, generate optimized proxy, upload to hot storage."""
        original_bucket = self.settings.s3_bucket_originals
        proxy_bucket = self.settings.s3_bucket_proxies
        image_bytes = await self.storage.get_object(original_bucket, original_s3_key)

        filename_to_check = original_filename or original_s3_key
        # Handle HEIC or standard decoding
        if filename_to_check.lower().endswith((".heic", ".heif")):
            heif_file = read_heif(image_bytes)
            image_np: Any = np.asarray(heif_file)
            image: Any = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
        else:
            image_array = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError(f"Failed to decode image from bytes for {original_s3_key}")

        # Resize maintaining aspect ratio
        max_dim = self.settings.proxy_max_dimension
        h, w = image.shape[:2]
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            image = cv2.resize(image, (new_w, new_h), interpolation=interpolation)

        # Encode WebP with quality scaling
        target_size_bytes = self.PROXY_TARGET_SIZE_KB * 1024
        quality = self.settings.proxy_quality

        while quality > 50:
            success, encoded_img = cv2.imencode(
                ".webp", image, [int(cv2.IMWRITE_WEBP_QUALITY), quality]
            )
            if not success:
                raise ValueError("Failed to encode WebP")
            if len(encoded_img) <= target_size_bytes:
                break
            quality -= 5

        proxy_buffer = encoded_img.tobytes()
        proxy_s3_key = f"proxies/{event_id}/{uuid.uuid4()}.webp"

        await self.storage.put_object(
            bucket=proxy_bucket,
            key=proxy_s3_key,
            data=proxy_buffer,
            content_type="image/webp",
            storage_class="STANDARD",
        )

        return proxy_s3_key, len(proxy_buffer)

    async def generate_derivatives(self, proxy_s3_key: str, event_id: str) -> DerivativeSet:
        """Produce the two grid renditions (thumb, micro-thumb) from an existing proxy.

        Derives from the proxy rather than the original so that any watermark
        already burned into the proxy is preserved, and so a backfill over old
        events reads the small Standard-tier object instead of pulling
        originals back out of Infrequent Access.

        Args:
            proxy_s3_key: Key of the 2048px WebP proxy in the proxies bucket.
            event_id: Event the photo belongs to, used in the derivative keys.

        Returns:
            Keys of the uploaded renditions and their combined size in bytes.

        Raises:
            ProcessingError: The proxy cannot be decoded or a rendition cannot
                be encoded.
            StorageError: The proxy cannot be read or a rendition cannot be
                written.
        """
        proxy_bucket = self.settings.s3_bucket_proxies
        proxy_bytes = await self.storage.get_object(proxy_bucket, proxy_s3_key)
        image = cv2.imdecode(np.frombuffer(proxy_bytes, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ProcessingError(f"Failed to decode proxy image {proxy_s3_key}")

        specs = (
            (
                PhotoVariant.THUMB,
                self.settings.thumb_max_dimension,
                self.settings.thumb_quality,
            ),
            (
                PhotoVariant.MICRO_THUMB,
                self.settings.micro_thumb_max_dimension,
                self.settings.micro_thumb_quality,
            ),
        )

        keys: dict[PhotoVariant, str] = {}
        total_bytes = 0
        for variant, max_dimension, quality in specs:
            encoded = self._encode_webp(
                self._downscale(image, max_dimension),
                quality,
                proxy_s3_key,
            )
            key = f"proxies/{event_id}/{uuid.uuid4()}-{variant.value}.webp"
            await self.storage.put_object(
                bucket=proxy_bucket,
                key=key,
                data=encoded,
                content_type="image/webp",
                storage_class="STANDARD",
            )
            keys[variant] = key
            total_bytes += len(encoded)

        return DerivativeSet(
            thumb_s3_key=keys[PhotoVariant.THUMB],
            micro_thumb_s3_key=keys[PhotoVariant.MICRO_THUMB],
            total_bytes=total_bytes,
        )

    @staticmethod
    def _downscale(image: Any, max_dimension: int, interpolation: int = cv2.INTER_AREA) -> Any:
        """Scale an image down so its longest edge is at most ``max_dimension``.

        Images already within the bound are returned unchanged. ``INTER_AREA``
        is the correct filter for downscaling and avoids the ringing that
        Lanczos introduces at thumbnail sizes.

        Args:
            image: Decoded BGR image.
            max_dimension: Upper bound for the longest edge, in pixels.
            interpolation: OpenCV interpolation flag.

        Returns:
            The original or a downscaled copy.
        """
        height, width = image.shape[:2]
        longest_edge = max(height, width)
        if longest_edge <= max_dimension:
            return image
        scale = max_dimension / longest_edge
        return cv2.resize(
            image,
            (max(int(width * scale), 1), max(int(height * scale), 1)),
            interpolation=interpolation,
        )

    @staticmethod
    def _encode_webp(image: Any, quality: int, source_key: str) -> bytes:
        """Encode a BGR image as WebP.

        Args:
            image: Decoded BGR image.
            quality: WebP quality between 1 and 100.
            source_key: Key of the source object, for error context.

        Returns:
            Encoded WebP bytes.

        Raises:
            ProcessingError: OpenCV could not encode the image.
        """
        success, encoded = cv2.imencode(".webp", image, [int(cv2.IMWRITE_WEBP_QUALITY), quality])
        if not success:
            raise ProcessingError(f"Failed to encode WebP at quality {quality} for {source_key}")
        return bytes(encoded.tobytes())

    async def generate_blurhash_and_dimensions(
        self, proxy_s3_key: str, interpolation: int = cv2.INTER_LANCZOS4
    ) -> tuple[str, int, int]:
        """Download proxy, generate blurhash and return dimensions."""
        proxy_bucket = self.settings.s3_bucket_proxies
        image_bytes = await self.storage.get_object(proxy_bucket, proxy_s3_key)

        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Failed to decode proxy image {proxy_s3_key}")

        h, w = image.shape[:2]

        small = cv2.resize(image, (32, 32), interpolation=interpolation)
        # Convert BGR to RGB for blurhash
        small_rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(small_rgb)

        blurhash = blurhash_encode(
            pil_image,
            x_components=4,
            y_components=3,
        )
        return blurhash, w, h
