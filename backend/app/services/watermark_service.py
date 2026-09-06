"""Watermark service for applying photographer logos to proxies."""

from __future__ import annotations

import io

from PIL import Image

from app.config import get_settings
from app.services.storage_service import StorageService


class WatermarkService:
    """Applies photographer's watermark to web-proxy images."""

    WATERMARK_OPACITY = 0.4  # 40% opacity (semi-transparent)
    WATERMARK_MAX_WIDTH_RATIO = 0.2  # watermark max 20% of image width
    WATERMARK_PADDING_RATIO = 0.02  # 2% padding from edges

    def __init__(self, storage_service: StorageService) -> None:
        """Initialize with storage service."""
        self.storage = storage_service
        self.settings = get_settings()

    async def apply_watermark(self, proxy_s3_key: str, watermark_s3_key: str) -> None:
        """Download proxy and watermark, composite, re-upload."""
        proxy_bucket = self.settings.s3_bucket_proxies
        assets_bucket = self.settings.s3_bucket_assets
        proxy_bytes = await self.storage.get_object(proxy_bucket, proxy_s3_key)
        watermark_bytes = await self.storage.get_object(assets_bucket, watermark_s3_key)

        proxy = Image.open(io.BytesIO(proxy_bytes)).convert("RGBA")
        watermark = Image.open(io.BytesIO(watermark_bytes)).convert("RGBA")

        # Scale watermark proportionally
        max_wm_width = int(proxy.width * self.WATERMARK_MAX_WIDTH_RATIO)
        wm_ratio = max_wm_width / watermark.width
        wm_size = (max_wm_width, int(watermark.height * wm_ratio))
        watermark = watermark.resize(wm_size, Image.Resampling.LANCZOS)

        # Apply opacity
        alpha = watermark.split()[3]
        alpha = alpha.point(lambda p: int(p * self.WATERMARK_OPACITY))
        watermark.putalpha(alpha)

        # Position: bottom-right with padding
        padding = int(proxy.width * self.WATERMARK_PADDING_RATIO)
        position = (
            proxy.width - watermark.width - padding,
            proxy.height - watermark.height - padding,
        )

        # Composite
        proxy.paste(watermark, position, watermark)

        # Convert back to RGB and save as WebP
        result = proxy.convert("RGB")
        buffer = io.BytesIO()
        result.save(buffer, format="WEBP", quality=82)

        await self.storage.put_object(
            bucket=proxy_bucket,
            key=proxy_s3_key,
            data=buffer.getvalue(),
            content_type="image/webp",
            storage_class="STANDARD",
        )
