"""Tests for couple (master) photos API, folders, and favorites."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from app.models.analytics_event import AnalyticsEvent
from app.models.couple_session import CoupleSession
from app.models.enums import AnalyticsAction, ProcessingStatus
from app.models.favorite import Favorite
from app.models.photo import Photo

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession


async def create_test_event_with_photos(db_session: AsyncSession) -> tuple[Any, Any, Any]:
    from tests.test_guest_auth import create_test_event

    event = await create_test_event(db_session)
    event.master_link_active = True
    await db_session.commit()

    # Create test couple session
    couple = CoupleSession(
        event_id=event.id,
        name="Test Couple",
        phone="+919988776655",
        phone_verified=True,
    )
    db_session.add(couple)
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

    return event, couple, photo


@pytest.fixture
async def couple_token(
    db_client: AsyncClient, db_session: AsyncSession
) -> tuple[str, Any, Any, Any]:
    event, couple, photo = await create_test_event_with_photos(db_session)

    from app.core.constants import JWTType
    from app.core.security import create_session_token

    token, _ = create_session_token(str(couple.id), str(event.id), JWTType.COUPLE)

    return token, event, couple, photo


@pytest.mark.asyncio
async def test_list_master_photos(
    db_client: AsyncClient,
    couple_token: tuple[str, Any, Any, Any],
) -> None:
    token, event, couple, photo = couple_token

    response = await db_client.get(
        f"/api/v1/event/{event.slug}/master/photos",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(photo.id)
    assert data["items"][0]["proxy_url"] is not None


@pytest.mark.asyncio
async def test_toggle_favorite(
    db_client: AsyncClient,
    db_session: AsyncSession,
    couple_token: tuple[str, Any, Any, Any],
) -> None:
    token, event, couple, photo = couple_token
    from sqlalchemy import select

    # Add favorite
    response = await db_client.post(
        f"/api/v1/event/{event.slug}/master/favorite",
        headers={"Authorization": f"Bearer {token}"},
        json={"photo_id": str(photo.id)},
    )
    assert response.status_code == 200
    assert response.json()["is_favorite"] is True

    # Check DB
    stmt = select(Favorite).where(
        Favorite.couple_session_id == couple.id, Favorite.photo_id == photo.id
    )
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is not None

    # List favorites
    list_response = await db_client.get(
        f"/api/v1/event/{event.slug}/master/favorites",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    # Remove favorite
    response2 = await db_client.post(
        f"/api/v1/event/{event.slug}/master/favorite",
        headers={"Authorization": f"Bearer {token}"},
        json={"photo_id": str(photo.id)},
    )
    assert response2.status_code == 200
    assert response2.json()["is_favorite"] is False


@pytest.mark.asyncio
async def test_download_master_photo(
    db_client: AsyncClient,
    db_session: AsyncSession,
    couple_token: tuple[str, Any, Any, Any],
) -> None:
    token, event, couple, photo = couple_token
    from sqlalchemy import select

    response = await db_client.get(
        f"/api/v1/event/{event.slug}/master/photos/{photo.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert "url" in response.json()

    # Verify analytics was recorded
    stmt = select(AnalyticsEvent).where(
        AnalyticsEvent.couple_session_id == couple.id,
        AnalyticsEvent.action == AnalyticsAction.DOWNLOAD,
    )
    result = await db_session.execute(stmt)
    analytics = result.scalar_one_or_none()
    assert analytics is not None
    assert analytics.photo_id == photo.id


@pytest.mark.asyncio
async def test_record_photo_view(
    db_client: AsyncClient,
    db_session: AsyncSession,
    couple_token: tuple[str, Any, Any, Any],
) -> None:
    token, event, couple, photo = couple_token
    from sqlalchemy import select

    response = await db_client.post(
        f"/api/v1/event/{event.slug}/photos/{photo.id}/view",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204

    # Verify analytics was recorded
    stmt = select(AnalyticsEvent).where(
        AnalyticsEvent.couple_session_id == couple.id, AnalyticsEvent.action == AnalyticsAction.VIEW
    )
    result = await db_session.execute(stmt)
    analytics = result.scalar_one_or_none()
    assert analytics is not None
    assert analytics.photo_id == photo.id

@pytest.mark.asyncio
async def test_couple_token_wrong_slug(
    db_client: AsyncClient,
    db_session: AsyncSession,
    couple_token: tuple[str, Any, Any, Any],
) -> None:
    token, _, _, _ = couple_token
    from tests.test_guest_auth import create_test_event

    other_event = await create_test_event(db_session)

    # Try to access other event with the couple token for the first event
    response = await db_client.get(
        f"/api/v1/event/{other_event.slug}/master/photos",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_list_master_folders(
    db_client: AsyncClient,
    db_session: AsyncSession,
    couple_token: tuple[str, Any, Any, Any],
) -> None:
    token, event, couple, photo = couple_token
    from app.models.folder import Folder

    folder = Folder(event_id=event.id, name="Root Folder")
    db_session.add(folder)
    await db_session.commit()

    response = await db_client.get(
        f"/api/v1/event/{event.slug}/master/folders",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["folders"]) == 1
    assert data["folders"][0]["name"] == "Root Folder"


@pytest.mark.asyncio
async def test_download_master_photo_disabled(
    db_client: AsyncClient,
    db_session: AsyncSession,
    couple_token: tuple[str, Any, Any, Any],
) -> None:
    token, event, couple, photo = couple_token

    # Disable download
    event.download_enabled = False
    await db_session.commit()

    response = await db_client.get(
        f"/api/v1/event/{event.slug}/master/photos/{photo.id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
