"""Storage service for S3 and local environments."""

from __future__ import annotations

import abc
import asyncio
import threading
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import aioboto3
import boto3
from botocore.client import BaseClient
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.config import Settings, get_settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger
from app.services.s3_presigner import register_cacheable_signer

logger = get_logger()

_S3_SERVICE_NAME = "s3"


def _s3_client_kwargs(settings: Settings) -> dict[str, Any]:
    """Return client arguments that pin S3 to a regional, virtual-hosted endpoint.

    Left to its own devices botocore signs for the configured region but
    addresses the legacy global ``s3.amazonaws.com`` host, which costs an extra
    routing hop on every gallery image. Naming the regional endpoint removes it.

    Args:
        settings: Application settings holding the region and optional override.

    Returns:
        Keyword arguments common to the async and signing clients.
    """
    endpoint_url = settings.s3_endpoint_url or f"https://s3.{settings.aws_region}.amazonaws.com"
    return {
        "endpoint_url": endpoint_url,
        "config": BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    }


class StorageService(abc.ABC):
    """Abstract base class for object storage operations."""

    @abc.abstractmethod
    async def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        storage_class: str = "STANDARD",
    ) -> None:
        """Upload an object."""
        ...

    @abc.abstractmethod
    async def get_object(self, bucket: str, key: str) -> bytes:
        """Download an object."""
        ...

    @abc.abstractmethod
    async def delete_object(self, bucket: str, key: str) -> None:
        """Delete an object."""
        ...

    @abc.abstractmethod
    async def delete_objects(self, bucket: str, keys: list[str]) -> None:
        """Delete multiple objects."""
        ...

    @abc.abstractmethod
    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        client_method: str = "get_object",
        expires_in: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        """Generate a presigned URL for GET or PUT."""
        ...

    @abc.abstractmethod
    def build_presigned_url(
        self,
        bucket: str,
        key: str,
        client_method: str = "get_object",
        expires_in: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        """Generate a presigned URL without performing any I/O.

        Signing is a local HMAC computation, so this is safe to call from
        synchronous code and from inside an event loop.
        """
        ...

    @abc.abstractmethod
    async def change_storage_class(self, bucket: str, key: str, storage_class: str) -> None:
        """Change the storage class of an existing object."""
        ...


class S3StorageService(StorageService):
    """S3 implementation using aioboto3.

    Both the async client used for object I/O and the synchronous client used
    for URL signing are created once and reused. Constructing a botocore client
    parses the multi-megabyte S3 service model and builds a TLS context, which
    is hundreds of milliseconds of *blocking* CPU. Doing that per request
    starves the event loop and, in turn, exhausts the database pool.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            region_name=settings.aws_region,
        )
        self.default_expiry = settings.s3_presigned_url_expiry
        self._client_kwargs = _s3_client_kwargs(settings)
        self._async_clients: dict[int, tuple[Any, AsyncExitStack]] = {}
        self._async_client_locks: dict[int, asyncio.Lock] = {}
        self._signing_client: BaseClient | None = None
        self._signing_lock = threading.Lock()

    async def _client(self) -> Any:
        """Return this event loop's shared S3 client, creating it on first use.

        Celery runs one ``asyncio.run()`` per task, so clients are keyed by loop
        to avoid reusing a connector bound to a closed loop.

        Returns:
            An aiobotocore S3 client owned by the current event loop.
        """
        loop_key = id(asyncio.get_running_loop())
        cached = self._async_clients.get(loop_key)
        if cached is not None:
            return cached[0]

        lock = self._async_client_locks.setdefault(loop_key, asyncio.Lock())
        async with lock:
            cached = self._async_clients.get(loop_key)
            if cached is not None:
                return cached[0]
            stack = AsyncExitStack()
            client = await stack.enter_async_context(
                self.session.client(_S3_SERVICE_NAME, **self._client_kwargs)
            )
            self._async_clients[loop_key] = (client, stack)
            return client

    async def aclose(self) -> None:
        """Close the S3 client owned by the current event loop.

        Call from the application lifespan shutdown and at the end of each
        Celery task so sockets are not left dangling on a closed loop.
        """
        loop_key = id(asyncio.get_running_loop())
        cached = self._async_clients.pop(loop_key, None)
        self._async_client_locks.pop(loop_key, None)
        if cached is None:
            return
        try:
            await cached[1].aclose()
        except Exception as exc:  # noqa: BLE001 - shutdown must not raise
            logger.warning("Failed to close S3 client cleanly", exc_info=exc)

    def _signer(self) -> BaseClient:
        """Return the process-wide synchronous client used only for signing.

        Presigning never touches the network, so a synchronous client is both
        correct and callable from async code without blocking on I/O.
        """
        if self._signing_client is not None:
            return self._signing_client
        with self._signing_lock:
            if self._signing_client is None:
                settings = get_settings()
                client = boto3.client(
                    _S3_SERVICE_NAME,
                    aws_access_key_id=settings.aws_access_key_id or None,
                    aws_secret_access_key=settings.aws_secret_access_key or None,
                    region_name=settings.aws_region,
                    **self._client_kwargs,
                )
                register_cacheable_signer(client, settings.gallery_url_cache_bucket_seconds)
                self._signing_client = client
            return self._signing_client

    async def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        storage_class: str = "STANDARD",
    ) -> None:
        """Upload bytes to S3."""
        try:
            s3 = await self._client()
            await s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                StorageClass=storage_class,
            )
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Failed to put object {key} in {bucket}: {e}") from e

    async def get_object(self, bucket: str, key: str) -> bytes:
        """Download bytes from S3."""
        try:
            s3 = await self._client()
            response = await s3.get_object(Bucket=bucket, Key=key)
            async with response["Body"] as stream:
                from typing import cast

                return cast(bytes, await stream.read())
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Failed to get object {key} from {bucket}: {e}") from e

    async def delete_object(self, bucket: str, key: str) -> None:
        """Delete an object from S3."""
        try:
            s3 = await self._client()
            await s3.delete_object(Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Failed to delete object {key} from {bucket}: {e}") from e

    async def delete_objects(self, bucket: str, keys: list[str]) -> None:
        """Delete multiple objects from S3 efficiently."""
        if not keys:
            return

        try:
            s3 = await self._client()
            # S3 delete_objects supports up to 1000 keys per request
            for i in range(0, len(keys), 1000):
                batch = keys[i : i + 1000]
                await s3.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
                )
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Failed to delete {len(keys)} objects from {bucket}: {e}") from e

    def build_presigned_url(
        self,
        bucket: str,
        key: str,
        client_method: str = "get_object",
        expires_in: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        """Sign an S3 URL locally. See ``StorageService.build_presigned_url``."""
        if expires_in is None:
            expires_in = self.default_expiry

        params: dict[str, Any] = {"Bucket": bucket, "Key": key}
        if extra_params:
            params.update(extra_params)

        try:
            return str(
                self._signer().generate_presigned_url(
                    ClientMethod=client_method,
                    Params=params,
                    ExpiresIn=expires_in,
                )
            )
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Failed to generate presigned URL for {key}: {e}") from e

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        client_method: str = "get_object",
        expires_in: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        """Generate a presigned URL. Async only for interface compatibility."""
        return self.build_presigned_url(
            bucket,
            key,
            client_method=client_method,
            expires_in=expires_in,
            extra_params=extra_params,
        )

    async def change_storage_class(self, bucket: str, key: str, storage_class: str) -> None:
        """Change storage class via copy to self."""
        try:
            s3 = await self._client()
            await s3.copy_object(
                Bucket=bucket,
                Key=key,
                CopySource={"Bucket": bucket, "Key": key},
                StorageClass=storage_class,
                MetadataDirective="COPY",
            )
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Failed to change storage class for {key} in {bucket}: {e}") from e


class LocalStorageService(StorageService):
    """Local file system implementation for development/testing."""

    def __init__(self) -> None:
        self.base_dir = Path(".data/s3").resolve()
        settings = get_settings()
        self.default_expiry = settings.s3_presigned_url_expiry

    def _get_path(self, bucket: str, key: str) -> Path:
        path = self.base_dir / bucket / key
        # Prevent path traversal
        if not str(path).startswith(str(self.base_dir / bucket)):
            raise StorageError("Invalid path")
        return path

    async def put_object(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str,
        storage_class: str = "STANDARD",
    ) -> None:
        """Write bytes to local disk."""
        path = self._get_path(bucket, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def get_object(self, bucket: str, key: str) -> bytes:
        """Read bytes from local disk."""
        path = self._get_path(bucket, key)
        if not path.exists():
            raise StorageError(f"Object {key} not found in {bucket}")
        return path.read_bytes()

    async def delete_object(self, bucket: str, key: str) -> None:
        """Delete file from local disk."""
        path = self._get_path(bucket, key)
        if path.exists():
            path.unlink()

    async def delete_objects(self, bucket: str, keys: list[str]) -> None:
        """Delete multiple files from local disk."""
        for key in keys:
            path = self._get_path(bucket, key)
            if path.exists():
                path.unlink()

    def build_presigned_url(
        self,
        bucket: str,
        key: str,
        client_method: str = "get_object",
        expires_in: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        """Mock presigned URL generation.

        The returned host is not servable, so gallery responses fall back to the
        signed ``/preview`` route whenever local storage is active.
        """
        if expires_in is None:
            expires_in = self.default_expiry
        settings = get_settings()
        return f"{settings.api_base_url}/mock-s3/{bucket}/{key}?expires_in={expires_in}"

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        client_method: str = "get_object",
        expires_in: int | None = None,
        extra_params: dict[str, Any] | None = None,
    ) -> str:
        """Mock presigned URL generation."""
        return self.build_presigned_url(
            bucket,
            key,
            client_method=client_method,
            expires_in=expires_in,
            extra_params=extra_params,
        )

    async def change_storage_class(self, bucket: str, key: str, storage_class: str) -> None:
        """Mock change storage class (no-op)."""
        # Ensure file exists
        path = self._get_path(bucket, key)
        if not path.exists():
            raise StorageError(f"Object {key} not found in {bucket}")
        pass


def get_storage_service() -> StorageService:
    """Return the process-wide storage service.

    S3 sessions are reused so gallery traffic does not allocate a new
    ``aioboto3.Session`` (and underlying HTTP pools) on every request.
    """
    settings = get_settings()
    if settings.aws_access_key_id:
        return _s3_storage_service()
    return LocalStorageService()


def _s3_storage_service() -> S3StorageService:
    """Return a cached S3 storage client for this process."""
    return _S3StorageHolder.get()


async def close_storage_service() -> None:
    """Release the shared S3 client bound to the current event loop.

    Safe to call when S3 is not configured or no client was ever created.
    """
    instance = _S3StorageHolder.peek()
    if instance is not None:
        await instance.aclose()


class _S3StorageHolder:
    """Lazy singleton so tests can still construct ``S3StorageService`` directly."""

    _instance: S3StorageService | None = None

    @classmethod
    def get(cls) -> S3StorageService:
        """Return the shared S3 service, creating it on first use."""
        if cls._instance is None:
            cls._instance = S3StorageService()
        return cls._instance

    @classmethod
    def peek(cls) -> S3StorageService | None:
        """Return the shared S3 service only if it has already been created."""
        return cls._instance
