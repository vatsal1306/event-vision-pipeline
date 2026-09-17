"""Tests for StorageService (BE-008)."""

import re
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import boto3
import pytest
from botocore.exceptions import ClientError

from app.config import get_settings
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
async def test_s3_storage_presign_targets_regional_virtual_host() -> None:
    """Presigning must address the bucket's region, not the legacy global host."""
    service = S3StorageService()
    settings = get_settings()

    url = await service.generate_presigned_url("test-bucket", "test.jpg")

    parsed = urlparse(url)
    assert parsed.netloc == f"test-bucket.s3.{settings.aws_region}.amazonaws.com"
    assert parsed.path == "/test.jpg"

    query = parse_qs(parsed.query)
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert settings.aws_region in query["X-Amz-Credential"][0]
    assert "X-Amz-Signature" in query


@pytest.mark.asyncio
async def test_s3_storage_presign_builds_one_client_for_many_urls() -> None:
    """Building a botocore client per request is what starved the event loop."""
    service = S3StorageService()

    with patch("app.services.storage_service.boto3.client", wraps=boto3.client) as client_factory:
        for index in range(25):
            await service.generate_presigned_url("test-bucket", f"test-{index}.jpg")

    assert client_factory.call_count == 1


def test_s3_storage_presign_is_stable_within_a_cache_bucket() -> None:
    """Identical URLs inside a bucket let the browser cache gallery images."""
    service = S3StorageService()

    first = service.build_presigned_url("test-bucket", "test.jpg", expires_in=7200)
    second = service.build_presigned_url("test-bucket", "test.jpg", expires_in=7200)

    assert first == second
    stamped = parse_qs(urlparse(first).query)["X-Amz-Date"][0]
    # Floored to the start of the hourly bucket: minutes and seconds are zero.
    assert re.fullmatch(r"\d{8}T\d{2}0000Z", stamped)
