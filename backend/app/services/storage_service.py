"""Storage service for S3 and local environments."""

from __future__ import annotations

import abc
from pathlib import Path

import aioboto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings
from app.core.exceptions import StorageError


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
    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        client_method: str = "get_object",
        expires_in: int | None = None,
    ) -> str:
        """Generate a presigned URL for GET or PUT."""
        ...

    @abc.abstractmethod
    async def change_storage_class(self, bucket: str, key: str, storage_class: str) -> None:
        """Change the storage class of an existing object."""
        ...


class S3StorageService(StorageService):
    """S3 implementation using aioboto3."""

    def __init__(self) -> None:
        settings = get_settings()
        self.session = aioboto3.Session(
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            region_name=settings.aws_region,
        )
        self.default_expiry = settings.s3_presigned_url_expiry

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
            async with self.session.client("s3") as s3:
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
            async with self.session.client("s3") as s3:
                response = await s3.get_object(Bucket=bucket, Key=key)
                async with response["Body"] as stream:
                    from typing import cast

                    return cast(bytes, await stream.read())
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Failed to get object {key} from {bucket}: {e}") from e

    async def delete_object(self, bucket: str, key: str) -> None:
        """Delete an object from S3."""
        try:
            async with self.session.client("s3") as s3:
                await s3.delete_object(Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Failed to delete object {key} from {bucket}: {e}") from e

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        client_method: str = "get_object",
        expires_in: int | None = None,
    ) -> str:
        """Generate a presigned URL."""
        if expires_in is None:
            expires_in = self.default_expiry
        try:
            async with self.session.client("s3") as s3:
                url = await s3.generate_presigned_url(
                    ClientMethod=client_method,
                    Params={"Bucket": bucket, "Key": key},
                    ExpiresIn=expires_in,
                )
                return str(url)
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Failed to generate presigned URL for {key}: {e}") from e

    async def change_storage_class(self, bucket: str, key: str, storage_class: str) -> None:
        """Change storage class via copy to self."""
        try:
            async with self.session.client("s3") as s3:
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

    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        client_method: str = "get_object",
        expires_in: int | None = None,
    ) -> str:
        """Mock presigned URL generation."""
        if expires_in is None:
            expires_in = self.default_expiry
        settings = get_settings()
        # Just return a mock localhost URL that clients can use (if we had a local route)
        return f"{settings.api_base_url}/mock-s3/{bucket}/{key}?expires_in={expires_in}"

    async def change_storage_class(self, bucket: str, key: str, storage_class: str) -> None:
        """Mock change storage class (no-op)."""
        # Ensure file exists
        path = self._get_path(bucket, key)
        if not path.exists():
            raise StorageError(f"Object {key} not found in {bucket}")
        pass


def get_storage_service() -> StorageService:
    """Return appropriate storage service."""
    settings = get_settings()
    if settings.aws_access_key_id:
        return S3StorageService()
    return LocalStorageService()
