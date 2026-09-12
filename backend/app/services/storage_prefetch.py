"""Sliding-window object downloads so bulk ML never queues every S3 GET at once."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine, Sequence
from typing import Any, TypeVar

T = TypeVar("T")
DownloadFn = Callable[[T], Coroutine[Any, Any, bytes]]


async def iter_prefetched(
    items: Sequence[T],
    download: DownloadFn[T],
    *,
    ahead: int = 4,
) -> AsyncIterator[tuple[T, bytes | None, BaseException | None]]:
    """Yield items in order while keeping up to ``ahead`` downloads in flight.

    A 20,000-photo event must not start 20,000 concurrent S3 GETs. This window
    overlaps download with GPU work without holding decoded images.

    Args:
        items: Photos or other download keys, in processing order.
        download: Async callable that returns object bytes.
        ahead: Maximum in-flight downloads (minimum 1 = sequential).

    Yields:
        ``(item, data, error)``. ``data`` is None when ``error`` is set.
    """
    window = max(1, ahead)
    iterator = iter(items)
    pending: list[tuple[T, asyncio.Task[bytes]]] = []

    def _start_next() -> None:
        try:
            item = next(iterator)
        except StopIteration:
            return
        pending.append((item, asyncio.create_task(download(item))))

    for _ in range(window):
        _start_next()
        if not pending:
            break

    while pending:
        item, task = pending.pop(0)
        data: bytes | None
        error: BaseException | None
        try:
            data = await task
            error = None
        except BaseException as exc:
            data = None
            error = exc
        _start_next()
        yield item, data, error
