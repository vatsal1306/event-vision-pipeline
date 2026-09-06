"""Tests for StorageService (BE-008)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from botocore.exceptions import ClientError

from app.core.exceptions import StorageError
from app.services.storage_service import LocalStorageService, S3StorageService


@pytest.fixture
def local_storage(tmp_path: Path) -> LocalStorageService:
    service = LocalStorageService()
    service.base_dir = tmp_path
    return service


@pytest.mark.asyncio
async def test_local_storage_put_get_delete(local_storage: LocalStorageService) -> None:
    bucket = "test-bucket"
    key = "folder/file.txt"
    data = b"hello world"

    # Put
    await local_storage.put_object(bucket, key, data, "text/plain")

    # Get
    retrieved = await local_storage.get_object(bucket, key)
    assert retrieved == data

    # Delete
    await local_storage.delete_object(bucket, key)
    with pytest.raises(StorageError):
        await local_storage.get_object(bucket, key)


@pytest.mark.asyncio
async def test_local_storage_change_storage_class(local_storage: LocalStorageService) -> None:
    bucket = "test-bucket"
    key = "folder/file.txt"
    data = b"hello world"

    await local_storage.put_object(bucket, key, data, "text/plain")
    # Mock no-op
    await local_storage.change_storage_class(bucket, key, "GLACIER_IR")

    # Non-existent
    with pytest.raises(StorageError):
        await local_storage.change_storage_class(bucket, "non-existent", "STANDARD")


@pytest.mark.asyncio
async def test_local_storage_presigned_url(local_storage: LocalStorageService) -> None:
    url = await local_storage.generate_presigned_url("test-bucket", "test.jpg")
    assert "mock-s3/test-bucket/test.jpg" in url


@pytest.fixture
def mock_aioboto3_client():
    mock_client = AsyncMock()

    # Setup get_object mock
    mock_stream = AsyncMock()
    mock_stream.read.return_value = b"hello s3"

    mock_body_cm = AsyncMock()
    mock_body_cm.__aenter__.return_value = mock_stream

    mock_client.get_object.return_value = {"Body": mock_body_cm}
    mock_client.generate_presigned_url.return_value = "https://mock-url"

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client

    with patch("aioboto3.Session.client", return_value=mock_cm):
        yield mock_client


@pytest.mark.asyncio
async def test_s3_storage_put_get_delete(mock_aioboto3_client) -> None:
    service = S3StorageService()

    bucket = "test-bucket"
    key = "file.txt"
    data = b"hello s3"

    # Put
    await service.put_object(bucket, key, data, "text/plain", "STANDARD_IA")
    mock_aioboto3_client.put_object.assert_called_once_with(
        Bucket=bucket, Key=key, Body=data, ContentType="text/plain", StorageClass="STANDARD_IA"
    )

    # Get
    retrieved = await service.get_object(bucket, key)
    assert retrieved == b"hello s3"
    mock_aioboto3_client.get_object.assert_called_once_with(Bucket=bucket, Key=key)

    # Delete
    await service.delete_object(bucket, key)
    mock_aioboto3_client.delete_object.assert_called_once_with(Bucket=bucket, Key=key)

    # Test error handling
    mock_aioboto3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "GetObject"
    )
    with pytest.raises(StorageError):
        await service.get_object(bucket, key)


@pytest.mark.asyncio
async def test_s3_storage_change_class(mock_aioboto3_client) -> None:
    service = S3StorageService()

    bucket = "test-bucket"
    key = "class.txt"

    # Change to GLACIER_IR
    await service.change_storage_class(bucket, key, "GLACIER_IR")

    mock_aioboto3_client.copy_object.assert_called_once_with(
        Bucket=bucket,
        Key=key,
        CopySource={"Bucket": bucket, "Key": key},
        StorageClass="GLACIER_IR",
        MetadataDirective="COPY",
    )


@pytest.mark.asyncio
async def test_s3_storage_presign(mock_aioboto3_client) -> None:
    service = S3StorageService()

    url = await service.generate_presigned_url("test-bucket", "test.jpg")
    assert url == "https://mock-url"

    mock_aioboto3_client.generate_presigned_url.assert_called_once_with(
        ClientMethod="get_object",
        Params={"Bucket": "test-bucket", "Key": "test.jpg"},
        ExpiresIn=3600,
    )
