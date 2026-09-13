"""SMS delivery adapters for OTP (log locally, Fast2SMS for real Indian SMS)."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.constants import (
    FAST2SMS_BULK_URL,
    FAST2SMS_HTTP_TIMEOUT_SECONDS,
    FAST2SMS_OTP_ROUTE,
    INDIAN_E164_PREFIX,
    INDIAN_MOBILE_DIGIT_COUNT,
    SMS_PROVIDER_FAST2SMS,
    SMS_PROVIDER_LOG,
)
from app.core.exceptions import BadRequestError
from app.core.logging import get_logger

logger = get_logger()


def indian_mobile_10(phone: str) -> str:
    """Return the 10-digit national number Fast2SMS expects.

    Args:
        phone: E.164 Indian mobile, for example ``+919876543210``.

    Returns:
        Ten digit string with no country code.

    Raises:
        BadRequestError: When the number is not ``+91`` plus 10 digits.
    """
    if phone.startswith(INDIAN_E164_PREFIX) and len(phone) == len(INDIAN_E164_PREFIX) + (
        INDIAN_MOBILE_DIGIT_COUNT
    ):
        national = phone[len(INDIAN_E164_PREFIX) :]
        if national.isdigit():
            return national
    raise BadRequestError("Phone must be a valid Indian mobile number (+91 and 10 digits).")


class SMSService:
    """Deliver OTP SMS via the configured provider."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the SMS adapter from runtime settings.

        Args:
            settings: Optional settings override (tests).
        """
        self.settings = settings or get_settings()

    async def send(self, phone: str, message: str) -> bool:
        """Send a free-text SMS. OTP delivery should use ``send_otp``.

        Log provider writes the body. Fast2SMS Quick OTP only supports the
        numeric OTP route, so this method is log-only for that provider.

        Args:
            phone: Destination phone number in E.164 format.
            message: SMS body text.

        Returns:
            True when the message was accepted (log mode), otherwise False.
        """
        if self.settings.sms_provider == SMS_PROVIDER_LOG:
            logger.info("sms.send", phone=phone, provider=SMS_PROVIDER_LOG)
            return True
        logger.warning(
            "sms.generic_send_unsupported",
            phone=phone,
            provider=self.settings.sms_provider,
        )
        return False

    async def send_otp(self, phone: str, otp: str) -> bool:
        """Deliver a numeric OTP to an Indian mobile number.

        Args:
            phone: Destination phone in E.164 (``+91`` + 10 digits).
            otp: Numeric OTP already stored (or about to be stored) in Redis.

        Returns:
            True when the provider accepted the message.

        Raises:
            BadRequestError: When ``phone`` is not a valid Indian mobile.
        """
        provider = self.settings.sms_provider
        if provider == SMS_PROVIDER_LOG:
            logger.info("sms.otp_log", phone=phone, provider=SMS_PROVIDER_LOG)
            return True
        if provider == SMS_PROVIDER_FAST2SMS:
            return await self._send_fast2sms_otp(phone, otp)

        logger.warning("sms.provider_not_configured", phone=phone, provider=provider)
        return False

    async def _send_fast2sms_otp(self, phone: str, otp: str) -> bool:
        """POST the OTP to Fast2SMS Quick OTP (``route=otp`` on bulkV2).

        Args:
            phone: E.164 Indian mobile.
            otp: Numeric code. Fast2SMS delivers ``Your OTP: {otp}``.

        Returns:
            True when the JSON body has ``return: true``.
        """
        api_key = self.settings.sms_api_key.strip()
        if not api_key:
            logger.warning("sms.fast2sms_missing_api_key", phone=phone)
            return False

        numbers = indian_mobile_10(phone)
        payload: dict[str, Any] = {
            "variables_values": otp,
            "route": FAST2SMS_OTP_ROUTE,
            "numbers": numbers,
        }
        headers = {
            "authorization": api_key,
            "accept": "application/json",
            "content-type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=FAST2SMS_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(FAST2SMS_BULK_URL, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning(
                "sms.fast2sms_http_error",
                phone=phone,
                error_type=type(exc).__name__,
            )
            return False

        accepted, request_id = self._parse_fast2sms_response(response)
        if accepted:
            logger.info(
                "sms.fast2sms_accepted",
                phone=phone,
                request_id=request_id,
                status_code=response.status_code,
            )
            return True

        logger.warning(
            "sms.fast2sms_rejected",
            phone=phone,
            status_code=response.status_code,
            request_id=request_id,
        )
        return False

    def _parse_fast2sms_response(self, response: httpx.Response) -> tuple[bool, str | None]:
        """Interpret Fast2SMS JSON. Success requires HTTP 2xx and ``return`` true.

        Args:
            response: Raw HTTP response from Fast2SMS.

        Returns:
            Tuple of (accepted, request_id if present).
        """
        try:
            body = response.json()
        except ValueError:
            return False, None
        if not isinstance(body, dict):
            return False, None
        request_id = body.get("request_id")
        request_id_str = str(request_id) if request_id is not None else None
        accepted = response.is_success and body.get("return") is True
        return accepted, request_id_str
