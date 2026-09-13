"""Unit tests for on-demand GPU EC2 start/stop (INF-009)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from typing import Any
from unittest.mock import patch

from botocore.exceptions import ClientError

from app.config import Settings
from app.services.gpu_host_service import GPU_IDLE_SINCE_KEY, GpuHostService
from app.tasks.celery_app import celery_app
from app.tasks.gpu_host_tasks import ensure_gpu_host_running, stop_idle_gpu_host


class FakeEc2:
    """In-memory EC2 API for lifecycle tests."""

    def __init__(self, state: str = "stopped") -> None:
        """Start in ``state`` (``stopped``, ``running``, ``stopping``, ...)."""
        self.state = state
        self.start_calls = 0
        self.stop_calls = 0

    def describe_instances(self, InstanceIds: list[str]) -> dict[str, Any]:
        """Return a single instance with the current state."""
        return {
            "Reservations": [
                {"Instances": [{"InstanceId": InstanceIds[0], "State": {"Name": self.state}}]}
            ]
        }

    def start_instances(self, InstanceIds: list[str]) -> dict[str, Any]:
        """Mark the instance running."""
        self.start_calls += 1
        self.state = "running"
        return {}

    def stop_instances(self, InstanceIds: list[str]) -> dict[str, Any]:
        """Mark the instance stopped."""
        self.stop_calls += 1
        self.state = "stopped"
        return {}


class FakeRedis:
    """Minimal Redis used for locks, queue length, and the idle timer."""

    def __init__(self) -> None:
        """Empty keyspace."""
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    def get(self, key: str) -> str | None:
        """Return a string value or None."""
        return self.values.get(key)

    def set(self, key: str, value: str) -> None:
        """Set a string key."""
        self.values[key] = value

    def delete(self, key: str) -> None:
        """Remove a key if present."""
        self.values.pop(key, None)

    def llen(self, key: str) -> int:
        """Length of a list key."""
        return len(self.lists.get(key, []))

    def lpush(self, key: str, value: str) -> None:
        """Push onto a list (tests only)."""
        self.lists.setdefault(key, []).append(value)

    def scan(
        self, cursor: int | str = 0, match: str = "*", count: int = 100
    ) -> tuple[int, list[str]]:
        """Return matching keys in one page."""
        matched = [key for key in self.values if fnmatch(key, match)]
        return 0, matched


def _settings(**overrides: object) -> Settings:
    """Build settings without reading local ``.env`` AWS keys."""
    payload: dict[str, object] = {
        "gpu_instance_id": "i-gpu1",
        "aws_compute_access_key_id": "AKIATEST",
        "aws_compute_secret_access_key": "secret",
        "gpu_idle_stop_minutes": 10,
    }
    payload.update(overrides)
    return Settings(_env_file=None, **payload)  # type: ignore[arg-type]


def _service(
    ec2: FakeEc2,
    app_redis: FakeRedis,
    broker_redis: FakeRedis | None = None,
    **setting_overrides: object,
) -> GpuHostService:
    """GpuHostService with fakes and no-op waiters."""
    clock = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    return GpuHostService(
        _settings(**setting_overrides),
        ec2_client=ec2,
        app_redis=app_redis,  # type: ignore[arg-type]
        broker_redis=(broker_redis or FakeRedis()),  # type: ignore[arg-type]
        wait_until_stopped=lambda: None,
        wait_until_running=lambda: None,
        now=lambda: clock,
    )


def test_ensure_running_skipped_without_instance_id() -> None:
    """Laptop/dev: empty GPU_INSTANCE_ID must not call AWS."""
    ec2 = FakeEc2()
    service = _service(ec2, FakeRedis(), gpu_instance_id="")
    assert service.ensure_running() == "skipped"
    assert ec2.start_calls == 0


def test_ensure_running_starts_stopped_instance() -> None:
    """Photographer trigger boots a stopped GPU box."""
    ec2 = FakeEc2("stopped")
    app_redis = FakeRedis()
    service = _service(ec2, app_redis)
    assert service.ensure_running() == "started"
    assert ec2.start_calls == 1
    assert GPU_IDLE_SINCE_KEY not in app_redis.values


def test_ensure_running_noop_when_already_running() -> None:
    """Second event while GPU is up must not start again."""
    ec2 = FakeEc2("running")
    service = _service(ec2, FakeRedis())
    assert service.ensure_running() == "running"
    assert ec2.start_calls == 0


def test_is_reachable_true_when_running_or_unconfigured() -> None:
    """Laptop (no instance id) and a running box must not trigger start retries."""
    running = _service(FakeEc2("running"), FakeRedis())
    assert running.is_reachable() is True
    laptop = _service(FakeEc2("stopped"), FakeRedis(), gpu_instance_id="")
    assert laptop.is_reachable() is True


def test_is_reachable_false_when_stopped() -> None:
    """Stopped GPU is the only case that should retry StartInstances."""
    service = _service(FakeEc2("stopped"), FakeRedis())
    assert service.is_reachable() is False


def test_ensure_running_waits_if_stopping() -> None:
    """If AWS is still stopping, wait then start."""
    ec2 = FakeEc2("stopping")
    waited: list[str] = []
    service = GpuHostService(
        _settings(),
        ec2_client=ec2,
        app_redis=FakeRedis(),  # type: ignore[arg-type]
        broker_redis=FakeRedis(),  # type: ignore[arg-type]
        wait_until_stopped=lambda: waited.append("stopped"),
        wait_until_running=lambda: waited.append("running"),
    )
    assert service.ensure_running() == "started"
    assert waited == ["stopped", "running"]
    assert ec2.start_calls == 1


def test_stop_if_idle_waits_full_timeout() -> None:
    """First idle tick only starts the timer; second tick after 10 min stops."""
    ec2 = FakeEc2("running")
    app_redis = FakeRedis()
    broker = FakeRedis()
    t0 = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
    first = GpuHostService(
        _settings(),
        ec2_client=ec2,
        app_redis=app_redis,  # type: ignore[arg-type]
        broker_redis=broker,  # type: ignore[arg-type]
        now=lambda: t0,
    )
    assert first.stop_if_idle() == "waiting"
    assert ec2.stop_calls == 0
    assert GPU_IDLE_SINCE_KEY in app_redis.values

    later = GpuHostService(
        _settings(),
        ec2_client=ec2,
        app_redis=app_redis,  # type: ignore[arg-type]
        broker_redis=broker,  # type: ignore[arg-type]
        now=lambda: t0 + timedelta(minutes=10),
    )
    assert later.stop_if_idle() == "stopped"
    assert ec2.stop_calls == 1


def test_stop_if_idle_busy_when_queue_has_jobs() -> None:
    """Pending face_processing jobs must reset the idle timer."""
    ec2 = FakeEc2("running")
    app_redis = FakeRedis()
    app_redis.set(GPU_IDLE_SINCE_KEY, datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat())
    broker = FakeRedis()
    broker.lpush("face_processing", "job")
    service = _service(ec2, app_redis, broker)
    assert service.stop_if_idle() == "busy"
    assert ec2.stop_calls == 0
    assert GPU_IDLE_SINCE_KEY not in app_redis.values


def test_stop_if_idle_busy_when_pipeline_lock_held() -> None:
    """A live face pipeline lock means the GPU is still working."""
    ec2 = FakeEc2("running")
    app_redis = FakeRedis()
    app_redis.set("face_pipeline_lock:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "locked")
    service = _service(ec2, app_redis)
    assert service.face_work_in_progress() is True
    assert service.stop_if_idle() == "busy"
    assert ec2.stop_calls == 0


def test_ensure_running_maps_missing_instance_to_error() -> None:
    """Wrong account/region must not raise raw boto ClientError (no Celery retry)."""

    class MissingInstanceEc2(FakeEc2):
        def describe_instances(self, InstanceIds: list[str]) -> dict[str, Any]:
            raise ClientError(
                {
                    "Error": {
                        "Code": "InvalidInstanceID.NotFound",
                        "Message": f"The instance ID '{InstanceIds[0]}' does not exist",
                    }
                },
                "DescribeInstances",
            )

    service = _service(MissingInstanceEc2(), FakeRedis())
    with patch.object(service, "_caller_account_id", return_value="111111111111"):
        assert service.ensure_running() == "error"


def test_gpu_host_tasks_route_to_photo_processing_queue() -> None:
    """Lifecycle tasks must run on the app CPU worker, not the GPU queue."""
    routes = celery_app.conf.task_routes
    assert routes["app.tasks.gpu_host_tasks.*"]["queue"] == "photo_processing"
    assert ensure_gpu_host_running._get_exec_options()["queue"] == "photo_processing"
    assert stop_idle_gpu_host._get_exec_options()["queue"] == "photo_processing"
    assert celery_app.conf.beat_schedule["stop-idle-gpu-host"]["task"] == (
        "app.tasks.gpu_host_tasks.stop_idle_gpu_host"
    )
