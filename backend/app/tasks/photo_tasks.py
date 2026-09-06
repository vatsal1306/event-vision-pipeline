"""Celery tasks for photo processing (stub for BE-009)."""

from __future__ import annotations

import logging
from typing import Any

from app.core.logging import get_logger
from app.tasks.celery_app import celery_app

logger = get_logger()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def process_uploaded_photo(self: Any, photo_id: str, s3_key: str, event_id: str) -> None:
    """Orchestrates the full processing chain for an uploaded photo.

    Stub implementation. Full implementation in BE-010.
    """
    logger.info("Processing uploaded photo %s from s3_key %s", photo_id, s3_key)
    # Stub: Would generate proxy, watermark, blurhash, detect faces here.
