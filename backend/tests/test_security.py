"""Unit tests for JWT and password helpers."""

from __future__ import annotations

import pytest
from jose import JWTError

from app.core.constants import JWTType
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_jwt,
    hash_password,
    verify_password,
)


def test_hash_password_and_verify_round_trip() -> None:
    """Password hashing should verify successfully for the original secret."""
    password = "Password1!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPass1!", hashed) is False


def test_access_token_contains_access_type_claim() -> None:
    """Access tokens must include type=access for API dependencies."""
    token, expires_in = create_access_token("00000000-0000-0000-0000-000000000001")
    payload = decode_jwt(token)
    assert payload["type"] == JWTType.ACCESS.value
    assert payload["sub"] == "00000000-0000-0000-0000-000000000001"
    assert expires_in == 15 * 60


def test_refresh_token_contains_jti_and_refresh_type() -> None:
    """Refresh tokens must include jti for rotation and logout denylist."""
    token, jti, _expires = create_refresh_token("00000000-0000-0000-0000-000000000001")
    payload = decode_jwt(token)
    assert payload["type"] == JWTType.REFRESH.value
    assert payload["jti"] == jti


def test_decode_jwt_rejects_tampered_token() -> None:
    """Tampered tokens must fail validation."""
    token, _expires = create_access_token("00000000-0000-0000-0000-000000000001")
    with pytest.raises(JWTError):
        decode_jwt(f"{token}invalid")
