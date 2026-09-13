"""Notification service for event processing (email) and archival (log only)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.event import Event
from app.services.email_service import EmailService
from app.services.email_templates import (
    face_processing_stalled_ops_email_content,
    processing_complete_email_content,
)

logger = get_logger()


class NotificationService:
    """Service to handle photographer notifications."""

    def __init__(self, db: AsyncSession, email_service: EmailService) -> None:
        """Initialize the notification service.

        Args:
            db: Database session.
            email_service: Configured email service adapter.
        """
        self.db = db
        self.email = email_service

    async def send_processing_complete(self, event_id: UUID) -> None:
        """Email the photographer when an event is fully processed.

        Args:
            event_id: The ID of the completed event.

        Raises:
            NotFoundError: If the event doesn't exist.
        """
        event = await self.db.get(Event, event_id)
        if not event:
            raise NotFoundError("Event")

        await self.db.refresh(event, ["photographer"])

        if not event.photographer:
            logger.warning("notification.no_photographer_for_event", event_id=str(event_id))
            return

        settings = get_settings()
        event_url = f"{settings.frontend_url.rstrip('/')}/dashboard/events/{event.id}"
        subject, text, html = processing_complete_email_content(
            studio_name=event.photographer.studio_name,
            event_name=event.name,
            photo_count=event.total_photos,
            event_url=event_url,
            app_name=settings.app_name,
        )

        await self.email.send(
            to=event.photographer.email,
            subject=subject,
            body=text,
            html_body=html,
        )
        logger.info(
            "notification.processing_complete_sent",
            event_id=str(event_id),
            photographer_id=str(event.photographer_id),
        )

    async def send_archival_warning(self, event_id: UUID) -> None:
        """Log an archival warning. Email is intentionally not sent."""
        event = await self.db.get(Event, event_id)
        if not event:
            raise NotFoundError("Event")

        logger.info(
            "notification.archival_warning_email_disabled",
            event_id=str(event_id),
        )

    async def send_archival_complete(self, event_id: UUID) -> None:
        """Log archival completion. Email is intentionally not sent."""
        event = await self.db.get(Event, event_id)
        if not event:
            raise NotFoundError("Event")

        logger.info(
            "notification.archival_complete_email_disabled",
            event_id=str(event_id),
        )

    async def send_face_processing_stalled_ops(
        self,
        *,
        event_id: UUID,
        event_name: str,
        reason: str,
    ) -> None:
        """Email every address in ``OPS_ALERT_EMAIL`` after stall give-up.

        Args:
            event_id: Stalled event.
            event_name: Event title for the subject line.
            reason: Short stall reason recorded on the progress hash.
        """
        settings = get_settings()
        recipients = settings.ops_alert_emails
        if not recipients:
            logger.warning(
                "notification.face_processing_stalled_ops_skipped_no_recipients",
                event_id=str(event_id),
            )
            return

        event_url = f"{settings.frontend_url.rstrip('/')}/dashboard/events/{event_id}"
        subject, text, html = face_processing_stalled_ops_email_content(
            event_name=event_name,
            event_id=str(event_id),
            event_url=event_url,
            stall_minutes=settings.face_processing_stall_minutes,
            reason=reason,
            app_name=settings.app_name,
        )
        for to in recipients:
            await self.email.send(
                to=to,
                subject=subject,
                body=text,
                html_body=html,
            )
        logger.info(
            "notification.face_processing_stalled_ops_sent",
            event_id=str(event_id),
            recipients=recipients,
            reason=reason,
        )


def get_notification_service(db: AsyncSession) -> NotificationService:
    """Return a configured NotificationService."""
    from app.services.email_service import get_email_service

    return NotificationService(db=db, email_service=get_email_service())
