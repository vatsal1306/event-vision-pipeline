"""Postgres integration tests for SelfieMatcher (pgvector centroids)."""

from __future__ import annotations

import uuid

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.config import MLConfig
from app.ml.matching.selfie_matcher import SelfieMatcher
from app.ml.matching.types import MatchStatus
from app.models.event import Event
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding
from app.models.photo import Photo
from app.models.photographer import Photographer

pytestmark = pytest.mark.ml

DIM = 512


def _unit(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(DIM).astype(np.float32)
    return vector / np.linalg.norm(vector)


@pytest_asyncio.fixture
async def seeded_event(db_session: AsyncSession) -> tuple[Event, FaceCluster, FaceCluster, Photo]:
    """Insert two clusters (identical + far) and one photo membership."""
    photographer = Photographer(
        email=f"ml008-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        studio_name="ML008 Studio",
        phone=f"+91{uuid.uuid4().hex[:10]}",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.flush()

    event = Event(
        photographer_id=photographer.id,
        name="ML008 Event",
        slug=f"ml008-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(event)
    await db_session.flush()

    query = _unit(21)
    match_cluster = FaceCluster(
        event_id=event.id,
        centroid=query.tolist(),
        secondary_centroid=_unit(22).tolist(),
        cluster_size=1,
    )
    far_cluster = FaceCluster(
        event_id=event.id,
        centroid=_unit(23).tolist(),
        secondary_centroid=_unit(24).tolist(),
        cluster_size=1,
    )
    db_session.add_all([match_cluster, far_cluster])
    await db_session.flush()

    photo = Photo(
        event_id=event.id,
        filename="guest.jpg",
        original_s3_key=f"originals/{event.id}/guest.jpg",
        file_size_bytes=1024,
        mime_type="image/jpeg",
    )
    db_session.add(photo)
    await db_session.flush()

    embedding = FaceEmbedding(
        photo_id=photo.id,
        event_id=event.id,
        cluster_id=match_cluster.id,
        embedding=query.tolist(),
        bbox_x=0.1,
        bbox_y=0.1,
        bbox_w=0.2,
        bbox_h=0.2,
        quality_passed=True,
    )
    db_session.add(embedding)
    await db_session.commit()
    return event, match_cluster, far_cluster, photo


@pytest.mark.asyncio
async def test_matcher_identical_centroid_matched(
    db_session: AsyncSession,
    seeded_event: tuple[Event, FaceCluster, FaceCluster, Photo],
) -> None:
    """Loading real centroids from Postgres should match an identical query."""
    event, match_cluster, _far, _photo = seeded_event
    query = np.asarray(match_cluster.centroid, dtype=np.float32)
    matcher = SelfieMatcher(db_session, config=MLConfig(selfie_pgvector_min_clusters=10_000))
    result = await matcher.match(query, event.id)
    assert result.status == MatchStatus.MATCHED
    assert match_cluster.id in result.matched_cluster_ids
    assert result.match_details[0].similarity == pytest.approx(1.0, abs=1e-4)


@pytest.mark.asyncio
async def test_matcher_far_query_no_match(
    db_session: AsyncSession,
    seeded_event: tuple[Event, FaceCluster, FaceCluster, Photo],
) -> None:
    """A far query against stored centroids should return no_match."""
    event, _match, _far, _photo = seeded_event
    matcher = SelfieMatcher(db_session, config=MLConfig(selfie_pgvector_min_clusters=10_000))
    result = await matcher.match(_unit(99), event.id)
    assert result.status == MatchStatus.NO_MATCH
    assert result.matched_cluster_ids == []


@pytest.mark.asyncio
async def test_matcher_event_without_clusters_no_clusters(db_session: AsyncSession) -> None:
    """An event with zero clusters should return no_clusters."""
    photographer = Photographer(
        email=f"ml008-empty-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        studio_name="Empty",
        phone=f"+91{uuid.uuid4().hex[:10]}",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.flush()
    event = Event(
        photographer_id=photographer.id,
        name="Empty",
        slug=f"ml008-empty-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(event)
    await db_session.commit()

    matcher = SelfieMatcher(db_session, config=MLConfig())
    result = await matcher.match(_unit(1), event.id)
    assert result.status == MatchStatus.NO_CLUSTERS


@pytest.mark.asyncio
async def test_matcher_pgvector_path(
    db_session: AsyncSession,
    seeded_event: tuple[Event, FaceCluster, FaceCluster, Photo],
) -> None:
    """Forcing the pgvector strategy should still return the identical cluster."""
    event, match_cluster, _far, _photo = seeded_event
    query = np.asarray(match_cluster.centroid, dtype=np.float32)
    matcher = SelfieMatcher(db_session, config=MLConfig(selfie_pgvector_min_clusters=1))
    result = await matcher.match(query, event.id)
    assert result.status == MatchStatus.MATCHED
    assert result.matched_cluster_ids[0] == match_cluster.id
