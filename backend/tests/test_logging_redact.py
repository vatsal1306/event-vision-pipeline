"""Unit tests for log redaction."""

from __future__ import annotations

from app.core.logging import REDACTED_VALUE, redact_sensitive_data


def test_redact_sensitive_data_strips_secrets() -> None:
    """Passwords, OTP codes, and tokens must not appear in log events."""
    event = {
        "event": "auth.login",
        "password": "super-secret",
        "otp_code": "123456",
        "access_token": "jwt-here",
        "user_id": "abc",
        "nested": {"refresh_token": "also-secret", "email": "a@b.c"},
    }
    redacted = redact_sensitive_data(None, "info", event)
    assert redacted["password"] == REDACTED_VALUE
    assert redacted["otp_code"] == REDACTED_VALUE
    assert redacted["access_token"] == REDACTED_VALUE
    assert redacted["user_id"] == "abc"
    nested = redacted["nested"]
    assert isinstance(nested, dict)
    assert nested["refresh_token"] == REDACTED_VALUE
    assert nested["email"] == "a@b.c"
