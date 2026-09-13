"""OTP generation, Redis storage, and verification."""

from __future__ import annotations

import secrets
import string

import redis.asyncio as redis

from app.config import Settings, get_settings
from app.core.constants import OTP_CHANNEL_EMAIL, OTP_CHANNEL_SMS, OTP_LENGTH
from app.core.exceptions import (
    EmailDeliveryError,
    OTPCooldownError,
    OTPMaxAttemptsError,
    SMSDeliveryError,
)
from app.core.logging import get_logger
from app.services.email_service import EmailService, get_email_service
from app.services.email_templates import otp_email_content
from app.services.sms_service import SMSService

logger = get_logger()

OTP_KEY_PREFIX = "otp:"
OTP_ATTEMPTS_PREFIX = "otp:attempts:"
OTP_COOLDOWN_PREFIX = "otp:cooldown:"

_OTP_PURPOSE_LABELS = {
    "registration": "registration",
    "login": "login",
    "password_reset": "password reset",
}


class OTPService:
    """OTP generation, storage, and verification using Redis."""

    def __init__(
        self,
        redis_client: redis.Redis,
        sms_service: SMSService,
        settings: Settings | None = None,
        email_service: EmailService | None = None,
    ) -> None:
        """Initialize OTP helpers with Redis and delivery adapters.

        Args:
            redis_client: Async Redis client.
            sms_service: SMS delivery adapter (guest, couple, photographer phone).
            settings: Optional settings override (tests).
            email_service: Email delivery adapter for photographer email OTPs.
        """
        self.redis = redis_client
        self.sms_service = sms_service
        self.settings = settings or get_settings()
        self.email_service = email_service or get_email_service()

    @property
    def otp_expiry_seconds(self) -> int:
        """OTP lifetime in seconds."""
        return self.settings.otp_expiry_seconds

    @property
    def max_attempts(self) -> int:
        """Maximum verification attempts before requiring a new OTP."""
        return self.settings.otp_max_attempts

    @property
    def cooldown_seconds(self) -> int:
        """Minimum wait time between OTP sends for the same destination and purpose."""
        return self.settings.otp_cooldown_seconds

    async def send_otp(
        self,
        destination: str,
        purpose: str,
        *,
        channel: str = OTP_CHANNEL_SMS,
    ) -> None:
        """Generate an OTP, store it in Redis, and deliver it.

        Args:
            destination: E.164 phone number or photographer email (Redis key).
            purpose: OTP purpose namespace (registration, login, password_reset).
            channel: ``sms`` or ``email``. Guests and couples must use SMS.

        Raises:
            OTPCooldownError: When another OTP was sent too recently.
            SMSDeliveryError: When SMS delivery fails and debug mode is off.
            EmailDeliveryError: When email delivery fails and debug mode is off.
        """
        cooldown_key = f"{OTP_COOLDOWN_PREFIX}{destination}:{purpose}"

        count = await self.redis.get(cooldown_key)
        if count and int(count) >= 2:
            raise OTPCooldownError()

        otp = self._generate_otp()
        otp_key = f"{OTP_KEY_PREFIX}{destination}:{purpose}"
        attempts_key = f"{OTP_ATTEMPTS_PREFIX}{destination}:{purpose}"

        await self.redis.setex(otp_key, self.otp_expiry_seconds, otp)

        new_count = await self.redis.incr(cooldown_key)
        if new_count == 1:
            await self.redis.expire(cooldown_key, self.cooldown_seconds)

        await self.redis.delete(attempts_key)

        delivered = await self._deliver(destination, purpose, otp, channel)
        if self.settings.debug:
            logger.info(
                "otp.dev_delivery",
                destination=destination,
                purpose=purpose,
                channel=channel,
                local_only=otp,
            )

        if delivered:
            return

        if self.settings.debug:
            logger.warning(
                "otp.delivery_failed_debug_fallback",
                destination=destination,
                purpose=purpose,
                channel=channel,
            )
            return

        await self.redis.delete(otp_key)
        await self.redis.delete(cooldown_key)
        if channel == OTP_CHANNEL_EMAIL:
            detail = getattr(self.email_service, "last_user_message", None)
            raise EmailDeliveryError(detail) if detail else EmailDeliveryError()
        detail = self.sms_service.last_user_message
        raise SMSDeliveryError(detail) if detail else SMSDeliveryError()

    async def verify_otp(self, destination: str, purpose: str, otp: str) -> bool:
        """Verify an OTP against the stored value with attempt limiting.

        Args:
            destination: E.164 phone number or email used when the OTP was stored.
            purpose: OTP purpose namespace.
            otp: User-supplied OTP code.

        Returns:
            True when the OTP matches and is consumed.

        Raises:
            OTPMaxAttemptsError: When verification attempts are exhausted.
        """
        if self.settings.debug and otp == "123456":
            return True

        attempts_key = f"{OTP_ATTEMPTS_PREFIX}{destination}:{purpose}"
        attempts = await self.redis.incr(attempts_key)
        await self.redis.expire(attempts_key, self.otp_expiry_seconds)

        if attempts > self.max_attempts:
            raise OTPMaxAttemptsError()

        otp_key = f"{OTP_KEY_PREFIX}{destination}:{purpose}"
        stored_otp = await self.redis.get(otp_key)

        if stored_otp and stored_otp == otp:
            await self.redis.delete(otp_key)
            await self.redis.delete(attempts_key)
            return True
        return False

    async def verify_otp_pair(
        self,
        *,
        phone: str,
        phone_otp: str,
        email: str,
        email_otp: str,
        purpose: str,
    ) -> bool:
        """Verify two independent OTPs and consume both only when both match.

        Args:
            phone: Photographer E.164 phone.
            phone_otp: Code sent via SMS.
            email: Photographer email (lowercased).
            email_otp: Code sent via email.
            purpose: Shared purpose namespace for both destinations.

        Returns:
            True when both codes match (or debug bypass applies).

        Raises:
            OTPMaxAttemptsError: When either destination has exhausted attempts.
        """
        if self.settings.debug and phone_otp == "123456" and email_otp == "123456":
            return True

        phone_attempts_key = f"{OTP_ATTEMPTS_PREFIX}{phone}:{purpose}"
        email_attempts_key = f"{OTP_ATTEMPTS_PREFIX}{email}:{purpose}"
        phone_attempts = await self.redis.incr(phone_attempts_key)
        email_attempts = await self.redis.incr(email_attempts_key)
        await self.redis.expire(phone_attempts_key, self.otp_expiry_seconds)
        await self.redis.expire(email_attempts_key, self.otp_expiry_seconds)
        if phone_attempts > self.max_attempts or email_attempts > self.max_attempts:
            raise OTPMaxAttemptsError()

        phone_stored = await self.peek_otp(phone, purpose)
        email_stored = await self.peek_otp(email, purpose)
        if phone_stored == phone_otp and email_stored == email_otp:
            await self.redis.delete(f"{OTP_KEY_PREFIX}{phone}:{purpose}")
            await self.redis.delete(f"{OTP_KEY_PREFIX}{email}:{purpose}")
            await self.redis.delete(phone_attempts_key)
            await self.redis.delete(email_attempts_key)
            return True
        return False

    async def peek_otp(self, destination: str, purpose: str) -> str | None:
        """Return the stored OTP without consuming it (tests only)."""
        stored = await self.redis.get(f"{OTP_KEY_PREFIX}{destination}:{purpose}")
        return stored if stored is None else str(stored)

    async def _deliver(self, destination: str, purpose: str, otp: str, channel: str) -> bool:
        """Send the OTP through SMS or email."""
        if channel == OTP_CHANNEL_EMAIL:
            expiry_minutes = max(1, self.otp_expiry_seconds // 60)
            purpose_label = _OTP_PURPOSE_LABELS.get(purpose, purpose)
            subject, text, html = otp_email_content(
                app_name=self.settings.app_name,
                otp=otp,
                purpose_label=purpose_label,
                expiry_minutes=expiry_minutes,
            )
            return await self.email_service.send(
                to=destination,
                subject=subject,
                body=text,
                html_body=html,
            )
        return await self.sms_service.send_otp(destination, otp)

    def _generate_otp(self) -> str:
        """Generate a cryptographically secure numeric OTP."""
        return "".join(secrets.choice(string.digits) for _ in range(OTP_LENGTH))
