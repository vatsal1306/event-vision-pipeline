"""Redis hash for photographer-facing bulk face-processing progress."""

from __future__ import annotations

from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID

import redis.asyncio as redis
import structlog

logger = structlog.get_logger(__name__)

PROCESSING_PROGRESS_KEY_TEMPLATE = "spotme:processing:{event_id}"

STATUS_PROCESSING = "processing"
STATUS_CLUSTERING = "clustering"
STATUS_COMPLETE = "complete"
STATUS_ERROR = "error"


@dataclass(frozen=True)
class ProcessingProgress:
    """Snapshot of bulk face processing for one event."""

    event_id: UUID
    total_photos: int
    processed_photos: int
    failed_photos: int
    total_faces: int
    embedded_faces: int
    status: str
    started_at: datetime | None
    eta_seconds: int | None


def progress_key(event_id: UUID) -> str:
    """Return the Redis hash key for an event's processing progress."""
    return PROCESSING_PROGRESS_KEY_TEMPLATE.format(event_id=event_id)


class ProcessingProgressTracker:
    """Read/write the ``spotme:processing:{event_id}`` Redis hash."""

    def __init__(
        self,
        redis_client: redis.Redis,
        event_id: UUID,
        *,
        ttl_seconds: int = 86400,
    ) -> None:
        """Bind a tracker to one event.

        Args:
            redis_client: Async Redis client (``decode_responses=True``).
            event_id: Event being processed.
            ttl_seconds: Key expiry so stale jobs do not linger.
        """
        self._redis = redis_client
        self._event_id = event_id
        self._ttl_seconds = ttl_seconds
        self._key = progress_key(event_id)
        self._started_at: datetime | None = None

    async def start(self, total_photos: int) -> None:
        """Initialise the hash when processing begins."""
        self._started_at = datetime.now(timezone.utc)
        await self._write(
            total_photos=total_photos,
            processed_photos=0,
            failed_photos=0,
            total_faces=0,
            embedded_faces=0,
            status=STATUS_PROCESSING,
            eta_seconds=None,
        )

    async def update(
        self,
        *,
        total_photos: int,
        processed_photos: int,
        failed_photos: int,
        total_faces: int,
        embedded_faces: int,
        status: str = STATUS_PROCESSING,
    ) -> None:
        """Overwrite counters and recompute ETA from elapsed time."""
        eta = self._eta_seconds(processed_photos, total_photos)
        await self._write(
            total_photos=total_photos,
            processed_photos=processed_photos,
            failed_photos=failed_photos,
            total_faces=total_faces,
            embedded_faces=embedded_faces,
            status=status,
            eta_seconds=eta,
        )

    async def mark_clustering(
        self,
        *,
        total_photos: int,
        processed_photos: int,
        failed_photos: int,
        total_faces: int,
        embedded_faces: int,
    ) -> None:
        """Set status to clustering after the last embedding flush."""
        await self.update(
            total_photos=total_photos,
            processed_photos=processed_photos,
            failed_photos=failed_photos,
            total_faces=total_faces,
            embedded_faces=embedded_faces,
            status=STATUS_CLUSTERING,
        )

    async def mark_complete(
        self,
        *,
        total_photos: int,
        processed_photos: int,
        failed_photos: int,
        total_faces: int,
        embedded_faces: int,
    ) -> None:
        """Set status to complete when clustering has finished."""
        await self.update(
            total_photos=total_photos,
            processed_photos=processed_photos,
            failed_photos=failed_photos,
            total_faces=total_faces,
            embedded_faces=embedded_faces,
            status=STATUS_COMPLETE,
        )

    async def mark_error(self, message: str) -> None:
        """Record a pipeline-level failure (does not abort per-photo skips)."""
        logger.warning(
            "face_processing_progress_error",
            event_id=str(self._event_id),
            error=message,
        )
        current = await self.read()
        await self._write(
            total_photos=current.total_photos if current else 0,
            processed_photos=current.processed_photos if current else 0,
            failed_photos=current.failed_photos if current else 0,
            total_faces=current.total_faces if current else 0,
            embedded_faces=current.embedded_faces if current else 0,
            status=STATUS_ERROR,
            eta_seconds=None,
        )

    async def read(self) -> ProcessingProgress | None:
        """Load the hash, or ``None`` if it has not been written yet."""
        raw = await cast(Awaitable[dict[str, str]], self._redis.hgetall(self._key))
        if not raw:
            return None
        started_raw = raw.get("started_at") or None
        started_at = None
        if started_raw:
            started_at = datetime.fromisoformat(started_raw)
        eta_raw = raw.get("eta_seconds") or ""
        eta_seconds = int(eta_raw) if eta_raw not in ("", "none", "None") else None
        return ProcessingProgress(
            event_id=self._event_id,
            total_photos=int(raw.get("total_photos") or 0),
            processed_photos=int(raw.get("processed_photos") or 0),
            failed_photos=int(raw.get("failed_photos") or 0),
            total_faces=int(raw.get("total_faces") or 0),
            embedded_faces=int(raw.get("embedded_faces") or 0),
            status=str(raw.get("status") or STATUS_PROCESSING),
            started_at=started_at,
            eta_seconds=eta_seconds,
        )

    def _eta_seconds(self, processed_photos: int, total_photos: int) -> int | None:
        """Estimate remaining seconds from average time per processed photo."""
        if self._started_at is None or processed_photos <= 0:
            return None
        remaining = total_photos - processed_photos
        if remaining <= 0:
            return 0
        elapsed = (datetime.now(timezone.utc) - self._started_at).total_seconds()
        if elapsed <= 0:
            return None
        rate = processed_photos / elapsed
        if rate <= 0:
            return None
        return int(remaining / rate)

    async def _write(
        self,
        *,
        total_photos: int,
        processed_photos: int,
        failed_photos: int,
        total_faces: int,
        embedded_faces: int,
        status: str,
        eta_seconds: int | None,
    ) -> None:
        started = self._started_at or datetime.now(timezone.utc)
        if self._started_at is None:
            self._started_at = started
        mapping = {
            "total_photos": str(total_photos),
            "processed_photos": str(processed_photos),
            "failed_photos": str(failed_photos),
            "total_faces": str(total_faces),
            "embedded_faces": str(embedded_faces),
            "status": status,
            "started_at": started.isoformat(),
            "eta_seconds": "" if eta_seconds is None else str(eta_seconds),
        }
        await cast(Awaitable[Any], self._redis.hset(self._key, mapping=mapping))
        await cast(Awaitable[bool], self._redis.expire(self._key, self._ttl_seconds))
