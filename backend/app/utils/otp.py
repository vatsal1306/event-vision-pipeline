"""OTP generation, Redis storage, and verification."""

from __future__ import annotations

import secrets
import string

import redis.asyncio as redis

from app.config import Settings, get_settings
from app.core.constants import OTP_LENGTH
from app.core.exceptions import OTPCooldownError, OTPMaxAttemptsError
from app.core.logging import get_logger
from app.services.sms_service import SMSService

logger = get_logger()

OTP_KEY_PREFIX = "otp:"
OTP_ATTEMPTS_PREFIX = "otp:attempts:"
OTP_COOLDOWN_PREFIX = "otp:cooldown:"


class OTPService:
    """OTP generation, storage, and verification using Redis."""

    def __init__(
        self,
        redis_client: redis.Redis,
        sms_service: SMSService,
        settings: Settings | None = None,
    ) -> None:
        """Initialize OTP helpers with Redis and SMS delivery.

        Args:
            redis_client: Async Redis client.
            sms_service: SMS delivery adapter.
            settings: Optional settings override (tests).
        """
        self.redis = redis_client
        self.sms_service = sms_service
        self.settings = settings or get_settings()

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
        """Minimum wait time between OTP sends for the same phone and purpose."""
        return self.settings.otp_cooldown_seconds

    async def send_otp(self, phone: str, purpose: str) -> None:
        """Generate an OTP, store it in Redis, and deliver it via SMS.

        Args:
            phone: E.164 phone number (for example ``+919876543210``).
            purpose: OTP purpose namespace (registration, login, password_reset).

        Raises:
            OTPCooldownError: When another OTP was sent too recently.
        """
        cooldown_key = f"{OTP_COOLDOWN_PREFIX}{phone}:{purpose}"
        if await self.redis.exists(cooldown_key):
            raise OTPCooldownError()

        otp = self._generate_otp()
        otp_key = f"{OTP_KEY_PREFIX}{phone}:{purpose}"
        attempts_key = f"{OTP_ATTEMPTS_PREFIX}{phone}:{purpose}"

        await self.redis.setex(otp_key, self.otp_expiry_seconds, otp)
        await self.redis.setex(cooldown_key, self.cooldown_seconds, "1")
        await self.redis.delete(attempts_key)

        await self.sms_service.send(phone, f"Your verification code is: {otp}")
        if self.settings.debug:
            logger.info("otp.dev_delivery", phone=phone, purpose=purpose, local_only=otp)

    async def verify_otp(self, phone: str, purpose: str, otp: str) -> bool:
        """Verify an OTP against the stored value with attempt limiting.

        Args:
            phone: E.164 phone number.
            purpose: OTP purpose namespace.
            otp: User-supplied OTP code.

        Returns:
            True when the OTP matches and is consumed.

        Raises:
            OTPMaxAttemptsError: When verification attempts are exhausted.
        """
        attempts_key = f"{OTP_ATTEMPTS_PREFIX}{phone}:{purpose}"
        attempts = await self.redis.incr(attempts_key)
        await self.redis.expire(attempts_key, self.otp_expiry_seconds)

        if attempts > self.max_attempts:
            raise OTPMaxAttemptsError()

        otp_key = f"{OTP_KEY_PREFIX}{phone}:{purpose}"
        stored_otp = await self.redis.get(otp_key)

        if stored_otp and stored_otp == otp:
            await self.redis.delete(otp_key)
            await self.redis.delete(attempts_key)
            return True
        return False

    async def peek_otp(self, phone: str, purpose: str) -> str | None:
        """Return the stored OTP without consuming it (tests only)."""
        return await self.redis.get(f"{OTP_KEY_PREFIX}{phone}:{purpose}")

    def _generate_otp(self) -> str:
        """Generate a cryptographically secure numeric OTP."""
        return "".join(secrets.choice(string.digits) for _ in range(OTP_LENGTH))
