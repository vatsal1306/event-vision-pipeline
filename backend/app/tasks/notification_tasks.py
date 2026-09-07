"""Celery tasks for sending notifications."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.database import async_session_factory
from app.core.exceptions import NotFoundError
from app.services.notification_service import get_notification_service
from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def notify_processing_complete_task(self: Any, event_id: str) -> None:
    """Send an email notification when event processing completes."""
    import asyncio

    async def _run() -> None:
        async with async_session_factory() as db:
            notification_service = get_notification_service(db)
            await notification_service.send_processing_complete(UUID(event_id))

    try:
        asyncio.run(_run())
    except NotFoundError:
        # Do not retry if the event is not found
        raise
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def notify_archival_warning_task(self: Any, event_id: str) -> None:
    """Send an email notification before an event is archived."""
    import asyncio

    async def _run() -> None:
        async with async_session_factory() as db:
            notification_service = get_notification_service(db)
            await notification_service.send_archival_warning(UUID(event_id))

    try:
        asyncio.run(_run())
    except NotFoundError:
        # Do not retry if the event is not found
        raise
    except Exception as exc:
        raise self.retry(exc=exc)
