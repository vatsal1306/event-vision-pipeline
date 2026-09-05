"""Password hashing and JWT creation helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.config import Settings, get_settings
from app.core.constants import JWTType

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_ALGORITHM = "HS256"
REFRESH_TOKEN_DENYLIST_PREFIX = "jwt:denylist:"


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt.

    Args:
        password: Plaintext password from the client.

    Returns:
        Bcrypt hash suitable for storage in ``photographers.password_hash``.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return True when the plaintext password matches the stored hash."""
    return pwd_context.verify(plain_password, password_hash)


def _utcnow() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(tz=timezone.utc)


def create_access_token(
    subject: str,
    *,
    settings: Settings | None = None,
) -> tuple[str, int]:
    """Create a short-lived access JWT for a photographer.

    Args:
        subject: Photographer UUID string placed in the ``sub`` claim.
        settings: Optional settings override (tests).

    Returns:
        Tuple of encoded token and expiry in seconds.
    """
    runtime_settings = settings or get_settings()
    expires_delta = timedelta(minutes=runtime_settings.jwt_access_token_expire_minutes)
    expires_at = _utcnow() + expires_delta
    payload = {
        "sub": subject,
        "type": JWTType.ACCESS.value,
        "exp": expires_at,
        "iat": _utcnow(),
    }
    token = jwt.encode(payload, runtime_settings.secret_key, algorithm=JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def create_refresh_token(
    subject: str,
    *,
    settings: Settings | None = None,
) -> tuple[str, str, int]:
    """Create a refresh JWT with a unique ``jti`` for rotation and logout.

    Args:
        subject: Photographer UUID string placed in the ``sub`` claim.
        settings: Optional settings override (tests).

    Returns:
        Tuple of encoded token, ``jti`` string, and expiry in seconds.
    """
    runtime_settings = settings or get_settings()
    expires_delta = timedelta(days=runtime_settings.jwt_refresh_token_expire_days)
    expires_at = _utcnow() + expires_delta
    token_jti = str(uuid.uuid4())
    payload = {
        "sub": subject,
        "type": JWTType.REFRESH.value,
        "jti": token_jti,
        "exp": expires_at,
        "iat": _utcnow(),
    }
    token = jwt.encode(payload, runtime_settings.secret_key, algorithm=JWT_ALGORITHM)
    return token, token_jti, int(expires_delta.total_seconds())


def decode_jwt(token: str, *, settings: Settings | None = None) -> dict[str, Any]:
    """Decode and validate a JWT, returning its claims.

    Args:
        token: Encoded JWT string.
        settings: Optional settings override (tests).

    Returns:
        Decoded JWT payload.

    Raises:
        JWTError: When the token is invalid or expired.
    """
    runtime_settings = settings or get_settings()
    return jwt.decode(token, runtime_settings.secret_key, algorithms=[JWT_ALGORITHM])


def refresh_token_denylist_key(jti: str) -> str:
    """Build the Redis key used to revoke a refresh token by ``jti``."""
    return f"{REFRESH_TOKEN_DENYLIST_PREFIX}{jti}"
