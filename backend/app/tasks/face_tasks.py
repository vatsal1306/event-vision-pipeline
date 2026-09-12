"""Celery tasks for event face processing (ML-009).

This module must stay import-light so CPU ``photo_processing`` workers can
boot without loading PyTorch. Heavy ML imports happen inside task bodies.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.logging import get_logger
from app.core.redis_client import create_redis_client
from app.ml.exceptions import ClusteringLockBusyError
from app.tasks.celery_app import celery_app

logger = get_logger()


def _build_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create an engine + session factory bound to the current event loop."""
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _process_event_photos_async(event_id: str) -> dict[str, Any]:
    """Load FaceService and run detect → embed → cluster for one event."""
    from app.ml.pipeline import FaceService
    from app.services.event_service import EventService

    session_factory = _build_session_factory()
    redis_client = create_redis_client()
    try:
        async with session_factory() as db:
            service = FaceService(db, redis_client=redis_client)
            result = await service.process_event_photos(UUID(event_id))
            event_service = EventService(db)
            await event_service.update_event_processing_status(UUID(event_id))
            return {
                "event_id": event_id,
                "photos_processed": result.photos_processed,
                "photos_failed": result.photos_failed,
            }
    finally:
        await redis_client.aclose()


async def _run_event_clustering_async(event_id: str) -> dict[str, str]:
    """Run clustering + recovery without re-extracting embeddings."""
    from app.ml.pipeline import FaceService
    from app.services.event_service import EventService

    session_factory = _build_session_factory()
    redis_client = create_redis_client()
    try:
        async with session_factory() as db:
            service = FaceService(db, redis_client=redis_client)
            await service.run_clustering(UUID(event_id))
            event_service = EventService(db)
            await event_service.update_event_processing_status(UUID(event_id))
            return {"event_id": event_id, "status": "clustered"}
    finally:
        await redis_client.aclose()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="face_processing",
    name="app.tasks.face_tasks.process_event_photos",
)  # type: ignore[untyped-decorator]
def process_event_photos(self: Any, event_id: str) -> dict[str, Any]:
    """Bulk-process unprocessed originals then cluster.

    Must run on the ``face_processing`` queue only (ML worker / local GPU later).
    """
    logger.info("Starting task process_event_photos", event_id=event_id)
    try:
        return asyncio.run(_process_event_photos_async(event_id))
    except ClusteringLockBusyError as exc:
        raise self.retry(exc=exc, countdown=min(60 * (self.request.retries + 1), 300))


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="face_processing",
    name="app.tasks.face_tasks.run_event_clustering",
)  # type: ignore[untyped-decorator]
def run_event_clustering(self: Any, event_id: str) -> dict[str, str]:
    """Standalone clustering for photos already embedded."""
    logger.info("Starting task run_event_clustering", event_id=event_id)
    try:
        return asyncio.run(_run_event_clustering_async(event_id))
    except ClusteringLockBusyError as exc:
        raise self.retry(exc=exc, countdown=min(60 * (self.request.retries + 1), 300))
