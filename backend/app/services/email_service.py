"""Email delivery adapters for notifications."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger()


class EmailAdapter(ABC):
    """Abstract interface for sending emails."""

    @abstractmethod
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email."""
        pass


class LogEmailAdapter(EmailAdapter):
    """Local development adapter that logs emails instead of sending them."""

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Log the email."""
        logger.info(
            "email.send",
            to=to,
            subject=subject,
            body=body,
            provider="log",
        )
        return True


class EmailService:
    """Service to coordinate email delivery using configured adapters."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the email service with the correct adapter."""
        self.settings = settings or get_settings()
        if self.settings.email_provider == "log":
            self.adapter: EmailAdapter = LogEmailAdapter()
        else:
            # Fallback to log for Phase 1 as per BE-017
            logger.warning(
                "email.provider_not_configured",
                provider=self.settings.email_provider,
            )
            self.adapter = LogEmailAdapter()

    async def send(self, to: str, subject: str, body: str) -> bool:
        """Send an email using the underlying adapter."""
        return await self.adapter.send_email(to, subject, body)


def get_email_service() -> EmailService:
    """Return configured email service."""
    return EmailService()
