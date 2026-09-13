"""Start and stop the on-demand GPU EC2 that consumes ``face_processing``.

Local/dev leaves ``GPU_INSTANCE_ID`` empty so this service is a no-op. Production
on the app EC2 uses compute-account keys (not the storage-account S3 user).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import boto3
import redis
from botocore.exceptions import ClientError

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.clustering.locks import CLUSTERING_LOCK_KEY_TEMPLATE, FACE_PIPELINE_LOCK_KEY_TEMPLATE

logger = get_logger()

GPU_IDLE_SINCE_KEY = "spotme:gpu_host:idle_since"
_FACE_QUEUE = "face_processing"
_PIPELINE_LOCK_SCAN = FACE_PIPELINE_LOCK_KEY_TEMPLATE.replace("{event_id}", "*")
_CLUSTERING_LOCK_SCAN = CLUSTERING_LOCK_KEY_TEMPLATE.replace("{event_id}", "*")
_RUNNING = "running"
_STOPPING = "stopping"
_PENDING = "pending"
_SHUTTING_DOWN = "shutting-down"


class GpuHostService:
    """EC2 start/stop plus idle detection for the ML host.

    Args:
        settings: App settings. Defaults to ``get_settings()``.
        ec2_client: Optional injected boto3 EC2 client (tests).
        app_redis: Sync Redis on ``REDIS_URL`` (pipeline locks).
        broker_redis: Sync Redis on ``CELERY_BROKER_URL`` (queue depth).
        wait_until_stopped: Override for the instance-stopped waiter.
        wait_until_running: Override for the instance-running waiter.
        now: Clock override for idle-timeout tests.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        ec2_client: Any | None = None,
        app_redis: Any | None = None,
        broker_redis: Any | None = None,
        wait_until_stopped: Callable[[], None] | None = None,
        wait_until_running: Callable[[], None] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Bind AWS and Redis clients used for GPU lifecycle."""
        self._settings = settings or get_settings()
        self._ec2 = ec2_client
        self._app_redis = app_redis
        self._broker_redis = broker_redis
        self._wait_until_stopped = wait_until_stopped
        self._wait_until_running = wait_until_running
        self._now = now or (lambda: datetime.now(timezone.utc))

    @property
    def is_configured(self) -> bool:
        """True when an instance id is set so AWS calls are allowed."""
        return bool(self._settings.gpu_instance_id.strip())

    def ensure_running(self) -> str:
        """Start the GPU instance if it is stopped. Never blocks the HTTP API.

        Returns:
            A short status string: ``skipped``, ``running``, ``started``, or
            ``error``.
        """
        if not self.is_configured:
            logger.info("gpu_host_skipped_not_configured")
            return "skipped"

        instance_id = self._settings.gpu_instance_id.strip()
        try:
            state = self.describe_state()
            if state == _RUNNING:
                logger.info("gpu_host_already_running", instance_id=instance_id)
                self._clear_idle_since()
                return "running"
            if state == _PENDING:
                logger.info("gpu_host_pending", instance_id=instance_id)
                self._clear_idle_since()
                return "running"
            if state == _SHUTTING_DOWN:
                logger.warning("gpu_host_shutting_down_skip_start", instance_id=instance_id)
                return "error"
            if state == _STOPPING:
                logger.info("gpu_host_wait_stopped_then_start", instance_id=instance_id)
                self._wait_stopped()
            self._start_instances()
            self._wait_running()
            self._clear_idle_since()
            logger.info("gpu_host_started", instance_id=instance_id)
            return "started"
        except GpuHostError as exc:
            logger.error(
                "gpu_host_start_failed",
                instance_id=instance_id,
                error=str(exc),
            )
            return "error"

    def stop_if_idle(self) -> str:
        """Stop the GPU instance after the face queue and locks stay idle.

        Returns:
            ``skipped``, ``busy``, ``waiting``, ``stopped``, or ``error``.
        """
        if not self.is_configured:
            return "skipped"

        instance_id = self._settings.gpu_instance_id.strip()
        try:
            state = self.describe_state()
            if state != _RUNNING:
                self._clear_idle_since()
                return "skipped"
            if self.face_work_in_progress():
                self._clear_idle_since()
                return "busy"

            idle_since = self._idle_since()
            now = self._now()
            if idle_since is None:
                self._mark_idle_since(now)
                logger.info("gpu_host_idle_timer_started", instance_id=instance_id)
                return "waiting"

            elapsed = (now - idle_since).total_seconds()
            threshold = self._settings.gpu_idle_stop_minutes * 60
            if elapsed < threshold:
                logger.info(
                    "gpu_host_idle_waiting",
                    instance_id=instance_id,
                    elapsed_seconds=int(elapsed),
                    threshold_seconds=int(threshold),
                )
                return "waiting"

            self._stop_instances()
            self._clear_idle_since()
            logger.info(
                "gpu_host_stopped_idle",
                instance_id=instance_id,
                idle_minutes=self._settings.gpu_idle_stop_minutes,
            )
            return "stopped"
        except GpuHostError as exc:
            logger.error(
                "gpu_host_stop_failed",
                instance_id=instance_id,
                error=str(exc),
            )
            return "error"

    def describe_state(self) -> str:
        """Return the EC2 instance state name (for example ``stopped``).

        Raises:
            GpuHostError: The instance id is missing from the describe response.
        """
        instance_id = self._settings.gpu_instance_id.strip()
        try:
            response = self._ec2_client().describe_instances(InstanceIds=[instance_id])
        except ClientError as exc:
            raise self._gpu_aws_error(instance_id, "DescribeInstances", exc) from exc
        reservations = response.get("Reservations") or []
        instances = reservations[0].get("Instances") if reservations else []
        if not instances:
            raise GpuHostError(f"GPU instance {instance_id} was not found.")
        return str(instances[0]["State"]["Name"])

    def face_work_in_progress(self) -> bool:
        """True when a pipeline lock is held or ``face_processing`` has jobs."""
        if self._scan_exists(self._locks_redis(), _PIPELINE_LOCK_SCAN):
            return True
        if self._scan_exists(self._locks_redis(), _CLUSTERING_LOCK_SCAN):
            return True
        pending_raw: Any = self._queue_redis().llen(_FACE_QUEUE)
        pending = int(pending_raw or 0)
        return pending > 0

    def _start_instances(self) -> None:
        """Call ``StartInstances`` for the configured GPU box."""
        instance_id = self._settings.gpu_instance_id.strip()
        try:
            self._ec2_client().start_instances(InstanceIds=[instance_id])
        except ClientError as exc:
            raise self._gpu_aws_error(instance_id, "StartInstances", exc) from exc

    def _stop_instances(self) -> None:
        """Call ``StopInstances`` (EBS disk is kept; do not terminate)."""
        instance_id = self._settings.gpu_instance_id.strip()
        try:
            self._ec2_client().stop_instances(InstanceIds=[instance_id])
        except ClientError as exc:
            raise self._gpu_aws_error(instance_id, "StopInstances", exc) from exc

    def _wait_stopped(self) -> None:
        """Block until the instance reaches ``stopped``."""
        if self._wait_until_stopped is not None:
            self._wait_until_stopped()
            return
        instance_id = self._settings.gpu_instance_id.strip()
        self._ec2_client().get_waiter("instance_stopped").wait(
            InstanceIds=[instance_id],
            WaiterConfig={"Delay": 15, "MaxAttempts": 40},
        )

    def _wait_running(self) -> None:
        """Block until the instance reaches ``running`` (not status-ok)."""
        if self._wait_until_running is not None:
            self._wait_until_running()
            return
        instance_id = self._settings.gpu_instance_id.strip()
        self._ec2_client().get_waiter("instance_running").wait(
            InstanceIds=[instance_id],
            WaiterConfig={"Delay": 15, "MaxAttempts": 40},
        )

    def _ec2_client(self) -> Any:
        """Build a boto3 EC2 client with compute-account credentials."""
        if self._ec2 is not None:
            return self._ec2
        access_key = self._settings.aws_compute_access_key_id.strip()
        secret_key = self._settings.aws_compute_secret_access_key.strip()
        if not access_key or not secret_key:
            raise GpuHostError(
                "GPU_INSTANCE_ID is set but AWS_COMPUTE_ACCESS_KEY_ID / "
                "AWS_COMPUTE_SECRET_ACCESS_KEY are missing."
            )
        self._ec2 = boto3.client(
            "ec2",
            region_name=self._settings.aws_compute_region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        return self._ec2

    def _gpu_aws_error(
        self,
        instance_id: str,
        operation: str,
        exc: ClientError,
    ) -> GpuHostError:
        """Turn an EC2 ClientError into a GpuHostError with account/region context.

        InvalidInstanceID.NotFound means the credentials can call EC2, but the
        id is not in that account+region (wrong keys, wrong region, or a
        terminated instance). VPC placement never causes this code.
        """
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        region = self._settings.aws_compute_region
        account = self._caller_account_id()
        return GpuHostError(
            f"{operation} failed for GPU instance {instance_id} in region "
            f"{region} (IAM account {account}): {error_code}: {exc}"
        )

    def _caller_account_id(self) -> str:
        """Return the AWS account id of AWS_COMPUTE_* keys, or unknown."""
        try:
            access_key = self._settings.aws_compute_access_key_id.strip()
            secret_key = self._settings.aws_compute_secret_access_key.strip()
            sts = boto3.client(
                "sts",
                region_name=self._settings.aws_compute_region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
            )
            return str(sts.get_caller_identity().get("Account") or "unknown")
        except ClientError:
            return "unknown"

    def _locks_redis(self) -> Any:
        """Sync Redis client for application locks (db 0 by default)."""
        if self._app_redis is None:
            self._app_redis = redis.Redis.from_url(
                self._settings.redis_url,
                decode_responses=True,
            )
        return self._app_redis

    def _queue_redis(self) -> Any:
        """Sync Redis client for the Celery broker (queue lists)."""
        if self._broker_redis is None:
            self._broker_redis = redis.Redis.from_url(
                self._settings.celery_broker_url,
                decode_responses=True,
            )
        return self._broker_redis

    def _idle_since(self) -> datetime | None:
        """Parse the idle-since timestamp, or None if the timer is not running."""
        raw = self._locks_redis().get(GPU_IDLE_SINCE_KEY)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            logger.warning("gpu_host_idle_since_invalid", value=str(raw))
            return None

    def _mark_idle_since(self, when: datetime) -> None:
        """Record when the GPU host first looked idle."""
        self._locks_redis().set(GPU_IDLE_SINCE_KEY, when.isoformat())

    def _clear_idle_since(self) -> None:
        """Drop the idle timer (work appeared, or the instance is not running)."""
        self._locks_redis().delete(GPU_IDLE_SINCE_KEY)

    @staticmethod
    def _scan_exists(client: Any, pattern: str) -> bool:
        """Return True if any key matches ``pattern``."""
        cursor: Any = 0
        while True:
            cursor, keys = client.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                return True
            if str(cursor) == "0":
                return False


class GpuHostError(Exception):
    """Raised when GPU instance lookup or credentials are invalid."""
