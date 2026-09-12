"""Decode uploaded originals (JPEG/PNG/WebP/HEIC) to OpenCV BGR images."""

from __future__ import annotations

import numpy as np

_HEIC_EXTENSIONS = (".heic", ".heif")
_HEIC_MIME_TYPES = {"image/heic", "image/heif"}


def decode_photo_bytes(
    image_bytes: bytes,
    *,
    filename: str = "",
    mime_type: str = "",
) -> np.ndarray | None:
    """Decode original photo bytes to a BGR ndarray.

    HEIC/HEIF originals are decoded via pillow-heif. JPEG/PNG/WebP use OpenCV.

    Args:
        image_bytes: Raw file content from object storage.
        filename: Original filename, used to detect HEIC.
        mime_type: Declared MIME type, used to detect HEIC.

    Returns:
        BGR image, or ``None`` when decoding fails.
    """
    if not image_bytes:
        return None

    lowered_name = filename.lower()
    lowered_mime = mime_type.lower().split(";")[0].strip()
    is_heic = lowered_name.endswith(_HEIC_EXTENSIONS) or lowered_mime in _HEIC_MIME_TYPES
    if is_heic:
        return _decode_heic(image_bytes)

    import cv2

    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    if buffer.size == 0:
        return None
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    return image


def _decode_heic(image_bytes: bytes) -> np.ndarray | None:
    """Decode HEIC/HEIF bytes to BGR using pillow-heif."""
    import cv2
    from pillow_heif import read_heif

    try:
        heif_file = read_heif(image_bytes)
        rgb = np.asarray(heif_file)
    except Exception:
        return None
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        return None
    return cv2.cvtColor(rgb[:, :, :3], cv2.COLOR_RGB2BGR)
