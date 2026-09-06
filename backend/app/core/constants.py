"""Application constants."""

from __future__ import annotations

import enum


class TokenType(str, enum.Enum):
    """Types of JWTs issued by the platform."""

    ACCESS = "access"
    REFRESH = "refresh"
    GUEST = "guest"
    COUPLE = "couple"


# OTP configuration constants
OTP_LENGTH = 6
