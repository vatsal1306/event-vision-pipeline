"""Watermark service for applying photographer logos to proxies."""

from __future__ import annotations

from typing import Any

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
        self,
        s3_key: str,
        watermark_s3_key: str,
        bucket: str | None = None,
        output_format: str = ".webp",
        output_quality: int | None = None,
        watermark_scale: float = 0.20,
        watermark_x: float = 0.98,
        watermark_y: float = 0.98,
        watermark_opacity: float = 0.70,
        interpolation: int = cv2.INTER_LANCZOS4,
    ) -> None:
        """Download image and watermark, composite, re-upload."""
        target_bucket = bucket or self.settings.s3_bucket_proxies
        assets_bucket = self.settings.s3_bucket_assets
        proxy_bytes = await self.storage.get_object(target_bucket, s3_key)
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

        # Scale watermark proportionally based on user settings
        # The watermark_scale represents the width of the watermark relative to the image width
        target_wm_width = int(proxy.shape[1] * watermark_scale)
        wm_ratio = target_wm_width / watermark.shape[1]
        new_wm_width = target_wm_width
        new_wm_height = int(watermark.shape[0] * wm_ratio)
        watermark = cv2.resize(
            watermark, (new_wm_width, new_wm_height), interpolation=interpolation
        )

        # Apply global opacity
        watermark[:, :, 3] = (watermark[:, :, 3] * watermark_opacity).astype(np.uint8)

        # x/y are top-left offset ratios (0.0–1.0) relative to the image.
        x_offset = int(proxy.shape[1] * watermark_x)
        y_offset = int(proxy.shape[0] * watermark_y)

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

        # Encode and save
        if output_format == ".webp":
            quality = output_quality if output_quality is not None else self.settings.proxy_quality
            encode_param = cv2.IMWRITE_WEBP_QUALITY
            success, encoded_img = cv2.imencode(output_format, proxy, [int(encode_param), quality])
            if not success:
                raise ValueError(f"Failed to encode {output_format}")
            buffer = encoded_img.tobytes()
        else:
            # For JPEG originals: match the original file size to avoid bloat.
            # Cameras typically save at quality 85-92. Re-encoding at 100
            # inflates file size 2-3x without visible improvement.
            original_size = len(proxy_bytes)
            buffer = self._encode_jpeg_matching_size(proxy, original_size, output_quality)

        content_type = "image/webp" if output_format == ".webp" else "image/jpeg"

        await self.storage.put_object(
            bucket=target_bucket,
            key=s3_key,
            data=buffer,
            content_type=content_type,
            storage_class="STANDARD",
        )

    def _encode_jpeg_matching_size(
        self, image: np.ndarray[Any, Any], target_size: int, explicit_quality: int | None = None
    ) -> bytes:
        """Encode JPEG at a quality that keeps file size close to the original.

        If an explicit quality is provided, use it directly.  Otherwise, start
        at quality 95 and binary-search downward until the encoded size is
        within 10% of ``target_size``.  Never goes below quality 85 to avoid
        visible degradation.
        """
        if explicit_quality is not None:
            ok, enc = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), explicit_quality])
            if not ok:
                raise ValueError("Failed to encode JPEG")
            return enc.tobytes()

        # Binary search for the right quality
        lo, hi = 85, 95
        best_buf: bytes | None = None

        while lo <= hi:
            mid = (lo + hi) // 2
            ok, enc = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), mid])
            if not ok:
                raise ValueError("Failed to encode JPEG")
            buf = enc.tobytes()
            best_buf = buf

            if len(buf) <= target_size * 1.1:
                # Size is acceptable, try higher quality
                lo = mid + 1
            else:
                # Too large, reduce quality
                hi = mid - 1

        if best_buf is None:
            raise ValueError("Failed to encode JPEG")
        return best_buf
