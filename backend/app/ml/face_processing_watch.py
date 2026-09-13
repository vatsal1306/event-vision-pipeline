"""Redis watch for face-processing heartbeats and stall detection."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from uuid import UUID

import redis.asyncio as redis

FACE_WATCH_KEY_TEMPLATE = "spotme:face_watch:{event_id}"
FACE_REQUEUE_KEY_TEMPLATE = "spotme:face_requeue:{event_id}"
FACE_GIVE_UP_KEY_TEMPLATE = "spotme:face_giveup:{event_id}"

_DEFAULT_TTL_SECONDS = 86400


@dataclass(frozen=True)
class FaceProcessingWatchSnapshot:
    """Started-at and last worker heartbeat for one event."""

    event_id: UUID
    started_at: datetime
    last_heartbeat_at: datetime | None


class FaceProcessingWatch:
    """Track whether a ``processing`` event still has a live GPU worker.

    ``started_at`` is set when the photographer clicks Find faces. A heartbeat is
    written only while the pipeline lock is held and being extended. Clicking
    start is not a heartbeat.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        event_id: UUID,
        *,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Bind one event's watch hash.

        Args:
            redis_client: Async Redis client with decoded string responses.
            event_id: Event being processed.
            ttl_seconds: Key expiry so abandoned watches do not linger.
            now: Clock override for tests.
        """
        self._redis = redis_client
        self._event_id = event_id
        self._ttl_seconds = ttl_seconds
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._key = FACE_WATCH_KEY_TEMPLATE.format(event_id=event_id)

    @property
    def key(self) -> str:
        """Redis hash key for this event's watch."""
        return self._key

    @property
    def requeue_key(self) -> str:
        """Short-lived key that debounces Celery re-enqueue."""
        return FACE_REQUEUE_KEY_TEMPLATE.format(event_id=self._event_id)

    @property
    def give_up_key(self) -> str:
        """Key that prevents double revert/email for one stall window."""
        return FACE_GIVE_UP_KEY_TEMPLATE.format(event_id=self._event_id)

    async def mark_started(self, started_at: datetime | None = None) -> None:
        """Record a new Find-faces attempt. Clears any previous heartbeat."""
        started = _as_utc(started_at or self._now())
        await self._write(started_at=started, last_heartbeat_at=None)
        await cast(Awaitable[Any], self._redis.delete(self.give_up_key))

    async def record_heartbeat(self) -> None:
        """Mark the GPU worker as alive. Creates started_at if missing."""
        current = await self.read()
        started = current.started_at if current is not None else self._now()
        await self._write(started_at=started, last_heartbeat_at=self._now())

    async def read(self) -> FaceProcessingWatchSnapshot | None:
        """Load the watch hash, or ``None`` if it was never written."""
        raw = await cast(Awaitable[dict[str, str]], self._redis.hgetall(self._key))
        if not raw:
            return None
        started_raw = raw.get("started_at") or ""
        if not started_raw:
            return None
        heartbeat_raw = raw.get("last_heartbeat_at") or ""
        last_heartbeat_at = datetime.fromisoformat(heartbeat_raw) if heartbeat_raw else None
        return FaceProcessingWatchSnapshot(
            event_id=self._event_id,
            started_at=datetime.fromisoformat(started_raw),
            last_heartbeat_at=last_heartbeat_at,
        )

    def seconds_since_activity(
        self,
        snapshot: FaceProcessingWatchSnapshot,
        *,
        now: datetime | None = None,
    ) -> float:
        """Seconds since last heartbeat, or since start if none yet."""
        clock = now or self._now()
        last = snapshot.last_heartbeat_at or snapshot.started_at
        return (clock - _as_utc(last)).total_seconds()

    def has_fresh_heartbeat(
        self,
        snapshot: FaceProcessingWatchSnapshot,
        stall_after: timedelta,
        *,
        now: datetime | None = None,
    ) -> bool:
        """True when a worker heartbeat landed inside the stall window."""
        if snapshot.last_heartbeat_at is None:
            return False
        clock = now or self._now()
        return clock - _as_utc(snapshot.last_heartbeat_at) < stall_after

    def is_stalled(
        self,
        snapshot: FaceProcessingWatchSnapshot,
        stall_after: timedelta,
        *,
        now: datetime | None = None,
    ) -> bool:
        """True when there has been no heartbeat (or start) for ``stall_after``."""
        return self.seconds_since_activity(snapshot, now=now) >= stall_after.total_seconds()

    async def try_begin_give_up(self) -> bool:
        """Claim exclusive right to revert + email. False if already claimed."""
        created = await self._redis.set(self.give_up_key, "1", nx=True, ex=self._ttl_seconds)
        return bool(created)

    async def try_mark_requeued(self, debounce_seconds: int) -> bool:
        """True when this tick should enqueue ``process_event_photos`` again."""
        created = await self._redis.set(self.requeue_key, "1", nx=True, ex=debounce_seconds)
        return bool(created)

    async def _write(
        self,
        *,
        started_at: datetime,
        last_heartbeat_at: datetime | None,
    ) -> None:
        mapping = {
            "started_at": _as_utc(started_at).isoformat(),
            "last_heartbeat_at": (
                _as_utc(last_heartbeat_at).isoformat() if last_heartbeat_at else ""
            ),
        }
        await cast(Awaitable[Any], self._redis.hset(self._key, mapping=mapping))
        await cast(Awaitable[bool], self._redis.expire(self._key, self._ttl_seconds))


def _as_utc(value: datetime) -> datetime:
    """Normalize naive datetimes to UTC for subtraction."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
