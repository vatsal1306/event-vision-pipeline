"""Shared photographer registration OTP helpers for API tests."""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

from app.services.sms_service import SMSService
from app.utils.otp import OTPService


async def register_and_verify(
    client: AsyncClient,
    redis_client: Any,
    payload: dict[str, str],
) -> dict[str, Any]:
    """Register a photographer and submit both SMS and email OTPs.

    Args:
        client: HTTP client targeting the API.
        redis_client: Redis used by OTPService.
        payload: Register JSON body.

    Returns:
        Verify-OTP JSON (tokens and photographer).
    """
    register = await client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    otp_service = OTPService(redis_client, SMSService())
    phone_otp = await otp_service.peek_otp(payload["phone"], "registration")
    email_otp = await otp_service.peek_otp(payload["email"].lower(), "registration")
    assert phone_otp is not None
    assert email_otp is not None

    verify = await client.post(
        "/api/v1/auth/verify-otp",
        json={
            "purpose": "registration",
            "phone": payload["phone"],
            "email": payload["email"],
            "phone_otp": phone_otp,
            "email_otp": email_otp,
        },
    )
    assert verify.status_code == 200, verify.text
    return verify.json()
