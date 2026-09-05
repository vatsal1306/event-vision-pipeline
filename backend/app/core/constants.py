"""Shared constants that must not be scattered as magic strings or numbers."""

from __future__ import annotations

from enum import Enum

OTP_LENGTH = 6
"""Numeric OTP length shown to users and stored in Redis."""

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 16
PASSWORD_PATTERN = (
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9])"
    rf".{{{PASSWORD_MIN_LENGTH},{PASSWORD_MAX_LENGTH}}}$"
)
"""Password must include upper, lower, digit, special char, and be 8-16 chars."""

INDIAN_PHONE_PATTERN = r"^\+91\d{10}$"

REQUEST_ID_HEADER = "X-Request-ID"
"""HTTP header used to correlate logs for a single request."""

MAX_INCOMING_REQUEST_ID_LENGTH = 128
"""Reject oversized client-supplied request IDs to avoid log abuse."""


class JWTType(str, Enum):
    """JWT `type` claim values used across photographer, guest, and couple auth."""

    ACCESS = "access"
    REFRESH = "refresh"
    GUEST = "guest"
    COUPLE = "couple"
