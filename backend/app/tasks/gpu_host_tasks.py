"""CPU-queue tasks that start and stop the GPU EC2 (INF-009).

These must run on the app host (``photo_processing``), never on the GPU worker.
"""

from __future__ import annotations

from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from app.core.logging import get_logger
from app.services.gpu_host_service import GpuHostError, GpuHostService
from app.tasks.celery_app import celery_app

logger = get_logger()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="photo_processing",
    name="app.tasks.gpu_host_tasks.ensure_gpu_host_running",
)  # type: ignore[untyped-decorator]
def ensure_gpu_host_running(self: Any) -> str:
    """Start the GPU instance after the photographer enqueues face work."""
    logger.info("ensure_gpu_host_running_started")
    try:
        return GpuHostService().ensure_running()
    except (ClientError, BotoCoreError) as exc:
        logger.error("ensure_gpu_host_running_failed", error=str(exc))
        raise self.retry(exc=exc)
    except GpuHostError as exc:
        logger.error("ensure_gpu_host_running_misconfigured", error=str(exc))
        return "error"


@celery_app.task(
    queue="photo_processing",
    name="app.tasks.gpu_host_tasks.stop_idle_gpu_host",
)  # type: ignore[untyped-decorator]
def stop_idle_gpu_host() -> str:
    """Beat task: stop the GPU box after locks + queue stay idle."""
    return GpuHostService().stop_if_idle()
