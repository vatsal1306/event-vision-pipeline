"""Tests for photographer profile endpoints."""

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_photographer
from app.main import app
from app.models.enums import EventStatus
from app.models.event import Event
from app.models.photo import Photo
from app.models.photographer import Photographer


@pytest_asyncio.fixture
async def profile_photographer(db_session: AsyncSession) -> Photographer:
    photographer = Photographer(
        email=f"profile_{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        studio_name="Profile Studio",
        phone=f"+9199{uuid.uuid4().hex[:8]}",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.commit()
    await db_session.refresh(photographer)
    return photographer


@pytest_asyncio.fixture
async def auth_client(
    db_client: AsyncClient,
    profile_photographer: Photographer,
) -> AsyncIterator[AsyncClient]:
    async def override_get_current_photographer() -> Photographer:
        return profile_photographer

    app.dependency_overrides[get_current_photographer] = override_get_current_photographer
    yield db_client
    app.dependency_overrides.pop(get_current_photographer, None)


@pytest.mark.asyncio
async def test_get_profile(
    auth_client: AsyncClient, db_session: AsyncSession, profile_photographer: Photographer
) -> None:
    """Test fetching photographer profile."""
    # Ensure there are keys to presign
    profile_photographer.logo_url = "profiles/test/logo.jpg"
    profile_photographer.watermark_url = "profiles/test/watermark.png"
    await db_session.commit()

    response = await auth_client.get("/api/v1/profile")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == profile_photographer.email
    assert data["studio_name"] == profile_photographer.studio_name
    assert "logo_url" in data
    assert "watermark_url" in data
    assert data["logo_url"].startswith("http")
    assert data["watermark_url"].startswith("http")


@pytest.mark.asyncio
async def test_update_profile(
    auth_client: AsyncClient, db_session: AsyncSession, profile_photographer: Photographer
) -> None:
    """Test updating studio name and ensuring presigned URLs are returned."""
    # Ensure there are keys to presign
    profile_photographer.logo_url = "profiles/test/logo.jpg"
    await db_session.commit()
    
    response = await auth_client.put(
        "/api/v1/profile",
        json={"studio_name": "New Studio Name"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["studio_name"] == "New Studio Name"
    assert data["logo_url"].startswith("http")


@pytest.mark.asyncio
async def test_upload_logo_success(auth_client: AsyncClient) -> None:
    """Test successful logo upload."""
    # Create fake JPEG bytes
    file_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"

    files = {"file": ("logo.jpg", file_content, "image/jpeg")}

    response = await auth_client.post(
        "/api/v1/profile/logo",
        files=files
    )
    assert response.status_code == 200
    assert "url" in response.json()


@pytest.mark.asyncio
async def test_upload_logo_webp_success(auth_client: AsyncClient) -> None:
    """Test successful WEBP logo upload."""
    # Create fake WEBP bytes: RIFF + size (4 bytes) + WEBP
    file_content = b"RIFF\x00\x00\x00\x00WEBPVP8 "
    
    files = {
        "file": ("logo.webp", file_content, "image/webp")
    }
    
    response = await auth_client.post(
        "/api/v1/profile/logo",
        files=files
    )
    assert response.status_code == 200
    assert "url" in response.json()


@pytest.mark.asyncio
async def test_upload_logo_too_large(auth_client: AsyncClient) -> None:
    """Test logo upload fails if file exceeds 10MB."""
    # 10MB + 1 byte
    file_content = b"\xff\xd8\xff\xe0" + b"\x00" * (10 * 1024 * 1024)
    
    files = {
        "file": ("logo.jpg", file_content, "image/jpeg")
    }
    
    response = await auth_client.post(
        "/api/v1/profile/logo",
        files=files
    )
    assert response.status_code == 422
    assert "File too large" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_logo_invalid_type(auth_client: AsyncClient) -> None:
    """Test logo upload fails with invalid file type."""
    files = {"file": ("logo.txt", b"not an image", "text/plain")}

    response = await auth_client.post("/api/v1/profile/logo", files=files)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_upload_watermark_success(auth_client: AsyncClient) -> None:
    """Test successful watermark upload."""
    # Create fake PNG bytes
    file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

    files = {"file": ("watermark.png", file_content, "image/png")}

    response = await auth_client.post(
        "/api/v1/profile/watermark",
        files=files
    )
    assert response.status_code == 200
    assert "url" in response.json()


@pytest.mark.asyncio
async def test_upload_watermark_wrong_magic_bytes(auth_client: AsyncClient) -> None:
    """Test watermark upload fails if content type is PNG but bytes are JPEG."""
    file_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    
    files = {
        "file": ("watermark.png", file_content, "image/png")
    }
    
    response = await auth_client.post(
        "/api/v1/profile/watermark",
        files=files
    )
    assert response.status_code == 422
    assert "Invalid image signature" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_watermark_invalid_type(auth_client: AsyncClient) -> None:
    """Test watermark upload fails if not PNG."""
    # Even if valid JPEG, it should fail
    file_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"

    files = {"file": ("watermark.jpg", file_content, "image/jpeg")}

    response = await auth_client.post("/api/v1/profile/watermark", files=files)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_get_storage_info(
    auth_client: AsyncClient, db_session: AsyncSession, profile_photographer: Photographer
) -> None:
    """Test fetching detailed storage info."""
    # Setup active and archived events with some photos
    active_event = Event(
        photographer_id=profile_photographer.id,
        name="Active",
        slug=f"active-{uuid.uuid4().hex[:8]}",
        status=EventStatus.READY,
    )
    archived_event = Event(
        photographer_id=profile_photographer.id,
        name="Archived",
        slug=f"archived-{uuid.uuid4().hex[:8]}",
        status=EventStatus.ARCHIVED,
    )
    db_session.add(active_event)
    db_session.add(archived_event)
    await db_session.commit()

    # Add photos
    photo1 = Photo(
        event_id=active_event.id,
        filename="p1.jpg",
        original_s3_key="orig1.jpg",
        file_size_bytes=1000000,
        mime_type="image/jpeg",
    )
    photo2 = Photo(
        event_id=archived_event.id,
        filename="p2.jpg",
        original_s3_key="orig2.jpg",
        file_size_bytes=2000000,
        mime_type="image/jpeg",
    )
    db_session.add(photo1)
    db_session.add(photo2)
    await db_session.commit()

    response = await auth_client.get("/api/v1/profile/storage")
    assert response.status_code == 200
    data = response.json()

    assert data["active_bytes"] == 1000000
    assert data["archived_bytes"] == 2000000
    assert data["used"] == 3000000
    assert data["limit"] == profile_photographer.storage_limit_bytes
    assert "used_percentage" in data

@pytest.mark.asyncio
async def test_get_storage_info_zero_photos(
    auth_client: AsyncClient, 
    db_session: AsyncSession,
    profile_photographer: Photographer
) -> None:
    """Test fetching storage info when no photos exist."""
    response = await auth_client.get("/api/v1/profile/storage")
    assert response.status_code == 200
    data = response.json()
    
    assert data["active_bytes"] == 0
    assert data["archived_bytes"] == 0
    assert data["used"] == 0
    assert data["limit"] == profile_photographer.storage_limit_bytes
    assert data["used_percentage"] == 0.0
