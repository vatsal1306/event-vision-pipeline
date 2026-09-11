"""Integration tests for orphan crop/cluster recovery (ML-007)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import create_redis_client
from app.ml.clustering import CLUSTER_TYPE, SWEEPER_TYPE, ClusterManager
from app.ml.config import MLConfig
from app.ml.exceptions import ClusterPersistenceError
from app.models.event import Event
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding
from app.models.photo import Photo
from app.models.photographer import Photographer

pytest.importorskip("sklearn")

pytestmark = pytest.mark.ml

EMBEDDING_DIM = 512


def _axis(index: int) -> np.ndarray:
    """Return a standard-basis unit vector."""
    vector = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vector[index] = 1.0
    return vector


def _blend(left: np.ndarray, right: np.ndarray, right_weight: float) -> np.ndarray:
    """Mix two unit vectors and re-normalise."""
    mixed = left * (1.0 - right_weight) + right * right_weight
    return mixed / np.linalg.norm(mixed)


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator:
    """Real Redis client flushed for lock tests."""
    client = create_redis_client()
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001 — skip when Redis is down
        await client.aclose()
        pytest.skip(f"Redis unavailable for orphan recovery lock tests: {exc}")
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


async def _seed_event(db_session: AsyncSession) -> tuple[Event, Photo]:
    """Insert photographer, event, and photo rows required by face FKs."""
    photographer = Photographer(
        email=f"ml007-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        studio_name="ML007 Studio",
        phone=f"+91{uuid.uuid4().hex[:10]}",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.flush()

    event = Event(
        photographer_id=photographer.id,
        name="ML007 Event",
        slug=f"ml007-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(event)
    await db_session.flush()

    photo = Photo(
        event_id=event.id,
        filename="face.jpg",
        original_s3_key=f"originals/{event.id}/face.jpg",
        file_size_bytes=1024,
        mime_type="image/jpeg",
    )
    db_session.add(photo)
    await db_session.commit()
    return event, photo


async def _add_embedding(
    db_session: AsyncSession,
    *,
    event_id: uuid.UUID,
    photo_id: uuid.UUID,
    embedding: np.ndarray,
    yaw: float | None = 5.0,
    pitch: float | None = 4.0,
    roll: float | None = 3.0,
    quality_passed: bool = True,
    cluster_id: uuid.UUID | None = None,
) -> FaceEmbedding:
    """Insert one face embedding row."""
    row = FaceEmbedding(
        photo_id=photo_id,
        event_id=event_id,
        cluster_id=cluster_id,
        embedding=embedding.astype(np.float32).tolist(),
        bbox_x=0.1,
        bbox_y=0.1,
        bbox_w=0.2,
        bbox_h=0.2,
        detection_score=0.99,
        blur_score=0.1,
        yaw=yaw,
        pitch=pitch,
        roll=roll,
        quality_passed=quality_passed,
    )
    db_session.add(row)
    await db_session.flush()
    return row


def _manager(
    db_session: AsyncSession,
    redis_client,
    **config_overrides: object,
) -> ClusterManager:
    """Build a ClusterManager with short lock retries for tests."""
    config = MLConfig(
        clustering_lock_ttl_seconds=30,
        clustering_lock_retry_attempts=2,
        clustering_lock_retry_base_delay_seconds=0.01,
        **config_overrides,
    )
    return ClusterManager(
        db_session,
        redis_client=redis_client,
        ml_config=config,
    )


@pytest.mark.asyncio
async def test_orphan_crop_high_similarity_assigned_to_pyr_cluster(
    db_session: AsyncSession, redis_client
) -> None:
    """A sweeper leftover near a PYR centroid is assigned; main centroid is unchanged."""
    event, photo = await _seed_event(db_session)
    main = _axis(0)
    pyr = _axis(1)
    cluster = FaceCluster(
        event_id=event.id,
        centroid=main.tolist(),
        pyr_centroid=pyr.tolist(),
        cluster_size=8,
        pyr_size=3,
    )
    db_session.add(cluster)
    await db_session.flush()
    orphan = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_blend(pyr, _axis(2), 0.01),
        yaw=60.0,
        pitch=10.0,
        roll=10.0,
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    result = await manager.run_recovery(event.id)
    await db_session.refresh(cluster)
    await db_session.refresh(orphan)

    assert result.skipped is False
    assert result.crop_result.recovered == 1
    assert result.crop_result.still_orphaned == 0
    assert orphan.cluster_id == cluster.id
    assert cluster.cluster_size == 9
    assert cluster.pyr_size == 4
    assert np.allclose(np.asarray(cluster.centroid, dtype=np.float32), main, atol=1e-5)
    assert cluster.pyr_centroid is not None
    assert not np.allclose(np.asarray(cluster.pyr_centroid, dtype=np.float32), pyr, atol=1e-6)


@pytest.mark.asyncio
async def test_orphan_crop_low_similarity_remains_unassigned(
    db_session: AsyncSession, redis_client
) -> None:
    """A leftover far from every PYR centroid stays unclustered."""
    event, photo = await _seed_event(db_session)
    cluster = FaceCluster(
        event_id=event.id,
        centroid=_axis(0).tolist(),
        pyr_centroid=_axis(1).tolist(),
        cluster_size=8,
        pyr_size=3,
    )
    db_session.add(cluster)
    await db_session.flush()
    orphan = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_axis(2),
        yaw=80.0,
        pitch=10.0,
        roll=10.0,
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    result = await manager.run_recovery(event.id)
    await db_session.refresh(orphan)

    assert result.crop_result.recovered == 0
    assert result.crop_result.still_orphaned == 1
    assert orphan.cluster_id is None


@pytest.mark.asyncio
async def test_orphan_crop_does_not_match_main_centroid_without_pyr(
    db_session: AsyncSession, redis_client
) -> None:
    """Clusters without PYR centroids are ignored even if the main centroid is close."""
    event, photo = await _seed_event(db_session)
    face = _axis(0)
    cluster = FaceCluster(
        event_id=event.id,
        centroid=face.tolist(),
        pyr_centroid=None,
        cluster_size=8,
        pyr_size=0,
    )
    db_session.add(cluster)
    await db_session.flush()
    orphan = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=face,
        yaw=70.0,
        pitch=10.0,
        roll=10.0,
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    result = await manager.run_recovery(event.id)
    await db_session.refresh(orphan)

    assert result.crop_result.recovered == 0
    assert orphan.cluster_id is None


@pytest.mark.asyncio
async def test_two_orphan_crops_same_cluster_update_pyr_once(
    db_session: AsyncSession, redis_client
) -> None:
    """Two leftovers matching one cluster both assign and share one PYR update."""
    event, photo = await _seed_event(db_session)
    pyr = _axis(1)
    cluster = FaceCluster(
        event_id=event.id,
        centroid=_axis(0).tolist(),
        pyr_centroid=pyr.tolist(),
        cluster_size=5,
        pyr_size=2,
    )
    db_session.add(cluster)
    await db_session.flush()
    first = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_blend(pyr, _axis(2), 0.01),
        yaw=55.0,
        pitch=10.0,
        roll=10.0,
    )
    second = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_blend(pyr, _axis(3), 0.01),
        yaw=90.0,
        pitch=12.0,
        roll=8.0,
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    result = await manager.run_recovery(event.id)
    await db_session.refresh(cluster)
    await db_session.refresh(first)
    await db_session.refresh(second)

    assert result.crop_result.recovered == 2
    assert {first.cluster_id, second.cluster_id} == {cluster.id}
    assert cluster.cluster_size == 7
    assert cluster.pyr_size == 4


@pytest.mark.asyncio
async def test_small_cluster_merges_into_large_cluster(
    db_session: AsyncSession, redis_client
) -> None:
    """A size-2 cluster matching a size-50 cluster is absorbed."""
    event, photo = await _seed_event(db_session)
    base = _axis(0)
    large = FaceCluster(
        event_id=event.id,
        centroid=base.tolist(),
        cluster_size=50,
        pyr_size=0,
    )
    small = FaceCluster(
        event_id=event.id,
        centroid=_blend(base, _axis(1), 0.01).tolist(),
        cluster_size=2,
        pyr_size=0,
    )
    db_session.add_all([large, small])
    await db_session.flush()
    for _offset in range(2):
        await _add_embedding(
            db_session,
            event_id=event.id,
            photo_id=photo.id,
            embedding=_blend(base, _axis(1), 0.01),
            cluster_id=small.id,
        )
    await db_session.commit()
    small_id = small.id

    manager = _manager(db_session, redis_client)
    result = await manager.run_recovery(event.id)
    await db_session.refresh(large)

    assert result.merge_result.merged_count == 1
    assert result.merge_result.remaining_orphans == 0
    assert large.cluster_size == 52
    missing = (
        await db_session.execute(select(FaceCluster).where(FaceCluster.id == small_id))
    ).scalar_one_or_none()
    assert missing is None
    member_clusters = (
        (
            await db_session.execute(
                select(FaceEmbedding.cluster_id).where(FaceEmbedding.event_id == event.id)
            )
        )
        .scalars()
        .all()
    )
    assert set(member_clusters) == {large.id}


@pytest.mark.asyncio
async def test_dissimilar_orphan_cluster_remains_independent(
    db_session: AsyncSession, redis_client
) -> None:
    """A small cluster far from every established cluster is not merged."""
    event, photo = await _seed_event(db_session)
    large = FaceCluster(
        event_id=event.id,
        centroid=_axis(0).tolist(),
        cluster_size=50,
        pyr_size=0,
    )
    small = FaceCluster(
        event_id=event.id,
        centroid=_axis(1).tolist(),
        cluster_size=2,
        pyr_size=0,
    )
    db_session.add_all([large, small])
    await db_session.flush()
    await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_axis(1),
        cluster_id=small.id,
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    result = await manager.run_recovery(event.id)
    remaining = (
        (await db_session.execute(select(FaceCluster).where(FaceCluster.event_id == event.id)))
        .scalars()
        .all()
    )
    assert result.merge_result.merged_count == 0
    assert result.merge_result.remaining_orphans == 1
    assert {row.id for row in remaining} == {large.id, small.id}


@pytest.mark.asyncio
async def test_dual_centroid_pyr_match_merges_when_main_centroids_differ(
    db_session: AsyncSession, redis_client
) -> None:
    """PYR-vs-PYR similarity can merge clusters whose main centroids would not."""
    event, photo = await _seed_event(db_session)
    pyr = _axis(2)
    large = FaceCluster(
        event_id=event.id,
        centroid=_axis(0).tolist(),
        pyr_centroid=pyr.tolist(),
        cluster_size=12,
        pyr_size=4,
    )
    small = FaceCluster(
        event_id=event.id,
        centroid=_axis(1).tolist(),
        pyr_centroid=_blend(pyr, _axis(3), 0.01).tolist(),
        cluster_size=2,
        pyr_size=2,
    )
    db_session.add_all([large, small])
    await db_session.flush()
    await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_axis(1),
        cluster_id=small.id,
    )
    await db_session.commit()
    small_id = small.id

    manager = _manager(db_session, redis_client)
    result = await manager.run_recovery(event.id)

    assert result.merge_result.merged_count == 1
    assert result.merge_result.details[0]["match_type"] == "pyr_centroid"
    missing = (
        await db_session.execute(select(FaceCluster).where(FaceCluster.id == small_id))
    ).scalar_one_or_none()
    assert missing is None


@pytest.mark.asyncio
async def test_recovery_disabled_by_flag_makes_no_writes(
    db_session: AsyncSession, redis_client
) -> None:
    """ML_ORPHAN_RECOVERY_ENABLED=false leaves leftovers and small clusters untouched."""
    event, photo = await _seed_event(db_session)
    pyr = _axis(1)
    large = FaceCluster(
        event_id=event.id,
        centroid=_axis(0).tolist(),
        pyr_centroid=pyr.tolist(),
        cluster_size=10,
        pyr_size=3,
    )
    small = FaceCluster(
        event_id=event.id,
        centroid=_axis(0).tolist(),
        cluster_size=2,
        pyr_size=0,
    )
    db_session.add_all([large, small])
    await db_session.flush()
    orphan = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=pyr,
        yaw=60.0,
        pitch=10.0,
        roll=10.0,
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client, orphan_recovery_enabled=False)
    result = await manager.run_recovery(event.id)
    await db_session.refresh(orphan)

    assert result.skipped is True
    assert result.crop_result.recovered == 0
    assert orphan.cluster_id is None
    cluster_count = await db_session.scalar(
        select(func.count()).select_from(FaceCluster).where(FaceCluster.event_id == event.id)
    )
    assert cluster_count == 2


@pytest.mark.asyncio
async def test_recovery_after_sweeper_pass(db_session: AsyncSession, redis_client) -> None:
    """Cluster → sweeper → recovery assigns a leftover sweeper did not take."""
    event, photo = await _seed_event(db_session)
    main = _axis(0)
    pyr = _axis(1)
    cluster = FaceCluster(
        event_id=event.id,
        centroid=main.tolist(),
        pyr_centroid=pyr.tolist(),
        cluster_size=8,
        pyr_size=3,
    )
    db_session.add(cluster)
    await db_session.flush()
    for index in range(3):
        await _add_embedding(
            db_session,
            event_id=event.id,
            photo_id=photo.id,
            embedding=_blend(main, _axis(2), 0.002 * (index + 1)),
            yaw=5.0,
            pitch=4.0,
            roll=3.0,
        )
    leftover = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_blend(pyr, _axis(3), 0.01),
        yaw=70.0,
        pitch=10.0,
        roll=10.0,
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    await manager.run_clustering_pass(event.id, CLUSTER_TYPE)
    await manager.run_clustering_pass(event.id, SWEEPER_TYPE)
    await db_session.refresh(leftover)
    assert leftover.cluster_id is None

    result = await manager.run_recovery(event.id)
    await db_session.refresh(leftover)
    await db_session.refresh(cluster)

    assert result.skipped is False
    assert leftover.cluster_id == cluster.id
    assert result.crop_result.recovered == 1


@pytest.mark.asyncio
async def test_recovery_rolls_back_failed_batch(db_session: AsyncSession, redis_client) -> None:
    """A persistence failure during crop assignment leaves the leftover unassigned."""
    event, photo = await _seed_event(db_session)
    pyr = _axis(1)
    cluster = FaceCluster(
        event_id=event.id,
        centroid=_axis(0).tolist(),
        pyr_centroid=pyr.tolist(),
        cluster_size=8,
        pyr_size=3,
    )
    db_session.add(cluster)
    await db_session.flush()
    orphan = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=pyr,
        yaw=60.0,
        pitch=10.0,
        roll=10.0,
    )
    await db_session.commit()
    event_id = event.id
    orphan_id = orphan.id
    cluster_id = cluster.id
    cluster_size_before = cluster.cluster_size

    manager = _manager(db_session, redis_client)

    async def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("forced recovery persistence failure")

    manager._persistence.refresh_secondary_centroids = _boom  # type: ignore[method-assign]

    with pytest.raises(ClusterPersistenceError):
        await manager.run_recovery(event_id)

    db_session.expunge_all()
    orphan_row = await db_session.get(FaceEmbedding, orphan_id)
    cluster_row = await db_session.get(FaceCluster, cluster_id)
    assert orphan_row is not None
    assert orphan_row.cluster_id is None
    assert cluster_row is not None
    assert cluster_row.cluster_size == cluster_size_before
