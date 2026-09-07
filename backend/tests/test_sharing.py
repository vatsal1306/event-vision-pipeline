"""Tests for public event sharing info (BE-011)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EventStatus
from app.models.event import Event
from app.models.photographer import Photographer


async def create_test_photographer_and_event(
    db: AsyncSession, with_logo: bool = False
) -> tuple[Photographer, Event]:
    photographer = Photographer(
        email=f"share_{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        studio_name="Share Studio",
        phone=f"+9199{uuid.uuid4().hex[:8]}",
        phone_verified=True,
    )
    if with_logo:
        photographer.logo_url = "logos/test_logo.png"

    db.add(photographer)
    await db.commit()
    await db.refresh(photographer)

    event = Event(
        photographer_id=photographer.id,
        name="Test Sharing Event",
        slug=f"share-slug-{uuid.uuid4().hex[:8]}",
        status=EventStatus.READY,
        guest_link_active=True,
        master_link_active=False,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    return photographer, event


@pytest.mark.asyncio
async def test_get_public_info_success(
    db_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test retrieving public info for a valid event slug without a logo."""
    photographer, event = await create_test_photographer_and_event(db_session, with_logo=False)

    response = await db_client.get(f"/api/v1/event/{event.slug}/info")
    assert response.status_code == 200

    data = response.json()
    assert data["event"]["name"] == event.name
    assert data["event"]["slug"] == event.slug
    assert data["event"]["download_enabled"] is True
    assert data["photographer"]["studio_name"] == photographer.studio_name
    assert data["photographer"]["logo_url"] is None
    assert data["event"]["guest_link_active"] is True
    assert data["event"]["master_link_active"] is False


@pytest.mark.asyncio
async def test_get_public_info_with_logo(
    db_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test retrieving public info presigns the studio logo if present."""
    photographer, event = await create_test_photographer_and_event(db_session, with_logo=True)

    response = await db_client.get(f"/api/v1/event/{event.slug}/info")
    assert response.status_code == 200

    data = response.json()
    assert data["event"]["name"] == event.name
    assert data["photographer"]["studio_name"] == photographer.studio_name
    assert data["photographer"]["logo_url"] is not None
    assert "logos/test_logo.png" in data["photographer"]["logo_url"]
    assert "expires_in=" in data["photographer"]["logo_url"]


@pytest.mark.asyncio
async def test_get_public_info_not_found(
    db_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test requesting info for a non-existent slug returns 404."""
    response = await db_client.get("/api/v1/event/invalid-slug-123/info")
    assert response.status_code == 404
    assert response.json()["detail"] == "Event with slug 'invalid-slug-123' not found"
