"""Integration tests for ClusterManager persistence (ML-006)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import numpy as np
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import create_redis_client
from app.ml.clustering import (
    CLUSTER_TYPE,
    CLUSTERING_LOCK_KEY_TEMPLATE,
    SWEEPER_TYPE,
    ClusteringResult,
    ClusterManager,
    EventClusteringLock,
    MergedCluster,
)
from app.ml.config import MLConfig
from app.ml.exceptions import ClusteringLockBusyError, ClusterPersistenceError
from app.models.event import Event
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding
from app.models.photo import Photo
from app.models.photographer import Photographer

pytest.importorskip("sklearn")

pytestmark = pytest.mark.ml

EMBEDDING_DIM = 512


def _unit_vector(seed: int) -> np.ndarray:
    """Build a deterministic L2-normalised 512-d vector."""
    rng = np.random.default_rng(seed)
    vector = rng.standard_normal(EMBEDDING_DIM).astype(np.float32)
    return vector / np.linalg.norm(vector)


def _near_vector(base: np.ndarray, seed: int, scale: float = 1e-3) -> np.ndarray:
    """Return a vector very close to ``base``."""
    rng = np.random.default_rng(seed)
    vector = base + rng.standard_normal(EMBEDDING_DIM).astype(np.float32) * scale
    return vector / np.linalg.norm(vector)


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator:
    """Real Redis client flushed for lock tests."""
    client = create_redis_client()
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001 — skip when Redis is down
        await client.aclose()
        pytest.skip(f"Redis unavailable for clustering lock tests: {exc}")
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


async def _seed_event(db_session: AsyncSession) -> tuple[Event, Photo]:
    """Insert a photographer, event, and photo required by face FK constraints."""
    photographer = Photographer(
        email=f"ml006-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hash",
        studio_name="ML006 Studio",
        phone=f"+91{uuid.uuid4().hex[:10]}",
        phone_verified=True,
    )
    db_session.add(photographer)
    await db_session.flush()

    event = Event(
        photographer_id=photographer.id,
        name="ML006 Event",
        slug=f"ml006-{uuid.uuid4().hex[:8]}",
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
    secondary: np.ndarray | None = None,
    cluster_id: uuid.UUID | None = None,
) -> FaceEmbedding:
    """Insert one face embedding row and return it."""
    row = FaceEmbedding(
        photo_id=photo_id,
        event_id=event_id,
        cluster_id=cluster_id,
        embedding=embedding.astype(np.float32).tolist(),
        secondary_embedding=None if secondary is None else secondary.astype(np.float32).tolist(),
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
    """Build a ClusterManager with lock retries suitable for tests."""
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
async def test_cluster_pass_assigns_ten_similar_embeddings(
    db_session: AsyncSession, redis_client
) -> None:
    """Ten near-identical frontal faces should all receive a cluster_id."""
    event, photo = await _seed_event(db_session)
    base = _unit_vector(1)
    for index in range(10):
        await _add_embedding(
            db_session,
            event_id=event.id,
            photo_id=photo.id,
            embedding=_near_vector(base, seed=100 + index),
        )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    result = await manager.run_clustering_pass(event.id, CLUSTER_TYPE)

    rows = (
        (await db_session.execute(select(FaceEmbedding).where(FaceEmbedding.event_id == event.id)))
        .scalars()
        .all()
    )
    assert all(row.cluster_id is not None for row in rows)
    cluster_ids = {row.cluster_id for row in rows}
    assert len(cluster_ids) == 1
    assert result.unassigned_crop_ids == []

    cluster = await db_session.get(FaceCluster, next(iter(cluster_ids)))
    assert cluster is not None
    assert cluster.cluster_size == 10
    assert cluster.secondary_centroid is None


@pytest.mark.asyncio
async def test_second_batch_expands_existing_cluster(
    db_session: AsyncSession, redis_client
) -> None:
    """A later batch of nearby faces should expand the existing cluster."""
    event, photo = await _seed_event(db_session)
    base = _unit_vector(20)
    for index in range(4):
        await _add_embedding(
            db_session,
            event_id=event.id,
            photo_id=photo.id,
            embedding=_near_vector(base, seed=200 + index),
            secondary=_near_vector(base, seed=300 + index),
        )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    await manager.run_clustering_pass(event.id, CLUSTER_TYPE)

    first = (
        await db_session.execute(select(FaceCluster).where(FaceCluster.event_id == event.id))
    ).scalar_one()
    old_centroid = np.asarray(first.centroid, dtype=np.float32)
    old_size = first.cluster_size

    for index in range(5):
        await _add_embedding(
            db_session,
            event_id=event.id,
            photo_id=photo.id,
            embedding=_near_vector(base, seed=400 + index),
            secondary=_near_vector(base, seed=500 + index),
        )
    await db_session.commit()

    result = await manager.run_clustering_pass(event.id, CLUSTER_TYPE)
    await db_session.refresh(first)

    assert result.expanded_clusters
    assert first.cluster_size == old_size + 5
    new_centroid = np.asarray(first.centroid, dtype=np.float32)
    assert not np.allclose(old_centroid, new_centroid)
    assert first.secondary_centroid is not None
    assert abs(float(np.linalg.norm(np.asarray(first.secondary_centroid))) - 1.0) < 1e-5

    assigned = (
        await db_session.execute(
            select(func.count())
            .select_from(FaceEmbedding)
            .where(
                FaceEmbedding.event_id == event.id,
                FaceEmbedding.cluster_id == first.id,
            )
        )
    ).scalar_one()
    assert assigned == 9


@pytest.mark.asyncio
async def test_merge_deletes_absorbed_cluster_and_reassigns_crops(
    db_session: AsyncSession, redis_client
) -> None:
    """Absorbed cluster rows are deleted and members move to the survivor."""
    event, photo = await _seed_event(db_session)
    base = _unit_vector(30)
    survivor = FaceCluster(
        event_id=event.id,
        centroid=base.tolist(),
        cluster_size=2,
        pyr_size=0,
    )
    absorbed = FaceCluster(
        event_id=event.id,
        centroid=_near_vector(base, seed=31).tolist(),
        cluster_size=2,
        pyr_size=0,
    )
    db_session.add_all([survivor, absorbed])
    await db_session.flush()

    for cluster, seed in ((survivor, 32), (absorbed, 33)):
        for offset in range(2):
            await _add_embedding(
                db_session,
                event_id=event.id,
                photo_id=photo.id,
                embedding=_near_vector(base, seed=seed + offset),
                cluster_id=cluster.id,
            )
    extra = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_near_vector(base, seed=40),
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    await manager.apply_clustering_result(
        event.id,
        ClusteringResult(
            merged_clusters=[
                MergedCluster(
                    surviving_cluster_id=str(survivor.id),
                    absorbed_cluster_ids=[str(absorbed.id)],
                    new_centroid=_near_vector(base, seed=41),
                    all_crop_ids=[str(extra.id)],
                    new_size=5,
                )
            ]
        ),
    )

    remaining = (
        (await db_session.execute(select(FaceCluster).where(FaceCluster.event_id == event.id)))
        .scalars()
        .all()
    )
    assert [row.id for row in remaining] == [survivor.id]
    assert remaining[0].cluster_size == 5

    orphan_clusters = (
        await db_session.execute(select(FaceCluster).where(FaceCluster.id == absorbed.id))
    ).scalar_one_or_none()
    assert orphan_clusters is None

    clustered = (
        (
            await db_session.execute(
                select(FaceEmbedding.cluster_id).where(FaceEmbedding.event_id == event.id)
            )
        )
        .scalars()
        .all()
    )
    assert set(clustered) == {survivor.id}


@pytest.mark.asyncio
async def test_cluster_pass_pyr_filter_excludes_high_and_boundary_angles(
    db_session: AsyncSession,
) -> None:
    """Cluster pass loads only faces whose absolute angles are all < 47°."""
    event, photo = await _seed_event(db_session)
    base = _unit_vector(50)
    included = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=base,
        yaw=10.0,
        pitch=-20.0,
        roll=30.0,
    )
    await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_near_vector(base, seed=51),
        yaw=47.0,
        pitch=10.0,
        roll=10.0,
    )
    await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_near_vector(base, seed=52),
        yaw=60.0,
        pitch=10.0,
        roll=10.0,
    )
    await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_near_vector(base, seed=53),
        quality_passed=False,
    )
    await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_near_vector(base, seed=54),
        yaw=None,
        pitch=10.0,
        roll=10.0,
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    loaded = await manager.load_unclustered_embeddings(event.id, CLUSTER_TYPE)
    assert set(loaded) == {str(included.id)}


@pytest.mark.asyncio
async def test_sweeper_pass_pyr_filter_loads_mid_range_angles(
    db_session: AsyncSession,
) -> None:
    """Sweeper pass loads faces with at least one angle in [47, 120] and none > 120."""
    event, photo = await _seed_event(db_session)
    base = _unit_vector(60)
    high = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=base,
        yaw=47.0,
        pitch=10.0,
        roll=10.0,
    )
    also = await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_near_vector(base, seed=61),
        yaw=10.0,
        pitch=90.0,
        roll=10.0,
    )
    await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_near_vector(base, seed=62),
        yaw=10.0,
        pitch=10.0,
        roll=10.0,
    )
    await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_near_vector(base, seed=63),
        yaw=130.0,
        pitch=10.0,
        roll=10.0,
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    loaded = await manager.load_unclustered_embeddings(event.id, SWEEPER_TYPE)
    assert set(loaded) == {str(high.id), str(also.id)}


@pytest.mark.asyncio
async def test_sweeper_pass_updates_pyr_centroid_not_main(
    db_session: AsyncSession, redis_client
) -> None:
    """Sweeper expand writes pyr_centroid and leaves the main centroid unchanged."""
    event, photo = await _seed_event(db_session)
    base = _unit_vector(70)
    cluster = FaceCluster(
        event_id=event.id,
        centroid=base.tolist(),
        cluster_size=3,
        pyr_size=0,
    )
    db_session.add(cluster)
    await db_session.flush()
    for index in range(3):
        await _add_embedding(
            db_session,
            event_id=event.id,
            photo_id=photo.id,
            embedding=_near_vector(base, seed=71 + index),
            cluster_id=cluster.id,
        )
    await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_near_vector(base, seed=80),
        yaw=60.0,
        pitch=10.0,
        roll=10.0,
    )
    await db_session.commit()

    manager = _manager(db_session, redis_client)
    result = await manager.run_clustering_pass(event.id, SWEEPER_TYPE)
    await db_session.refresh(cluster)

    assert result.expanded_clusters
    assert result.new_clusters == []
    assert np.allclose(np.asarray(cluster.centroid, dtype=np.float32), base, atol=1e-5)
    assert cluster.pyr_centroid is not None
    assert cluster.pyr_size >= 1


@pytest.mark.asyncio
async def test_concurrent_clustering_lock_blocks_second_pass(
    db_session: AsyncSession, redis_client
) -> None:
    """A second pass for the same event fails while the Redis lock is held."""
    event, photo = await _seed_event(db_session)
    await _add_embedding(
        db_session,
        event_id=event.id,
        photo_id=photo.id,
        embedding=_unit_vector(90),
    )
    await db_session.commit()

    holder = EventClusteringLock(redis_client, event.id, ttl_seconds=30)
    assert await holder.acquire()
    try:
        manager = _manager(db_session, redis_client)
        with pytest.raises(ClusteringLockBusyError):
            await manager.run_clustering_pass(event.id, CLUSTER_TYPE)
        stored = await redis_client.get(CLUSTERING_LOCK_KEY_TEMPLATE.format(event_id=event.id))
        assert stored is not None
    finally:
        await holder.release()


@pytest.mark.asyncio
async def test_apply_rolls_back_on_error(db_session: AsyncSession, redis_client) -> None:
    """A failure mid-apply leaves no partial cluster rows or assignments."""
    event, photo = await _seed_event(db_session)
    base = _unit_vector(95)
    for index in range(3):
        await _add_embedding(
            db_session,
            event_id=event.id,
            photo_id=photo.id,
            embedding=_near_vector(base, seed=96 + index),
        )
    await db_session.commit()
    event_id = event.id

    manager = _manager(db_session, redis_client)

    async def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("forced persistence failure")

    manager._persistence.refresh_secondary_centroids = _boom  # type: ignore[method-assign]

    with pytest.raises(ClusterPersistenceError):
        await manager.run_clustering_pass(event_id, CLUSTER_TYPE)

    db_session.expunge_all()

    cluster_count = await db_session.scalar(
        select(func.count()).select_from(FaceCluster).where(FaceCluster.event_id == event_id)
    )
    assert cluster_count == 0
    unclustered = (
        await db_session.execute(
            select(func.count())
            .select_from(FaceEmbedding)
            .where(
                FaceEmbedding.event_id == event_id,
                FaceEmbedding.cluster_id.is_(None),
            )
        )
    ).scalar_one()
    assert unclustered == 3
