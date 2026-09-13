"""Email delivery adapters for notifications and photographer OTPs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from email.message import EmailMessage
from email.utils import formataddr

import aiosmtplib

from app.config import Settings, get_settings
from app.core.constants import (
    EMAIL_PROVIDER_LOG,
    EMAIL_PROVIDER_NONE,
    EMAIL_PROVIDER_SMTP,
    SMTP_HTTP_TIMEOUT_SECONDS,
)
from app.core.logging import get_logger

logger = get_logger()


class EmailAdapter(ABC):
    """Abstract interface for sending emails."""

    @abstractmethod
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> bool:
        """Send an email. Return True when the provider accepted it."""


class LogEmailAdapter(EmailAdapter):
    """Local development adapter that logs emails instead of sending them."""

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> bool:
        """Log the email without delivering it."""
        logger.info(
            "email.send",
            to=to,
            subject=subject,
            body=body,
            has_html=html_body is not None,
            provider="log",
        )
        return True


class SmtpEmailAdapter(EmailAdapter):
    """Deliver mail through SMTP (Google Workspace / Gmail)."""

    def __init__(self, settings: Settings) -> None:
        """Bind SMTP settings for this adapter instance."""
        self._settings = settings
        self.last_user_message: str | None = None

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> bool:
        """Authenticate to SMTP and send a multipart message.

        Returns:
            True when SMTP accepts the message.

        Raises:
            Never raises to the caller — failures are logged and return False.
        """
        self.last_user_message = None
        if not self._settings.smtp_user or not self._settings.smtp_password:
            logger.warning("email.smtp_credentials_missing")
            self.last_user_message = (
                "Email SMTP is not configured. Set SMTP_USER and SMTP_PASSWORD "
                "(Google App Password) on the server."
            )
            return False

        message = EmailMessage()
        from_name = self._settings.email_from_name or self._settings.app_name
        message["From"] = formataddr((from_name, self._settings.email_from))
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        try:
            await aiosmtplib.send(
                message,
                hostname=self._settings.smtp_host,
                port=self._settings.smtp_port,
                username=self._settings.smtp_user,
                password=self._settings.smtp_password,
                start_tls=self._settings.smtp_use_tls,
                timeout=SMTP_HTTP_TIMEOUT_SECONDS,
            )
        except aiosmtplib.SMTPException as exc:
            smtp_code = getattr(exc, "code", None)
            logger.warning(
                "email.smtp_rejected",
                to=to,
                error_type=type(exc).__name__,
                smtp_code=smtp_code,
                smtp_message=str(exc),
                smtp_user=self._settings.smtp_user,
                smtp_host=self._settings.smtp_host,
                smtp_port=self._settings.smtp_port,
            )
            if isinstance(exc, aiosmtplib.SMTPAuthenticationError):
                self.last_user_message = (
                    "Gmail rejected the SMTP login. Use a Google App Password for "
                    f"{self._settings.smtp_user}, not the normal mailbox password."
                )
            else:
                self.last_user_message = "Could not send email. Please try again."
            return False
        except OSError as exc:
            logger.warning(
                "email.smtp_network_error",
                to=to,
                error_type=type(exc).__name__,
            )
            return False

        logger.info("email.smtp_accepted", to=to, subject=subject)
        return True


class EmailService:
    """Service to coordinate email delivery using configured adapters."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the email service with the correct adapter."""
        self.settings = settings or get_settings()
        provider = self.settings.email_provider.lower()
        if provider == EMAIL_PROVIDER_SMTP:
            self.adapter: EmailAdapter = SmtpEmailAdapter(self.settings)
        elif provider in {EMAIL_PROVIDER_LOG, EMAIL_PROVIDER_NONE}:
            self.adapter = LogEmailAdapter()
        else:
            logger.warning("email.provider_not_configured", provider=self.settings.email_provider)
            self.adapter = LogEmailAdapter()

    @property
    def last_user_message(self) -> str | None:
        """Client-safe reason from the last SMTP failure, if any."""
        adapter = self.adapter
        if isinstance(adapter, SmtpEmailAdapter):
            return adapter.last_user_message
        return None

    async def send(
        self,
        to: str,
        subject: str,
        body: str,
        html_body: str | None = None,
    ) -> bool:
        """Send an email using the underlying adapter."""
        return await self.adapter.send_email(to, subject, body, html_body=html_body)


def get_email_service() -> EmailService:
    """Return configured email service."""
    return EmailService()
