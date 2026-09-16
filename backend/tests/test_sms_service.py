"""Tests for Fast2SMS OTP delivery and SMS failure handling."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.config import Settings
from app.core.constants import SMS_PROVIDER_FAST2SMS, SMS_PROVIDER_LOG
from app.core.exceptions import BadRequestError, SMSDeliveryError
from app.services.sms_service import SMSService, indian_mobile_10
from app.utils.otp import OTPService

PHONE = "+919876543210"
OTP = "482913"


def _fast2sms_settings(*, debug: bool, api_key: str = "test-fast2sms-key") -> Settings:
    """Build settings that target Fast2SMS without loading a real .env key."""
    return Settings(
        debug=debug,
        environment="production",
        sms_provider=SMS_PROVIDER_FAST2SMS,
        sms_api_key=api_key,
        email_provider="none",
    )


def test_indian_mobile_10_strips_country_code() -> None:
    """Fast2SMS expects a 10-digit national number."""
    assert indian_mobile_10(PHONE) == "9876543210"


def test_indian_mobile_10_rejects_non_indian() -> None:
    """Non +91 numbers must not be sent to Fast2SMS."""
    with pytest.raises(BadRequestError):
        indian_mobile_10("+14155550100")


@pytest.mark.asyncio
async def test_log_provider_does_not_call_fast2sms(respx_mock) -> None:
    """Default log provider must not hit Fast2SMS."""
    settings = Settings(debug=True, sms_provider=SMS_PROVIDER_LOG, sms_api_key="")
    service = SMSService(settings=settings)
    assert await service.send_otp(PHONE, OTP) is True
    assert respx_mock["fast2sms"].call_count == 0


@pytest.mark.asyncio
async def test_fast2sms_posts_otp_route(respx_mock) -> None:
    """Successful Fast2SMS send uses route=otp and the 10-digit number."""
    route = respx_mock["fast2sms"]
    route.mock(
        return_value=httpx.Response(
            200,
            json={"return": True, "request_id": "req-1", "message": "SMS sent successfully."},
        )
    )
    service = SMSService(settings=_fast2sms_settings(debug=True))
    assert await service.send_otp(PHONE, OTP) is True
    assert route.called
    request = route.calls.last.request
    assert request.headers["authorization"] == "test-fast2sms-key"
    payload = json.loads(request.content)
    assert payload["route"] == "otp"
    assert payload["numbers"] == "9876543210"
    assert payload["variables_values"] == OTP
    assert respx_mock["fast2sms"].call_count == 1


@pytest.mark.asyncio
async def test_fast2sms_falls_back_to_quick_sms_after_otp_kyc(respx_mock) -> None:
    """OTP route KYC (996) should retry Quick SMS ``route=q``."""

    def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload.get("route") == "otp":
            return httpx.Response(
                400,
                json={
                    "return": False,
                    "status_code": 996,
                    "message": "Before using OTP SMS API, complete KYC.",
                },
            )
        assert payload.get("route") == "q"
        assert "482913" in payload["message"]
        return httpx.Response(200, json={"return": True, "request_id": "quick-1"})

    respx_mock["fast2sms"].mock(side_effect=_handler)
    service = SMSService(settings=_fast2sms_settings(debug=False))
    assert await service.send_otp(PHONE, OTP) is True
    assert respx_mock["fast2sms"].call_count == 2


@pytest.mark.asyncio
async def test_fast2sms_invalid_number_sets_user_message(respx_mock) -> None:
    """Provider status 411 should explain the number was rejected."""
    respx_mock["fast2sms"].mock(
        return_value=httpx.Response(
            400,
            json={"return": False, "status_code": 411, "message": "Invalid Numbers"},
        )
    )
    service = SMSService(settings=_fast2sms_settings(debug=False))
    assert await service.send_otp(PHONE, OTP) is False
    assert service.last_user_message is not None
    assert "real Indian mobile" in service.last_user_message


@pytest.mark.asyncio
async def test_fast2sms_rejects_false_return(respx_mock) -> None:
    """Provider JSON ``return: false`` is treated as a failed send."""
    respx_mock["fast2sms"].mock(
        return_value=httpx.Response(
            200, json={"return": False, "message": "Invalid authentication"}
        )
    )
    service = SMSService(settings=_fast2sms_settings(debug=False))
    assert await service.send_otp(PHONE, OTP) is False


@pytest.mark.asyncio
async def test_fast2sms_missing_key_does_not_call_api(respx_mock) -> None:
    """Empty API key must not call Fast2SMS."""
    service = SMSService(settings=_fast2sms_settings(debug=True, api_key=""))
    assert await service.send_otp(PHONE, OTP) is False
    assert respx_mock["fast2sms"].call_count == 0


@pytest.mark.asyncio
async def test_otp_send_raises_when_sms_fails_outside_debug() -> None:
    """Production (debug off) must not keep a Redis OTP if SMS failed."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.incr = AsyncMock(return_value=1)
    sms_mock = AsyncMock()
    sms_mock.send_otp = AsyncMock(return_value=False)
    sms_mock.last_user_message = None
    settings = Settings(debug=False, sms_provider=SMS_PROVIDER_FAST2SMS, sms_api_key="k")
    otp_service = OTPService(redis_mock, sms_mock, settings=settings)

    with pytest.raises(SMSDeliveryError) as exc_info:
        await otp_service.send_otp(PHONE, "login")

    assert exc_info.value.code == "SMS_DELIVERY_FAILED"
    redis_mock.delete.assert_awaited()


@pytest.mark.asyncio
async def test_otp_send_keeps_code_when_sms_fails_in_debug() -> None:
    """Debug mode keeps Redis OTP so ``123456`` / logs still work if SMS fails."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.incr = AsyncMock(return_value=1)
    sms_mock = AsyncMock()
    sms_mock.send_otp = AsyncMock(return_value=False)
    sms_mock.last_user_message = None
    settings = Settings(debug=True, sms_provider=SMS_PROVIDER_FAST2SMS, sms_api_key="k")
    otp_service = OTPService(redis_mock, sms_mock, settings=settings)

    await otp_service.send_otp(PHONE, "login")

    redis_mock.setex.assert_awaited()
    delete_keys = [call.args[0] for call in redis_mock.delete.await_args_list]
    assert not any(str(key).startswith("otp:+91") for key in delete_keys)
