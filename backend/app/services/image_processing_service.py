"""Image processing service for proxies and blurhash."""

from __future__ import annotations

import uuid
from typing import Any

import cv2
import numpy as np
from blurhash import encode as blurhash_encode  # type: ignore[import-untyped]
from PIL import Image
from pillow_heif import read_heif  # type: ignore

from app.config import get_settings
from app.services.storage_service import StorageService


class ImageProcessingService:
    """Generates web-optimized proxy images from originals."""

    PROXY_TARGET_SIZE_KB = 500

    def __init__(self, storage_service: StorageService) -> None:
        """Initialize with storage service."""
        self.storage = storage_service
        self.settings = get_settings()

    async def generate_web_proxy(
        self, original_s3_key: str, event_id: str, interpolation: int = cv2.INTER_LANCZOS4
    ) -> str:
        """Download original, generate optimized proxy, upload to hot storage."""
        original_bucket = self.settings.s3_bucket_originals
        proxy_bucket = self.settings.s3_bucket_proxies
        image_bytes = await self.storage.get_object(original_bucket, original_s3_key)

        # Handle HEIC or standard decoding
        if original_s3_key.lower().endswith((".heic", ".heif")):
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

        return proxy_s3_key

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
