"""Unit tests for sliding-window S3/MinIO prefetch."""

from __future__ import annotations

import asyncio

import pytest

from app.services.storage_prefetch import iter_prefetched


@pytest.mark.asyncio
async def test_prefetch_preserves_order_and_limits_concurrency() -> None:
    """At most ``ahead`` downloads run at once; yields stay in input order."""
    current = 0
    peak = 0

    async def fetch(item: int) -> bytes:
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.02)
        current -= 1
        return bytes([item])

    items = list(range(8))
    yielded: list[int] = []
    async for item, data, error in iter_prefetched(items, fetch, ahead=3):
        assert error is None
        assert data == bytes([item])
        yielded.append(item)

    assert yielded == items
    assert peak <= 3
    assert peak >= 2


@pytest.mark.asyncio
async def test_prefetch_yields_errors_without_stopping() -> None:
    """A failed download still yields later items."""

    async def fetch(item: int) -> bytes:
        if item == 1:
            raise RuntimeError("s3 timeout")
        return b"ok"

    results: list[tuple[int, bool]] = []
    async for item, data, error in iter_prefetched([0, 1, 2], fetch, ahead=2):
        results.append((item, error is None and data is not None))

    assert results == [(0, True), (1, False), (2, True)]
