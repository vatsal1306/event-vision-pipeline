"""HMAC-signed URLs so photo previews can load in <img> without a JWT header."""

from __future__ import annotations

import hashlib
import hmac
import time
from uuid import UUID

from app.config import get_settings
from app.core.exceptions import AuthenticationError, BadRequestError


def build_photo_preview_url(event_id: UUID, photo_id: UUID) -> str:
    """Return a time-limited preview URL for a photo.

    Args:
        event_id: Event that owns the photo.
        photo_id: Photo to preview.

    Returns:
        Absolute URL including ``expires`` and ``sig`` query parameters.
    """
    settings = get_settings()
    expires_at = int(time.time()) + settings.s3_presigned_url_expiry
    signature = sign_photo_preview(event_id, photo_id, expires_at)
    return (
        f"{settings.api_base_url}/api/v1/events/{event_id}/photos/{photo_id}"
        f"/preview?expires={expires_at}&sig={signature}"
    )


def sign_photo_preview(event_id: UUID, photo_id: UUID, expires_at: int) -> str:
    """Create an HMAC signature for a photo preview request."""
    settings = get_settings()
    message = f"{event_id}.{photo_id}.{expires_at}".encode()
    return hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()


def verify_photo_preview_signature(
    event_id: UUID, photo_id: UUID, expires_at: int, signature: str
) -> None:
    """Validate a preview signature or raise an authentication error.

    Args:
        event_id: Event from the request path.
        photo_id: Photo from the request path.
        expires_at: Unix timestamp from the query string.
        signature: Hex HMAC from the query string.

    Raises:
        BadRequestError: If the expiry is missing or malformed.
        AuthenticationError: If the link is expired or the signature is invalid.
    """
    if expires_at <= 0:
        raise BadRequestError("Invalid preview expiry")
    if expires_at < int(time.time()):
        raise AuthenticationError("Preview link expired")

    expected = sign_photo_preview(event_id, photo_id, expires_at)
    if not hmac.compare_digest(expected, signature):
        raise AuthenticationError("Invalid preview signature")
