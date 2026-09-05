"""SMS delivery adapters for OTP and notifications."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger()


class SMSService:
    """SMS delivery interface. Phase 1 logs messages instead of calling MSG91."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the SMS adapter from runtime settings."""
        self.settings = settings or get_settings()

    async def send(self, phone: str, message: str) -> bool:
        """Send an SMS message to the given phone number.

        Local/dev uses structured logging only. Real providers are wired in BE-017.

        Args:
            phone: Destination phone number in E.164 format.
            message: SMS body text.

        Returns:
            True when the message was accepted for delivery (always True for log mode).
        """
        if self.settings.sms_provider == "log":
            logger.info("sms.send", phone=phone, provider="log", message=message)
            return True

        logger.warning(
            "sms.provider_not_configured",
            phone=phone,
            provider=self.settings.sms_provider,
        )
        return False
