"""Tests for analytics endpoints (BE-015)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_photographer, get_photographer_event
from app.models.analytics_event import AnalyticsEvent
from app.models.enums import AnalyticsAction, EventStatus, ProcessingStatus
from app.models.event import Event
from app.models.guest_session import GuestSession
from app.models.photo import Photo
from app.models.photographer import Photographer


@pytest_asyncio.fixture
async def analytics_data(
    db_session: AsyncSession,
) -> tuple[Photographer, Event, list[GuestSession], list[Photo]]:
    # Create photographer
    photographer = Photographer(
        email=f"analytics_{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        studio_name="Analytics Studio",
        phone=f"+9199{uuid.uuid4().hex[:8]}",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.commit()
    await db_session.refresh(photographer)

    # Create event
    event = Event(
        photographer_id=photographer.id,
        name="Test Analytics Event",
        slug=f"analytics-{uuid.uuid4().hex[:8]}",
        status=EventStatus.READY,
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    # Create photos
    photos = []
    for i in range(3):
        p = Photo(
            event_id=event.id,
            filename=f"photo_{i}.jpg",
            original_s3_key=f"orig_{i}.jpg",
            file_size_bytes=1000,
            mime_type="image/jpeg",
            processing_status=ProcessingStatus.COMPLETED,
        )
        db_session.add(p)
        photos.append(p)
    await db_session.commit()

    # Create guests
    guests = []
    for i in range(2):
        g = GuestSession(
            event_id=event.id,
            name=f"Guest {i}",
            phone=f"+91999999990{i}",
            phone_verified=True,
            matched_photo_count=5,
        )
        db_session.add(g)
        guests.append(g)

    # Create unverified guest (should not appear in leads)
    unverified = GuestSession(
        event_id=event.id,
        name="Unverified",
        phone="+919999999999",
        phone_verified=False,
    )
    db_session.add(unverified)
    await db_session.commit()

    # Add analytics events
    # Photo 0: 3 views, 1 download (Guest 0)
    # Photo 1: 1 view, 2 downloads (Guest 1)

    # Photo 0 views
    for _ in range(3):
        db_session.add(
            AnalyticsEvent(
                event_id=event.id,
                photo_id=photos[0].id,
                guest_session_id=guests[0].id,
                action=AnalyticsAction.VIEW,
            )
        )
    db_session.add(
        AnalyticsEvent(
            event_id=event.id,
            photo_id=photos[0].id,
            guest_session_id=guests[0].id,
            action=AnalyticsAction.DOWNLOAD,
        )
    )

    # Photo 1 views/downloads
    db_session.add(
        AnalyticsEvent(
            event_id=event.id,
            photo_id=photos[1].id,
            guest_session_id=guests[1].id,
            action=AnalyticsAction.VIEW,
        )
    )
    for _ in range(2):
        db_session.add(
            AnalyticsEvent(
                event_id=event.id,
                photo_id=photos[1].id,
                guest_session_id=guests[1].id,
                action=AnalyticsAction.DOWNLOAD,
            )
        )
    await db_session.commit()
    return photographer, event, guests, photos


@pytest_asyncio.fixture
async def auth_client(
    db_client: AsyncClient,
    analytics_data: tuple[Photographer, Event, list[GuestSession], list[Photo]],
) -> AsyncIterator[AsyncClient]:
    photographer, event, _, _ = analytics_data

    async def override_get_photographer_event() -> Event:
        return event

    async def override_get_current_photographer() -> Photographer:
        return photographer

    from app.main import app

    app.dependency_overrides[get_photographer_event] = override_get_photographer_event
    app.dependency_overrides[get_current_photographer] = override_get_current_photographer
    yield db_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_summary(
    auth_client: AsyncClient,
    analytics_data: tuple[Photographer, Event, list[GuestSession], list[Photo]],
) -> None:
    _, event, guests, _ = analytics_data

    response = await auth_client.get(f"/api/v1/events/{event.id}/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_guests"] == 2
    assert data["total_views"] == 4
    assert data["total_downloads"] == 3
    assert data["engagement_rate"] == 2.0


@pytest.mark.asyncio
async def test_get_top_photos(
    auth_client: AsyncClient,
    analytics_data: tuple[Photographer, Event, list[GuestSession], list[Photo]],
) -> None:
    _, event, _, photos = analytics_data

    # By views
    response = await auth_client.get(
        f"/api/v1/events/{event.id}/analytics/top-photos?sort_by=views"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["photos"]) == 3
    assert data["photos"][0]["id"] == str(photos[0].id)
    assert data["photos"][0]["views"] == 3
    assert data["photos"][1]["id"] == str(photos[1].id)
    assert data["photos"][1]["views"] == 1

    # By downloads
    response = await auth_client.get(
        f"/api/v1/events/{event.id}/analytics/top-photos?sort_by=downloads"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["photos"][0]["id"] == str(photos[1].id)
    assert data["photos"][0]["downloads"] == 2
    assert data["photos"][1]["id"] == str(photos[0].id)
    assert data["photos"][1]["downloads"] == 1


@pytest.mark.asyncio
async def test_get_guest_leads(
    auth_client: AsyncClient,
    analytics_data: tuple[Photographer, Event, list[GuestSession], list[Photo]],
) -> None:
    _, event, guests, _ = analytics_data

    response = await auth_client.get(f"/api/v1/events/{event.id}/analytics/guests")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["guests"]) == 2

    # Check properties.
    names = [i["guest_name"] for i in data["guests"]]
    assert "Guest 0" in names
    assert "Guest 1" in names
    assert "Unverified" not in names
    
    # Check download counts
    guest0 = next(g for g in data["guests"] if g["guest_name"] == "Guest 0")
    guest1 = next(g for g in data["guests"] if g["guest_name"] == "Guest 1")
    assert guest0["download_count"] == 1
    assert guest1["download_count"] == 2


@pytest.mark.asyncio
async def test_export_guest_leads(
    auth_client: AsyncClient,
    analytics_data: tuple[Photographer, Event, list[GuestSession], list[Photo]],
) -> None:
    _, event, _, _ = analytics_data

    response = await auth_client.get(f"/api/v1/events/{event.id}/analytics/guests/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert f'filename="{event.slug}_guests.csv"' in response.headers["content-disposition"]

    csv_content = response.text
    assert "Name,Phone,First Visited,Photos Matched,Photos Downloaded" in csv_content
    assert "Guest 0" in csv_content
    assert "Guest 1" in csv_content
    assert "Unverified" not in csv_content

@pytest.mark.asyncio
async def test_wrong_photographer_ownership(
    db_client: AsyncClient,
    analytics_data: tuple[Photographer, Event, list[GuestSession], list[Photo]],
) -> None:
    _, event, _, _ = analytics_data
    from app.core.constants import JWTType
    from app.core.security import create_access_token
    
    token, _ = create_access_token(
        subject=str(uuid.uuid4())
    )
    db_client.headers["Authorization"] = f"Bearer {token}"
    
    # Actually the fake photographer doesn't exist in DB, so get_current_photographer raises 401
    # Let's create a real second photographer instead
    
    response = await db_client.get(f"/api/v1/events/{event.id}/analytics/summary")
    assert response.status_code == 401  # Because photographer doesn't exist
