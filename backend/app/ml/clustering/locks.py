"""Redis distributed lock for one clustering pass per event."""

from __future__ import annotations

import uuid
from typing import Any

import redis.asyncio as redis
import structlog

logger = structlog.get_logger(__name__)

CLUSTERING_LOCK_KEY_TEMPLATE = "clustering_lock:{event_id}"

_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

_EXTEND_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
else
    return 0
end
"""


class EventClusteringLock:
    """Compare-and-set Redis lock scoped to a single event clustering pass.

    Token-based SET NX is used instead of ``redis.lock()`` so the lock works
    with the project's ``decode_responses=True`` client.
    """

    def __init__(self, redis_client: redis.Redis, event_id: uuid.UUID, ttl_seconds: int) -> None:
        """Bind a lock key for ``event_id``.

        Args:
            redis_client: Async Redis client (string-decoded responses).
            event_id: Event whose clustering must be exclusive.
            ttl_seconds: Key expiry used on acquire and extend.
        """
        self._redis = redis_client
        self._event_id = event_id
        self._ttl_seconds = ttl_seconds
        self._key = CLUSTERING_LOCK_KEY_TEMPLATE.format(event_id=event_id)
        self._token = str(uuid.uuid4())

    @property
    def key(self) -> str:
        """Redis key holding the lock token."""
        return self._key

    async def acquire(self) -> bool:
        """Try to acquire the lock without blocking.

        Returns:
            True if this instance now owns the lock.
        """
        acquired = await self._redis.set(self._key, self._token, nx=True, ex=self._ttl_seconds)
        return bool(acquired)

    async def extend(self) -> bool:
        """Refresh TTL if this instance still owns the lock.

        Returns:
            True when expiry was reset to ``ttl_seconds``.
        """
        result = await self._eval_script(
            _EXTEND_SCRIPT, self._key, self._token, str(self._ttl_seconds)
        )
        extended = bool(result)
        if not extended:
            logger.warning(
                "clustering_lock_extend_failed",
                event_id=str(self._event_id),
                lock_key=self._key,
            )
        return extended

    async def release(self) -> None:
        """Delete the lock key only if this instance still owns it."""
        await self._eval_script(_RELEASE_SCRIPT, self._key, self._token)

    async def _eval_script(self, script: str, *args: str) -> object:
        """Run a Lua script. redis-py's eval overloads are not await-safe for mypy."""
        eval_command: Any = self._redis.eval
        return await eval_command(script, 1, *args)
