"""Celery tasks for event archival."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.exceptions import NotFoundError
from app.models.enums import EventStatus
from app.models.event import Event
from app.services.archival_service import ArchivalService
from app.tasks.celery_app import celery_app
from app.tasks.notification_tasks import notify_archival_warning_task


async def _check_events_for_archival_impl() -> None:
    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)
        stmt = select(Event).where(
            Event.archive_at <= now,
            Event.status == EventStatus.READY,
        )
        events = (await db.execute(stmt)).scalars().all()
        for event in events:
            archive_event_task.delay(str(event.id))


@celery_app.task  # type: ignore[untyped-decorator]
def check_events_for_archival() -> None:
    """Check for events past their archive_at date and archive them."""
    asyncio.run(_check_events_for_archival_impl())


@celery_app.task  # type: ignore[untyped-decorator]
def send_archival_warnings() -> None:
    """Send 7-day and 1-day warnings for events nearing archival."""

    async def _run() -> None:
        async with async_session_factory() as db:
            now = datetime.now(timezone.utc)
            stmt = select(Event).where(
                Event.archive_at > now,
                Event.status != EventStatus.ARCHIVED,
            )
            events = (await db.execute(stmt)).scalars().all()
            for event in events:
                if not event.archive_at:
                    continue
                # Calculate absolute days remaining
                delta = event.archive_at - now
                days_left = delta.total_seconds() / 86400.0

                # Check for 7 day or 1 day warnings using a 24-hour window
                # to tolerate timezone shifts or delayed Beat runs.
                if (6.5 <= days_left <= 7.5) or (0.5 <= days_left <= 1.5):
                    notify_archival_warning_task.delay(str(event.id))

    asyncio.run(_run())


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def archive_event_task(self: Any, event_id: str) -> None:
    """Archive an event: move originals to Glacier, delete proxies."""

    async def _run() -> None:
        async with async_session_factory() as db:
            service = ArchivalService(db)
            await service.archive_event(UUID(event_id))

    try:
        asyncio.run(_run())
    except NotFoundError:
        raise
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def restore_event_task(self: Any, event_id: str) -> None:
    """Restore an archived event."""

    async def _run() -> None:
        async with async_session_factory() as db:
            service = ArchivalService(db)
            await service.restore_event(UUID(event_id))

    try:
        asyncio.run(_run())
    except NotFoundError:
        raise
    except Exception as exc:
        raise self.retry(exc=exc)
