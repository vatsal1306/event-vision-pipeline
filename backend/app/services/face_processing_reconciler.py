"""Recover stalled photographer face-processing jobs (heartbeat + 30-minute give-up)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.clustering.locks import FACE_PIPELINE_LOCK_KEY_TEMPLATE, EventClusteringLock
from app.ml.config import get_ml_config
from app.ml.face_processing_watch import FaceProcessingWatch
from app.models.enums import EventStatus
from app.models.event import Event
from app.services.gpu_host_service import GpuHostService

logger = get_logger()

STALL_REASON_NO_HEARTBEAT = "no_worker_heartbeat"


class FaceProcessingReconciler:
    """Keep ``processing`` events moving, or revert them after a stall.

    A fresh pipeline heartbeat means photos are actually running — this service
    does not time out those jobs. GPU ``StartInstances`` runs only when the
    instance is not reachable.
    """

    def __init__(
        self,
        db: AsyncSession,
        redis_client: redis.Redis,
        *,
        settings: Settings | None = None,
        gpu_host: GpuHostService | None = None,
        now: Callable[[], datetime] | None = None,
        enqueue_face_job: Callable[[str], Any] | None = None,
        send_ops_alert: Callable[..., Any] | None = None,
    ) -> None:
        """Bind database, Redis, and optional test doubles.

        Args:
            db: Async SQLAlchemy session.
            redis_client: App Redis (locks, progress, watch keys).
            settings: App settings override.
            gpu_host: GPU lifecycle service (AWS). Injected in tests.
            now: Clock override for stall tests.
            enqueue_face_job: ``process_event_photos.delay`` stand-in.
            send_ops_alert: Optional async/sync callback after revert.
        """
        self.db = db
        self._redis = redis_client
        self._settings = settings or get_settings()
        self._gpu = gpu_host if gpu_host is not None else GpuHostService(self._settings)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._enqueue_face_job = enqueue_face_job
        self._send_ops_alert = send_ops_alert
        self._ml = get_ml_config()

    @property
    def stall_after(self) -> timedelta:
        """No-heartbeat window before revert (default 30 minutes)."""
        return timedelta(minutes=max(1, self._settings.face_processing_stall_minutes))

    @property
    def heartbeat_fresh_after(self) -> timedelta:
        """A worker is considered live if it heartbeated within this window."""
        return timedelta(seconds=max(60, self._settings.face_processing_heartbeat_fresh_seconds))

    async def reconcile_all(self) -> list[str]:
        """Run recovery for every event still in ``processing``.

        Returns:
            One action label per event considered.
        """
        result = await self.db.scalars(select(Event).where(Event.status == EventStatus.PROCESSING))
        actions: list[str] = []
        for event in result.all():
            actions.append(await self.reconcile_event(event))
        return actions

    async def reconcile_event(self, event: Event) -> str:
        """Recover or give up on one ``processing`` event.

        Args:
            event: Event row currently marked processing.

        Returns:
            ``healthy``, ``gpu_started``, ``requeued``, ``recovered``,
            ``reverted``, or ``skipped``.
        """
        if event.status != EventStatus.PROCESSING:
            return "skipped"

        watch = FaceProcessingWatch(
            self._redis,
            event.id,
            ttl_seconds=self._ml.processing_progress_ttl_seconds,
            now=self._now,
        )
        snapshot = await watch.read()
        if snapshot is None:
            if await self._pipeline_lock_held(event.id):
                logger.info(
                    "face_processing_reconcile_healthy_lock_without_watch",
                    event_id=str(event.id),
                )
                return "healthy"
            started = event.updated_at or self._now()
            await watch.mark_started(started)
            snapshot = await watch.read()
            if snapshot is None:
                return "skipped"

        if watch.has_fresh_heartbeat(snapshot, self.heartbeat_fresh_after, now=self._now()):
            logger.info("face_processing_reconcile_healthy", event_id=str(event.id))
            return "healthy"

        if watch.is_stalled(snapshot, self.stall_after, now=self._now()):
            return await self._give_up(event, watch)

        return await self._recover(event, watch)

    async def _recover(self, event: Event, watch: FaceProcessingWatch) -> str:
        """Start GPU if down and re-enqueue remaining-photo work if unlocked."""
        actions: list[str] = []
        if not self._gpu.is_reachable():
            gpu_result = self._gpu.ensure_running()
            logger.warning(
                "face_processing_reconcile_gpu_start",
                event_id=str(event.id),
                gpu_result=gpu_result,
            )
            actions.append("gpu_started")

        if await self._pipeline_lock_held(event.id):
            return actions[0] if actions else "waiting_lock"

        if await watch.try_mark_requeued(self._settings.face_processing_requeue_seconds):
            self._enqueue(str(event.id))
            actions.append("requeued")
            logger.warning(
                "face_processing_reconcile_requeued",
                event_id=str(event.id),
            )

        if not actions:
            return "waiting_requeue"
        return "recovered" if len(actions) > 1 else actions[0]

    async def _give_up(self, event: Event, watch: FaceProcessingWatch) -> str:
        """Revert to uploading, mark progress error, and email ops once."""
        if not await watch.try_begin_give_up():
            return "skipped"

        from app.services.face_processing_service import FaceProcessingService

        service = FaceProcessingService(self.db, self._redis)
        await service.revert_stalled_processing(event, reason=STALL_REASON_NO_HEARTBEAT)
        logger.error(
            "face_processing_reconcile_reverted",
            event_id=str(event.id),
            stall_minutes=self._settings.face_processing_stall_minutes,
        )
        if self._send_ops_alert is not None:
            result = self._send_ops_alert(
                event_id=event.id,
                event_name=event.name,
                reason=STALL_REASON_NO_HEARTBEAT,
            )
            if hasattr(result, "__await__"):
                await result
        else:
            from app.tasks.notification_tasks import notify_face_processing_stalled_ops_task

            notify_face_processing_stalled_ops_task.delay(
                str(event.id),
                event.name,
                STALL_REASON_NO_HEARTBEAT,
            )
        return "reverted"

    def _enqueue(self, event_id: str) -> None:
        """Put remaining-photo work on the face queue."""
        if self._enqueue_face_job is not None:
            self._enqueue_face_job(event_id)
            return
        from app.tasks.face_tasks import process_event_photos

        process_event_photos.delay(event_id)

    async def _pipeline_lock_held(self, event_id: UUID) -> bool:
        """Return True when a worker still owns the pipeline lock."""
        lock = EventClusteringLock(
            self._redis,
            event_id,
            ttl_seconds=self._ml.face_pipeline_lock_ttl_seconds,
            key_template=FACE_PIPELINE_LOCK_KEY_TEMPLATE,
        )
        exists = await self._redis.exists(lock.key)
        return bool(exists)
