"""Unit tests for face-processing stall watch and reconciler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.config import Settings
from app.ml.clustering.locks import FACE_PIPELINE_LOCK_KEY_TEMPLATE
from app.ml.face_processing_watch import FaceProcessingWatch
from app.models.enums import EventStatus
from app.services.face_processing_reconciler import FaceProcessingReconciler
from app.tasks.celery_app import celery_app
from app.tasks.gpu_host_tasks import reconcile_face_processing


class FakeAsyncRedis:
    """Minimal async Redis for watch keys, locks, and SET NX."""

    def __init__(self) -> None:
        """Empty keyspace."""
        self.values: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        """SET with optional NX."""
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        """GET a string key."""
        return self.values.get(key)

    async def delete(self, key: str) -> int:
        """DEL one key from strings or hashes."""
        removed = 0
        if key in self.values:
            del self.values[key]
            removed += 1
        if key in self.hashes:
            del self.hashes[key]
            removed += 1
        return removed

    async def exists(self, key: str) -> int:
        """EXISTS for lock checks."""
        return int(key in self.values or key in self.hashes)

    async def hset(self, key: str, mapping: dict[str, str] | None = None) -> int:
        """HSET mapping."""
        self.hashes.setdefault(key, {}).update(mapping or {})
        return len(mapping or {})

    async def hgetall(self, key: str) -> dict[str, str]:
        """HGETALL."""
        return dict(self.hashes.get(key, {}))

    async def expire(self, key: str, ttl: int) -> bool:
        """No-op TTL."""
        return True


def _settings(**overrides: object) -> Settings:
    """Settings without reading local ``.env`` compute keys."""
    payload: dict[str, object] = {
        "face_processing_stall_minutes": 30,
        "face_processing_requeue_seconds": 120,
        "gpu_instance_id": "",
    }
    payload.update(overrides)
    return Settings(_env_file=None, **payload)  # type: ignore[arg-type]


def _event(*, status: EventStatus = EventStatus.PROCESSING) -> MagicMock:
    """Event-shaped mock used by the reconciler."""
    event = MagicMock()
    event.id = uuid4()
    event.name = "Sharma Wedding"
    event.status = status
    event.updated_at = datetime(2026, 9, 14, 11, 0, tzinfo=timezone.utc)
    return event


@pytest.mark.asyncio
async def test_watch_start_is_not_a_heartbeat() -> None:
    """Find faces click must not count as a live worker."""
    redis_client = FakeAsyncRedis()
    event_id = uuid4()
    t0 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    watch = FaceProcessingWatch(redis_client, event_id, now=lambda: t0)  # type: ignore[arg-type]
    await watch.mark_started()
    snapshot = await watch.read()
    assert snapshot is not None
    assert snapshot.last_heartbeat_at is None
    assert watch.has_fresh_heartbeat(snapshot, timedelta(minutes=30), now=t0) is False
    assert watch.is_stalled(snapshot, timedelta(minutes=30), now=t0) is False
    assert watch.is_stalled(snapshot, timedelta(minutes=30), now=t0 + timedelta(minutes=30)) is True


@pytest.mark.asyncio
async def test_reconciler_skips_gpu_when_heartbeat_is_fresh() -> None:
    """A long-running job with heartbeats must not StartInstances or revert."""
    redis_client = FakeAsyncRedis()
    event = _event()
    t0 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    watch = FaceProcessingWatch(redis_client, event.id, now=lambda: t0)  # type: ignore[arg-type]
    await watch.mark_started()
    later = t0 + timedelta(hours=3)
    watch_later = FaceProcessingWatch(redis_client, event.id, now=lambda: later)  # type: ignore[arg-type]
    await watch_later.record_heartbeat()

    gpu = MagicMock()
    gpu.is_reachable.return_value = False
    enqueue = MagicMock()
    reconciler = FaceProcessingReconciler(
        MagicMock(),
        redis_client,  # type: ignore[arg-type]
        settings=_settings(),
        gpu_host=gpu,
        now=lambda: later,
        enqueue_face_job=enqueue,
        send_ops_alert=AsyncMock(),
    )
    action = await reconciler.reconcile_event(event)
    assert action == "healthy"
    gpu.ensure_running.assert_not_called()
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_reconciler_starts_gpu_only_when_unreachable() -> None:
    """Boot retries happen only while the instance is down, not during real work."""
    redis_client = FakeAsyncRedis()
    event = _event()
    t0 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    watch = FaceProcessingWatch(redis_client, event.id, now=lambda: t0)  # type: ignore[arg-type]
    await watch.mark_started()

    gpu = MagicMock()
    gpu.is_reachable.return_value = False
    gpu.ensure_running.return_value = "started"
    enqueue = MagicMock()
    tick = t0 + timedelta(minutes=5)
    reconciler = FaceProcessingReconciler(
        MagicMock(),
        redis_client,  # type: ignore[arg-type]
        settings=_settings(),
        gpu_host=gpu,
        now=lambda: tick,
        enqueue_face_job=enqueue,
        send_ops_alert=AsyncMock(),
    )
    action = await reconciler.reconcile_event(event)
    assert action in {"gpu_started", "recovered"}
    gpu.ensure_running.assert_called_once()
    enqueue.assert_called_once_with(str(event.id))


@pytest.mark.asyncio
async def test_reconciler_does_not_start_gpu_when_instance_is_up() -> None:
    """GPU running / worker missing: requeue only."""
    redis_client = FakeAsyncRedis()
    event = _event()
    t0 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    watch = FaceProcessingWatch(redis_client, event.id, now=lambda: t0)  # type: ignore[arg-type]
    await watch.mark_started()

    gpu = MagicMock()
    gpu.is_reachable.return_value = True
    enqueue = MagicMock()
    tick = t0 + timedelta(minutes=5)
    reconciler = FaceProcessingReconciler(
        MagicMock(),
        redis_client,  # type: ignore[arg-type]
        settings=_settings(),
        gpu_host=gpu,
        now=lambda: tick,
        enqueue_face_job=enqueue,
        send_ops_alert=AsyncMock(),
    )
    action = await reconciler.reconcile_event(event)
    assert action == "requeued"
    gpu.ensure_running.assert_not_called()
    enqueue.assert_called_once_with(str(event.id))


@pytest.mark.asyncio
async def test_reconciler_does_not_requeue_while_lock_held() -> None:
    """Another worker owns the pipeline lock — do not pile duplicate jobs."""
    redis_client = FakeAsyncRedis()
    event = _event()
    t0 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    watch = FaceProcessingWatch(redis_client, event.id, now=lambda: t0)  # type: ignore[arg-type]
    await watch.mark_started()
    lock_key = FACE_PIPELINE_LOCK_KEY_TEMPLATE.format(event_id=event.id)
    redis_client.values[lock_key] = "token"

    gpu = MagicMock()
    gpu.is_reachable.return_value = True
    enqueue = MagicMock()
    reconciler = FaceProcessingReconciler(
        MagicMock(),
        redis_client,  # type: ignore[arg-type]
        settings=_settings(),
        gpu_host=gpu,
        now=lambda: t0 + timedelta(minutes=5),
        enqueue_face_job=enqueue,
        send_ops_alert=AsyncMock(),
    )
    action = await reconciler.reconcile_event(event)
    assert action == "waiting_lock"
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_reconciler_gives_up_after_thirty_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No heartbeat for 30 minutes → revert once and email ops."""
    redis_client = FakeAsyncRedis()
    event = _event()
    t0 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    watch = FaceProcessingWatch(redis_client, event.id, now=lambda: t0)  # type: ignore[arg-type]
    await watch.mark_started()

    revert = AsyncMock()
    monkeypatch.setattr(
        "app.services.face_processing_service.FaceProcessingService.revert_stalled_processing",
        revert,
    )
    ops = AsyncMock()
    gpu = MagicMock()
    gpu.is_reachable.return_value = False
    enqueue = MagicMock()
    reconciler = FaceProcessingReconciler(
        MagicMock(),
        redis_client,  # type: ignore[arg-type]
        settings=_settings(),
        gpu_host=gpu,
        now=lambda: t0 + timedelta(minutes=30),
        enqueue_face_job=enqueue,
        send_ops_alert=ops,
    )
    action = await reconciler.reconcile_event(event)
    assert action == "reverted"
    revert.assert_awaited_once()
    ops.assert_awaited_once()
    gpu.ensure_running.assert_not_called()
    enqueue.assert_not_called()

    second = await reconciler.reconcile_event(event)
    assert second == "skipped"
    assert revert.await_count == 1


