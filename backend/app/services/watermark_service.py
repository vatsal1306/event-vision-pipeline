"""Watermark service for applying photographer logos to proxies."""

from __future__ import annotations

import cv2
import numpy as np

from app.config import get_settings
from app.services.storage_service import StorageService


class WatermarkService:
    """Applies photographer's watermark to web-proxy images."""

    WATERMARK_MAX_WIDTH_RATIO = 0.2  # watermark max 20% of image width
    WATERMARK_PADDING_RATIO = 0.02  # 2% padding from edges

    def __init__(self, storage_service: StorageService) -> None:
        """Initialize with storage service."""
        self.storage = storage_service
        self.settings = get_settings()

    async def apply_watermark(
        self, proxy_s3_key: str, watermark_s3_key: str, interpolation: int = cv2.INTER_LANCZOS4
    ) -> None:
        """Download proxy and watermark, composite, re-upload."""
        proxy_bucket = self.settings.s3_bucket_proxies
        assets_bucket = self.settings.s3_bucket_assets
        proxy_bytes = await self.storage.get_object(proxy_bucket, proxy_s3_key)
        watermark_bytes = await self.storage.get_object(assets_bucket, watermark_s3_key)

        # Load proxy as BGR
        proxy_array = np.frombuffer(proxy_bytes, np.uint8)
        proxy = cv2.imdecode(proxy_array, cv2.IMREAD_COLOR)

        # Load watermark as BGRA (unchanged to keep alpha channel)
        wm_array = np.frombuffer(watermark_bytes, np.uint8)
        watermark = cv2.imdecode(wm_array, cv2.IMREAD_UNCHANGED)

        if proxy is None or watermark is None:
            raise ValueError("Failed to decode proxy or watermark image")

        # If watermark has no alpha channel, add one
        if len(watermark.shape) < 3 or watermark.shape[2] != 4:
            watermark = cv2.cvtColor(watermark, cv2.COLOR_BGR2BGRA)

        # Scale watermark proportionally
        max_wm_width = int(proxy.shape[1] * self.WATERMARK_MAX_WIDTH_RATIO)
        wm_ratio = max_wm_width / watermark.shape[1]
        new_wm_width = max_wm_width
        new_wm_height = int(watermark.shape[0] * wm_ratio)
        watermark = cv2.resize(
            watermark, (new_wm_width, new_wm_height), interpolation=interpolation
        )

        # Apply global opacity
        opacity = self.settings.watermark_opacity
        watermark[:, :, 3] = (watermark[:, :, 3] * opacity).astype(np.uint8)

        # Position: bottom-right with padding
        padding = int(proxy.shape[1] * self.WATERMARK_PADDING_RATIO)
        x_offset = proxy.shape[1] - watermark.shape[1] - padding
        y_offset = proxy.shape[0] - watermark.shape[0] - padding

        # Ensure ROI is within bounds
        y1, y2 = max(0, y_offset), min(proxy.shape[0], y_offset + watermark.shape[0])
        x1, x2 = max(0, x_offset), min(proxy.shape[1], x_offset + watermark.shape[1])

        # Calculate valid watermark area in case of clipping
        wm_y1 = 0 if y_offset >= 0 else -y_offset
        wm_y2 = wm_y1 + (y2 - y1)
        wm_x1 = 0 if x_offset >= 0 else -x_offset
        wm_x2 = wm_x1 + (x2 - x1)

        # Extract ROI and Alpha channels
        roi = proxy[y1:y2, x1:x2]
        wm_roi = watermark[wm_y1:wm_y2, wm_x1:wm_x2]

        if wm_roi.shape[0] > 0 and wm_roi.shape[1] > 0:
            alpha = wm_roi[:, :, 3] / 255.0
            alpha_inv = 1.0 - alpha

            # Composite
            for c in range(3):
                roi[:, :, c] = alpha * wm_roi[:, :, c] + alpha_inv * roi[:, :, c]

            proxy[y1:y2, x1:x2] = roi

        # Encode and save as WebP
        success, encoded_img = cv2.imencode(
            ".webp", proxy, [int(cv2.IMWRITE_WEBP_QUALITY), self.settings.proxy_quality]
        )
        if not success:
            raise ValueError("Failed to encode WebP")

        buffer = encoded_img.tobytes()

        await self.storage.put_object(
            bucket=proxy_bucket,
            key=proxy_s3_key,
            data=buffer,
            content_type="image/webp",
            storage_class="STANDARD",
        )
