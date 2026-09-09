"""Tests for HMAC-signed photo preview URLs."""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from app.core.exceptions import AuthenticationError
from app.utils.media_tokens import (
    build_photo_preview_url,
    sign_photo_preview,
    verify_photo_preview_signature,
)


def test_preview_signature_round_trip() -> None:
    """Accept a freshly signed preview token."""
    event_id = uuid4()
    photo_id = uuid4()
    expires_at = int(time.time()) + 60
    signature = sign_photo_preview(event_id, photo_id, expires_at)
    verify_photo_preview_signature(event_id, photo_id, expires_at, signature)


def test_preview_signature_rejects_tampering() -> None:
    """Reject a signature that does not match the photo id."""
    event_id = uuid4()
    expires_at = int(time.time()) + 60
    signature = sign_photo_preview(event_id, uuid4(), expires_at)
    with pytest.raises(AuthenticationError):
        verify_photo_preview_signature(event_id, uuid4(), expires_at, signature)


def test_build_photo_preview_url_contains_query() -> None:
    """Preview URLs include expiry and signature query params."""
    url = build_photo_preview_url(uuid4(), uuid4())
    assert "/preview?" in url
    assert "expires=" in url
    assert "sig=" in url
