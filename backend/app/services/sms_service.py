"""SMS delivery adapters for OTP (log locally, Fast2SMS for real Indian SMS)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.constants import (
    FAST2SMS_BULK_URL,
    FAST2SMS_HTTP_TIMEOUT_SECONDS,
    FAST2SMS_OTP_FALLBACK_STATUS_CODES,
    FAST2SMS_OTP_ROUTE,
    FAST2SMS_QUICK_ROUTE,
    INDIAN_E164_PREFIX,
    INDIAN_MOBILE_DIGIT_COUNT,
    OTP_SMS_BODY_TEMPLATE,
    SMS_PROVIDER_FAST2SMS,
    SMS_PROVIDER_LOG,
)
from app.core.exceptions import BadRequestError, SMSDeliveryError
from app.core.logging import get_logger

logger = get_logger()

# Fast2SMS JSON ``status_code`` (not the HTTP status). Safe to show to the user.
_FAST2SMS_USER_MESSAGES: dict[int, str] = {
    411: "That mobile number was rejected. Use a real Indian mobile you can receive SMS on.",
    412: "SMS API key is invalid. Check SMS_API_KEY in backend/.env.",
    413: "SMS API key is disabled in Fast2SMS.",
    416: "Fast2SMS wallet is empty. Add credits and try again.",
    995: "Too many SMS to the same number. Wait a few minutes and try again.",
    996: "Fast2SMS OTP sending needs KYC on their dashboard.",
    999: "Fast2SMS requires a minimum ₹100 wallet top-up before the API works.",
}


@dataclass(frozen=True)
class _Fast2SMSParse:
    """Parsed Fast2SMS JSON body (HTTP layer is separate)."""

    accepted: bool
    request_id: str | None
    provider_status: int | None
    provider_message: str | None


def indian_mobile_10(phone: str) -> str:
    """Return the 10-digit national number Fast2SMS expects.

    Args:
        phone: E.164 Indian mobile, for example ``+919876543210``.

    Returns:
        Ten digit string with no country code.

    Raises:
        BadRequestError: When the number is not ``+91`` plus 10 digits.
    """
    expected_len = len(INDIAN_E164_PREFIX) + INDIAN_MOBILE_DIGIT_COUNT
    if phone.startswith(INDIAN_E164_PREFIX) and len(phone) == expected_len:
        national = phone[len(INDIAN_E164_PREFIX) :]
        if national.isdigit():
            return national
    raise BadRequestError("Phone must be a valid Indian mobile number (+91 and 10 digits).")


def fast2sms_user_message(provider_status: int | None) -> str:
    """Map a Fast2SMS status_code to a client-safe error string."""
    if provider_status is not None and provider_status in _FAST2SMS_USER_MESSAGES:
        return _FAST2SMS_USER_MESSAGES[provider_status]
    return SMSDeliveryError().message


def _stringify_fast2sms_message(raw: object) -> str | None:
    """Fast2SMS ``message`` is a string or a list of strings."""
    if raw is None:
        return None
    if isinstance(raw, list):
        parts = [str(item) for item in raw if item is not None]
        return "; ".join(parts) if parts else None
    return str(raw)


class SMSService:
    """Deliver OTP SMS via the configured provider."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the SMS adapter from runtime settings.

        Args:
            settings: Optional settings override (tests).
        """
        self.settings = settings or get_settings()
        self.last_user_message: str | None = None

    async def send(self, phone: str, message: str) -> bool:
        """Send a free-text SMS. OTP delivery should use ``send_otp``.

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
        self.last_user_message = None
        provider = self.settings.sms_provider
        if self.settings.environment.lower() == "development":
            logger.info("sms.otp_log_dev", phone=phone, otp=otp)
            return True

        if provider == SMS_PROVIDER_LOG:
            logger.info("sms.otp_log", phone=phone, provider=SMS_PROVIDER_LOG)
            return True
        if provider == SMS_PROVIDER_FAST2SMS:
            return await self._send_fast2sms_otp(phone, otp)

        logger.warning("sms.provider_not_configured", phone=phone, provider=provider)
        return False

    async def _send_fast2sms_otp(self, phone: str, otp: str) -> bool:
        """Send via OTP route, then Quick SMS if Fast2SMS requires KYC/DLT.

        Args:
            phone: E.164 Indian mobile.
            otp: Numeric code.

        Returns:
            True when Fast2SMS accepted a send.
        """
        api_key = self.settings.sms_api_key.strip()
        if not api_key:
            logger.warning("sms.fast2sms_missing_api_key", phone=phone)
            self.last_user_message = "SMS API key is not set. Add SMS_API_KEY in backend/.env."
            return False

        numbers = indian_mobile_10(phone)
        otp_payload: dict[str, Any] = {
            "variables_values": otp,
            "route": FAST2SMS_OTP_ROUTE,
            "numbers": numbers,
        }
        parsed = await self._post_fast2sms(phone, api_key, otp_payload)
        if parsed.accepted:
            return True

        if parsed.provider_status in FAST2SMS_OTP_FALLBACK_STATUS_CODES:
            logger.info(
                "sms.fast2sms_quick_fallback",
                phone=phone,
                provider_status=parsed.provider_status,
            )
            quick_payload: dict[str, Any] = {
                "message": OTP_SMS_BODY_TEMPLATE.format(otp=otp),
                "route": FAST2SMS_QUICK_ROUTE,
                "numbers": numbers,
            }
            parsed = await self._post_fast2sms(phone, api_key, quick_payload)
            if parsed.accepted:
                return True

        self.last_user_message = fast2sms_user_message(parsed.provider_status)
        return False

    async def _post_fast2sms(
        self,
        phone: str,
        api_key: str,
        payload: dict[str, Any],
    ) -> _Fast2SMSParse:
        """POST one Fast2SMS bulkV2 payload and log the outcome (never the OTP)."""
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
                route=payload.get("route"),
            )
            return _Fast2SMSParse(False, None, None, None)

        parsed = self._parse_fast2sms_response(response)
        if parsed.accepted:
            logger.info(
                "sms.fast2sms_accepted",
                phone=phone,
                request_id=parsed.request_id,
                status_code=response.status_code,
                route=payload.get("route"),
            )
            return parsed

        logger.warning(
            "sms.fast2sms_rejected",
            phone=phone,
            status_code=response.status_code,
            provider_status=parsed.provider_status,
            provider_message=parsed.provider_message,
            request_id=parsed.request_id,
            route=payload.get("route"),
        )
        return parsed

    def _parse_fast2sms_response(self, response: httpx.Response) -> _Fast2SMSParse:
        """Interpret Fast2SMS JSON. Success requires HTTP 2xx and ``return`` true."""
        try:
            body = response.json()
        except ValueError:
            return _Fast2SMSParse(False, None, None, None)
        if not isinstance(body, dict):
            return _Fast2SMSParse(False, None, None, None)

        request_id = body.get("request_id")
        request_id_str = str(request_id) if request_id is not None else None
        raw_status = body.get("status_code")
        provider_status: int | None
        try:
            provider_status = int(raw_status) if raw_status is not None else None
        except (TypeError, ValueError):
            provider_status = None
        provider_message = _stringify_fast2sms_message(body.get("message"))
        accepted = response.is_success and body.get("return") is True
        return _Fast2SMSParse(accepted, request_id_str, provider_status, provider_message)
