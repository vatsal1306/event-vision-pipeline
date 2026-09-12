"""Tests for original-photo decoding used by FaceService."""

from __future__ import annotations

import io

from PIL import Image

from app.ml.image_io import decode_photo_bytes


def test_decode_jpeg_bytes() -> None:
    """JPEG originals decode to a BGR array."""
    image = Image.new("RGB", (16, 16), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    decoded = decode_photo_bytes(buffer.getvalue(), filename="a.jpg", mime_type="image/jpeg")
    assert decoded is not None
    assert decoded.shape[2] == 3


def test_decode_invalid_bytes_returns_none() -> None:
    """Garbage bytes do not raise."""
    assert decode_photo_bytes(b"nope", filename="a.jpg") is None