@pytest.mark.asyncio
async def test_reconciler_resets_clock_after_heartbeat_then_death() -> None:
    """After a live run dies, give-up is 30 minutes from last heartbeat, not from click."""
    redis_client = FakeAsyncRedis()
    event = _event()
    t0 = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
    live = datetime(2026, 9, 14, 13, 0, tzinfo=timezone.utc)
    watch = FaceProcessingWatch(redis_client, event.id, now=lambda: t0)  # type: ignore[arg-type]
    await watch.mark_started()
    live_watch = FaceProcessingWatch(redis_client, event.id, now=lambda: live)  # type: ignore[arg-type]
    await live_watch.record_heartbeat()

    gpu = MagicMock()
    gpu.is_reachable.return_value = True
    enqueue = MagicMock()
    still_recovering = FaceProcessingReconciler(
        MagicMock(),
        redis_client,  # type: ignore[arg-type]
        settings=_settings(),
        gpu_host=gpu,
        now=lambda: live + timedelta(minutes=10),
        enqueue_face_job=enqueue,
        send_ops_alert=AsyncMock(),
    )
    action = await still_recovering.reconcile_event(event)
    assert action == "requeued"
    enqueue.assert_called_once()


@pytest.mark.asyncio
async def test_reconciler_treats_two_minute_old_heartbeat_as_healthy() -> None:
    """Pulse interval is 60s; a slightly delayed heartbeat is still a live job."""
    redis_client = FakeAsyncRedis()
    event = _event()
    t0 = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    watch = FaceProcessingWatch(redis_client, event.id, now=lambda: t0)  # type: ignore[arg-type]
    await watch.mark_started()
    await watch.record_heartbeat()
    gpu = MagicMock()
    gpu.is_reachable.return_value = False
    enqueue = MagicMock()
    reconciler = FaceProcessingReconciler(
        MagicMock(),
        redis_client,  # type: ignore[arg-type]
        settings=_settings(),
        gpu_host=gpu,
        now=lambda: t0 + timedelta(minutes=2),
        enqueue_face_job=enqueue,
        send_ops_alert=AsyncMock(),
    )
    assert await reconciler.reconcile_event(event) == "healthy"
    gpu.ensure_running.assert_not_called()
    enqueue.assert_not_called()


def test_ops_alert_emails_split_and_dedupe() -> None:
    """Comma-separated OPS_ALERT_EMAIL should mail each unique address."""
    settings = Settings(
        _env_file=None,  # type: ignore[arg-type]
        ops_alert_email="a@hpk.ai, b@hpk.ai, a@hpk.ai, ",
    )
    assert settings.ops_alert_emails == ["a@hpk.ai", "b@hpk.ai"]


def test_reconcile_task_is_on_cpu_beat() -> None:
    """Stall recovery must run on the app host, once a minute."""
    routes = celery_app.conf.task_routes
    assert routes["app.tasks.gpu_host_tasks.*"]["queue"] == "photo_processing"
    assert reconcile_face_processing._get_exec_options()["queue"] == "photo_processing"
    assert celery_app.conf.beat_schedule["reconcile-face-processing"]["task"] == (
        "app.tasks.gpu_host_tasks.reconcile_face_processing"
    )
    assert celery_app.conf.beat_schedule["reconcile-face-processing"]["schedule"].seconds == 60
