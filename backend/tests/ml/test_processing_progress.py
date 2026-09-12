"""Redis processing-progress tracker tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio

from app.ml.processing_progress import (
    STATUS_COMPLETE,
    STATUS_PROCESSING,
    ProcessingProgressTracker,
)

pytestmark = pytest.mark.ml


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator:
    """Real Redis client flushed for hash tests."""
    from app.core.redis_client import create_redis_client

    client = create_redis_client()
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001
        await client.aclose()
        pytest.skip(f"Redis unavailable: {exc}")
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.mark.asyncio
async def test_progress_tracker_round_trip(redis_client: object) -> None:
    """start/update/complete persist as a Redis hash the API can poll."""
    event_id = uuid4()
    tracker = ProcessingProgressTracker(redis_client, event_id, ttl_seconds=60)  # type: ignore[arg-type]
    await tracker.start(10)
    started = await tracker.read()
    assert started is not None
    assert started.total_photos == 10
    assert started.processed_photos == 0
    assert started.status == STATUS_PROCESSING

    await tracker.update(
        total_photos=10,
        processed_photos=4,
        failed_photos=1,
        total_faces=12,
        embedded_faces=8,
    )
    mid = await tracker.read()
    assert mid is not None
    assert mid.processed_photos == 4
    assert mid.failed_photos == 1
    assert mid.total_faces == 12
    assert mid.embedded_faces == 8

    await tracker.mark_complete(
        total_photos=10,
        processed_photos=10,
        failed_photos=1,
        total_faces=12,
        embedded_faces=8,
    )
    done = await tracker.read()
    assert done is not None
    assert done.status == STATUS_COMPLETE
    assert done.processed_photos == 10
