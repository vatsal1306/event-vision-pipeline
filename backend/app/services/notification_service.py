"""Notification service for event processing and archival."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.event import Event
from app.services.email_service import EmailService

logger = get_logger()


class NotificationService:
    """Service to handle high-level notifications (email/SMS)."""

    def __init__(self, db: AsyncSession, email_service: EmailService) -> None:
        """Initialize the notification service.

        Args:
            db: Database session.
            email_service: Configured email service adapter.
        """
        self.db = db
        self.email = email_service

    async def send_processing_complete(self, event_id: UUID) -> None:
        """Send a notification when an event is fully processed.

        Args:
            event_id: The ID of the completed event.

        Raises:
            NotFoundError: If the event doesn't exist.
        """
        event = await self.db.get(Event, event_id)
        if not event:
            raise NotFoundError("Event")

        # In a real app we'd load the related photographer efficiently
        # Since we just need their email, let's get it from the back-population if loaded,
        # or we can await it if we configure lazy="selectin" on the relationship.
        # Photographer is selectin loaded by default or we can just get the photographer directly.
        await self.db.refresh(event, ["photographer"])

        if not event.photographer:
            logger.warning("notification.no_photographer_for_event", event_id=str(event_id))
            return

        subject = f"Event Processing Complete: {event.name}"
        body = (
            f"Hello {event.photographer.studio_name},\n\n"
            f"Great news! Your event '{event.name}' has finished processing.\n"
            f"All {event.total_photos} photos have been processed and facial recognition is "
            "complete.\n\n"
            "You can now review and share the gallery with your clients.\n"
        )

        await self.email.send(
            to=event.photographer.email,
            subject=subject,
            body=body,
        )
        logger.info(
            "notification.processing_complete_sent",
            event_id=str(event_id),
            photographer_id=str(event.photographer_id),
        )

    async def send_archival_warning(self, event_id: UUID) -> None:
        """Send a warning notification before an event is archived.

        Args:
            event_id: The ID of the event nearing archival.
        """
        event = await self.db.get(Event, event_id)
        if not event:
            raise NotFoundError("Event")

        await self.db.refresh(event, ["photographer"])

        if not event.photographer:
            logger.warning("notification.no_photographer_for_event", event_id=str(event_id))
            return

        archive_date = event.archive_at.strftime("%Y-%m-%d") if event.archive_at else "soon"
        subject = f"Action Required: Event '{event.name}' Archiving Soon"

        body = (
            f"Hello {event.photographer.studio_name},\n\n"
            f"This is a reminder that your event '{event.name}' is scheduled to be archived "
            f"on {archive_date}.\n"
            "Once archived, high-resolution original photos will be moved to cold storage and "
            "may take longer to retrieve.\n\n"
            "If you need to keep this event active, please visit your dashboard.\n"
        )

        await self.email.send(
            to=event.photographer.email,
            subject=subject,
            body=body,
        )
        logger.info(
            "notification.archival_warning_sent",
            event_id=str(event_id),
            photographer_id=str(event.photographer_id),
        )

    async def send_archival_complete(self, event_id: UUID) -> None:
        """Send a notification when an event is successfully archived."""
        event = await self.db.get(Event, event_id)
        if not event:
            raise NotFoundError("Event")

        await self.db.refresh(event, ["photographer"])

        if not event.photographer:
            logger.warning("notification.no_photographer_for_event", event_id=str(event_id))
            return

        subject = f"Event Archived: {event.name}"
        body = (
            f"Hello {event.photographer.studio_name},\n\n"
            f"Your event '{event.name}' has been successfully archived.\n"
            "High-resolution original photos have been moved to cold storage. Web proxies "
            "and facial recognition data have been removed to save space.\n\n"
            "You can restore this event at any time from your dashboard, which will "
            "make the photos available for viewing and downloading again.\n"
        )

        await self.email.send(
            to=event.photographer.email,
            subject=subject,
            body=body,
        )
        logger.info(
            "notification.archival_complete_sent",
            event_id=str(event_id),
            photographer_id=str(event.photographer_id),
        )


def get_notification_service(db: AsyncSession) -> NotificationService:
    """Return a configured NotificationService."""
    from app.services.email_service import get_email_service

    return NotificationService(db=db, email_service=get_email_service())
