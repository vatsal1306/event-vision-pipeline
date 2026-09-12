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


def test_decode_empty_bytes_returns_none() -> None:
    """Empty payloads are treated as decode failures."""
    assert decode_photo_bytes(b"", filename="a.jpg") is None


def test_decode_png_bytes() -> None:
    """PNG originals also decode to BGR."""
    image = Image.new("RGB", (12, 10), color="blue")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    decoded = decode_photo_bytes(buffer.getvalue(), filename="a.png", mime_type="image/png")
    assert decoded is not None
    assert decoded.shape[0] == 10
    assert decoded.shape[1] == 12


def test_decode_heic_garbage_returns_none() -> None:
    """Invalid HEIC bytes should not raise out of the decoder."""
    assert decode_photo_bytes(b"not-heic", filename="a.heic", mime_type="image/heic") is None
