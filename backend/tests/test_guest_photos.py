"""Tests for guest photos API and selfie matching."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from app.models.enums import ProcessingStatus
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding
from app.models.guest_session import GuestSession
from app.models.photo import Photo

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_test_event_with_photos(db_session: AsyncSession) -> tuple[Any, Any]:
    from tests.test_guest_auth import create_test_event

    event = await create_test_event(db_session)

    # Create test guest session
    guest = GuestSession(
        event_id=event.id,
        name="Test Guest",
        phone="+919988776655",
        phone_verified=True,
    )
    db_session.add(guest)
    await db_session.commit()

    # Create a cluster
    cluster = FaceCluster(event_id=event.id, centroid=[0.1] * 512, cluster_size=1)
    db_session.add(cluster)
    await db_session.commit()

    # Create a photo
    photo = Photo(
        event_id=event.id,
        filename="test.jpg",
        original_s3_key="original.jpg",
        proxy_s3_key="proxy.jpg",
        file_size_bytes=1000,
        mime_type="image/jpeg",
        processing_status=ProcessingStatus.COMPLETED,
    )
    db_session.add(photo)
    await db_session.commit()

    # Create embedding
    embedding = FaceEmbedding(
        event_id=event.id,
        photo_id=photo.id,
        cluster_id=cluster.id,
        embedding=[0.1] * 512,
        bbox_x=0.0,
        bbox_y=0.0,
        bbox_w=0.0,
        bbox_h=0.0,
        detection_score=0.99,
        blur_score=0.0,
    )
    db_session.add(embedding)
    await db_session.commit()

    return event, guest, photo, cluster


@pytest.fixture
async def guest_token(
    db_client: AsyncClient, db_session: AsyncSession
) -> tuple[str, Any, Any, Any, Any]:
    event, guest, photo, cluster = await create_test_event_with_photos(db_session)

    from app.core.constants import JWTType
    from app.core.security import create_session_token

    token, _ = create_session_token(str(guest.id), str(event.id), JWTType.GUEST)

    return token, event, guest, photo, cluster


@pytest.mark.asyncio
async def test_upload_selfie_matched(
    db_client: AsyncClient,
    guest_token: tuple[str, Any, Any, Any, Any],
    monkeypatch: Any,
) -> None:
    token, event, guest, photo, cluster = guest_token

    from app.services.face_service import MatchResult

    mock_result = MatchResult(status="matched", clusters=[cluster.id], photo_ids=[photo.id])

    async def mock_match_selfie(*args: Any, **kwargs: Any) -> MatchResult:
        return mock_result

    monkeypatch.setattr("app.services.face_service.FaceService.match_selfie", mock_match_selfie)

    # Mock file upload
    file_content = b"fake_image_data"
    files = {"file": ("selfie.jpg", file_content, "image/jpeg")}

    response = await db_client.post(
        f"/api/v1/event/{event.slug}/selfie",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "matched"
    assert data["matched_photo_ids"] == [str(photo.id)]
    assert data["matched_photo_count"] == 1


@pytest.mark.asyncio
async def test_upload_selfie_no_match(
    db_client: AsyncClient,
    guest_token: tuple[str, Any, Any, Any, Any],
) -> None:
    token, event, guest, photo, cluster = guest_token

    # Not mocking FaceService here, so it returns the stub 'no_match'
    file_content = b"fake_image_data"
    files = {"file": ("selfie.jpg", file_content, "image/jpeg")}

    response = await db_client.post(
        f"/api/v1/event/{event.slug}/selfie",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_match"
    assert data["matched_photo_ids"] == []
    assert data["matched_photo_count"] == 0


@pytest.mark.asyncio
async def test_list_guest_photos(
    db_client: AsyncClient,
    db_session: AsyncSession,
    guest_token: tuple[str, Any, Any, Any, Any],
) -> None:
    token, event, guest, photo, cluster = guest_token

    # First, manually set the guest's matched clusters
    guest.matched_cluster_ids = [cluster.id]
    await db_session.commit()

    response = await db_client.get(
        f"/api/v1/event/{event.slug}/guest/photos",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(photo.id)
    assert data["items"][0]["proxy_url"] is not None


@pytest.mark.asyncio
async def test_list_guest_photos_empty(
    db_client: AsyncClient,
    guest_token: tuple[str, Any, Any, Any, Any],
) -> None:
    token, event, guest, photo, cluster = guest_token

    # No matched clusters
    response = await db_client.get(
        f"/api/v1/event/{event.slug}/guest/photos",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_download_guest_photo(
    db_client: AsyncClient,
    db_session: AsyncSession,
    guest_token: tuple[str, Any, Any, Any, Any],
) -> None:
    token, event, guest, photo, cluster = guest_token

    # First, manually set the guest's matched clusters
    guest.matched_cluster_ids = [cluster.id]
    await db_session.commit()

    response = await db_client.get(
        f"/api/v1/event/{event.slug}/photos/{photo.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "original.jpg" in data["url"]


@pytest.mark.asyncio
async def test_download_guest_photo_disabled(
    db_client: AsyncClient,
    db_session: AsyncSession,
    guest_token: tuple[str, Any, Any, Any, Any],
) -> None:
    token, event, guest, photo, cluster = guest_token

    # Manually disable downloads
    event.download_enabled = False
    guest.matched_cluster_ids = [cluster.id]
    await db_session.commit()

    response = await db_client.get(
        f"/api/v1/event/{event.slug}/photos/{photo.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert "Downloads are disabled" in response.json()["detail"]
