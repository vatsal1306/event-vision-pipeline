"""Unit tests for SMTP and log email adapters."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.core.constants import EMAIL_PROVIDER_SMTP, OTP_CHANNEL_EMAIL
from app.core.exceptions import EmailDeliveryError
from app.services.email_service import EmailService, SmtpEmailAdapter
from app.services.sms_service import SMSService
from app.utils.otp import OTPService


@pytest.mark.asyncio
async def test_smtp_adapter_sends_multipart_message() -> None:
    """SMTP adapter posts the message when credentials are set."""
    settings = Settings(
        email_provider=EMAIL_PROVIDER_SMTP,
        email_from="admin@hpklabs.ai",
        email_from_name="SpotMe",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="admin@hpklabs.ai",
        smtp_password="app-password",
        smtp_use_tls=True,
    )
    with patch("app.services.email_service.aiosmtplib.send", new_callable=AsyncMock) as send:
        adapter = SmtpEmailAdapter(settings)
        result = await adapter.send_email(
            "studio@example.com",
            "Subject",
            "Plain text",
            html_body="<p>Hello</p>",
        )
    assert result is True
    send.assert_awaited_once()
    message = send.await_args.args[0]
    assert message["To"] == "studio@example.com"
    assert message["Subject"] == "Subject"


@pytest.mark.asyncio
async def test_smtp_adapter_returns_false_without_password() -> None:
    """Missing SMTP password must not attempt a network send."""
    settings = Settings(
        email_provider=EMAIL_PROVIDER_SMTP,
        smtp_user="admin@hpklabs.ai",
        smtp_password="",
    )
    with patch("app.services.email_service.aiosmtplib.send", new_callable=AsyncMock) as send:
        result = await EmailService(settings).send("a@b.com", "S", "B")
    assert result is False
    send.assert_not_called()


@pytest.mark.asyncio
async def test_smtp_password_spaces_are_stripped() -> None:
    """Google App Passwords copied with spaces must still authenticate."""
    settings = Settings(smtp_password="abcd efgh ijkl mnop")
    assert settings.smtp_password == "abcdefghijklmnop"


@pytest.mark.asyncio
async def test_otp_email_channel_does_not_sms() -> None:
    """Photographer email OTPs go through EmailService, not SMS."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.incr = AsyncMock(return_value=1)
    email_mock = AsyncMock()
    email_mock.send = AsyncMock(return_value=True)
    sms_mock = AsyncMock()
    settings = Settings(debug=True, email_provider="log")
    otp_service = OTPService(
        redis_mock,
        sms_mock,
        settings=settings,
        email_service=email_mock,
    )

    await otp_service.send_otp("studio@example.com", "login", channel=OTP_CHANNEL_EMAIL)

    email_mock.send.assert_awaited_once()
    sms_mock.send_otp.assert_not_called()
    sent = email_mock.send.await_args.kwargs
    assert sent["to"] == "studio@example.com"
    assert sent["html_body"]


@pytest.mark.asyncio
async def test_otp_email_failure_raises_outside_debug() -> None:
    """Production deletes the Redis OTP when email delivery fails."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.incr = AsyncMock(return_value=1)
    email_mock = AsyncMock()
    email_mock.send = AsyncMock(return_value=False)
    settings = Settings(debug=False, email_provider="smtp")
    otp_service = OTPService(
        redis_mock,
        SMSService(settings=settings),
        settings=settings,
        email_service=email_mock,
    )

    with pytest.raises(EmailDeliveryError):
        await otp_service.send_otp("studio@example.com", "login", channel=OTP_CHANNEL_EMAIL)
