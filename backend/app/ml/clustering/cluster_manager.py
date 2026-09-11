"""Persist incremental clustering results into PostgreSQL + pgvector."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Collection

import numpy as np
import redis.asyncio as redis
import structlog
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.clustering.cluster_persistence import ClusterPersistence
from app.ml.clustering.incremental_clusterer import IncrementalClusterer
from app.ml.clustering.locks import EventClusteringLock
from app.ml.clustering.types import (
    ClusteringInput,
    ClusteringResult,
    ClusteringTypeConfig,
    ExistingCluster,
)
from app.ml.clustering.vector_utils import as_float32_vector, merge_clustering_results
from app.ml.config import MLConfig, get_ml_config
from app.ml.exceptions import (
    ClusteringLockBusyError,
    ClusteringLockError,
    ClusterPersistenceError,
)
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding

logger = structlog.get_logger(__name__)

_SWEEPER_PASS_NAME = "sweeper"


class ClusterManager:
    """Bridge ``IncrementalClusterer`` with SpotMe cluster tables.

    Loads cluster centroids and unclustered embeddings, runs one batched
    clustering pass, and writes new / expanded / merged clusters in one
    transaction per batch.
    """

    def __init__(
        self,
        db: AsyncSession,
        redis_client: redis.Redis | None = None,
        clusterer: IncrementalClusterer | None = None,
        ml_config: MLConfig | None = None,
    ) -> None:
        """Create a manager bound to one database session.

        Args:
            db: Async SQLAlchemy session used for loads and writes.
            redis_client: Required for ``run_clustering_pass`` (event lock).
            clusterer: Optional clusterer override. Defaults to ``IncrementalClusterer``.
            ml_config: Optional ML settings override.
        """
        self._db = db
        self._redis = redis_client
        self._config = ml_config or get_ml_config()
        self._clusterer = clusterer or IncrementalClusterer(ml_config=self._config)
        self._persistence = ClusterPersistence(db)

    async def load_event_clusters(self, event_id: uuid.UUID) -> dict[str, ExistingCluster]:
        """Load all clusters for an event as algorithm input snapshots.

        Args:
            event_id: Event whose ``face_clusters`` rows should be loaded.

        Returns:
            Mapping of cluster UUID string to ``ExistingCluster``. Crop IDs are
            omitted; merge persistence reassigns members by ``cluster_id``.
        """
        result = await self._db.execute(select(FaceCluster).where(FaceCluster.event_id == event_id))
        clusters: dict[str, ExistingCluster] = {}
        for row in result.scalars().all():
            clusters[str(row.id)] = ExistingCluster(
                centroid=as_float32_vector(row.centroid),
                size=row.cluster_size,
                crop_ids=[],
                pyr_centroid=(
                    as_float32_vector(row.pyr_centroid) if row.pyr_centroid is not None else None
                ),
                pyr_size=row.pyr_size,
            )
        return clusters

    async def load_unclustered_embeddings(
        self,
        event_id: uuid.UUID,
        clustering_type: ClusteringTypeConfig,
        *,
        limit: int | None = None,
        exclude_ids: Collection[uuid.UUID] | None = None,
    ) -> dict[str, np.ndarray]:
        """Load quality-passed embeddings with no cluster, filtered by PYR range.

        Cluster pass: every absolute yaw/pitch/roll is in ``[low, high)``.
        Sweeper pass: every absolute angle is ``<= high`` and at least one is
        ``>= low``. Missing angles are excluded from both passes.

        Args:
            event_id: Event to load faces from.
            clustering_type: Cluster vs sweeper PYR bounds and name.
            limit: Optional max rows (batch size). ``None`` loads all matches.
            exclude_ids: Face IDs already tried in this pass (prevents sweeper
                leftovers from being loaded forever).

        Returns:
            Mapping of embedding UUID string to L2-ready primary embedding.
        """
        stmt = self._unclustered_statement(event_id, clustering_type)
        if exclude_ids:
            stmt = stmt.where(FaceEmbedding.id.notin_(list(exclude_ids)))
        stmt = stmt.order_by(FaceEmbedding.id)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._db.execute(stmt)
        embeddings: dict[str, np.ndarray] = {}
        for row in result.scalars().all():
            embeddings[str(row.id)] = as_float32_vector(row.embedding)
        return embeddings

    async def apply_clustering_result(self, event_id: uuid.UUID, result: ClusteringResult) -> None:
        """Write one clustering batch inside a single database transaction.

        Order matters for merges: members are reassigned to the surviving
        cluster before absorbed rows are deleted (``cluster_id`` is
        ``ON DELETE SET NULL``).

        Args:
            event_id: Event the result belongs to.
            result: Output of ``IncrementalClusterer.cluster``.

        Raises:
            ClusterPersistenceError: If the write fails; the transaction is rolled back.
        """
        try:
            await self._persistence.write_result(event_id, result)
            await self._db.commit()
        except ClusterPersistenceError:
            await self._db.rollback()
            raise
        except Exception as exc:
            await self._db.rollback()
            raise ClusterPersistenceError(str(event_id), str(exc)) from exc

    async def run_clustering_pass(
        self,
        event_id: uuid.UUID,
        clustering_type: ClusteringTypeConfig,
    ) -> ClusteringResult:
        """Run batched clustering for one event under a Redis lock.

        Each unclustered face is attempted at most once per pass so sweeper
        leftovers do not loop forever. The lock TTL is refreshed after every
        batch so 10–20k photo events can finish without the key expiring.

        Args:
            event_id: Event to cluster.
            clustering_type: Cluster or sweeper configuration.

        Returns:
            Combined ``ClusteringResult`` across all batches.

        Raises:
            ClusteringLockError: If Redis is missing.
            ClusteringLockBusyError: If the event lock cannot be acquired.
            ClusterPersistenceError: If a batch cannot be persisted.
        """
        lock = await self._acquire_event_lock(event_id)
        combined = ClusteringResult.empty()
        attempted_ids: set[uuid.UUID] = set()
        try:
            while True:
                existing = await self.load_event_clusters(event_id)
                unclustered = await self.load_unclustered_embeddings(
                    event_id,
                    clustering_type,
                    limit=self._config.clustering_batch_size,
                    exclude_ids=attempted_ids,
                )
                if not unclustered:
                    break

                attempted_ids.update(uuid.UUID(crop_id) for crop_id in unclustered)
                batch_result = self._clusterer.cluster(
                    ClusteringInput(
                        new_embeddings=unclustered,
                        existing_clusters=existing,
                        clustering_type=clustering_type,
                    )
                )
                await self.apply_clustering_result(event_id, batch_result)
                merge_clustering_results(combined, batch_result)
                await lock.extend()
        finally:
            await lock.release()

        logger.info(
            "clustering_pass_complete",
            event_id=str(event_id),
            clustering_type=clustering_type.name,
            new_clusters=len(combined.new_clusters),
            expanded_clusters=len(combined.expanded_clusters),
            merged_clusters=len(combined.merged_clusters),
            unassigned=len(combined.unassigned_crop_ids),
        )
        return combined

    def _unclustered_statement(
        self,
        event_id: uuid.UUID,
        clustering_type: ClusteringTypeConfig,
    ) -> Select[tuple[FaceEmbedding]]:
        """Build the filtered SELECT for unclustered quality-passed faces."""
        abs_yaw = func.abs(FaceEmbedding.yaw)
        abs_pitch = func.abs(FaceEmbedding.pitch)
        abs_roll = func.abs(FaceEmbedding.roll)
        min_deg, max_deg = clustering_type.pyr_range

        has_angles = and_(
            FaceEmbedding.yaw.is_not(None),
            FaceEmbedding.pitch.is_not(None),
            FaceEmbedding.roll.is_not(None),
        )
        filters = [
            FaceEmbedding.event_id == event_id,
            FaceEmbedding.cluster_id.is_(None),
            FaceEmbedding.quality_passed.is_(True),
            has_angles,
        ]
        if clustering_type.name == _SWEEPER_PASS_NAME:
            filters.append(and_(abs_yaw <= max_deg, abs_pitch <= max_deg, abs_roll <= max_deg))
            filters.append(or_(abs_yaw >= min_deg, abs_pitch >= min_deg, abs_roll >= min_deg))
        else:
            filters.append(
                and_(
                    abs_yaw >= min_deg,
                    abs_yaw < max_deg,
                    abs_pitch >= min_deg,
                    abs_pitch < max_deg,
                    abs_roll >= min_deg,
                    abs_roll < max_deg,
                )
            )
        return select(FaceEmbedding).where(*filters)

    async def _acquire_event_lock(self, event_id: uuid.UUID) -> EventClusteringLock:
        """Acquire the per-event clustering lock with exponential backoff."""
        if self._redis is None:
            raise ClusteringLockError(f"Redis client is required to cluster event {event_id}.")

        lock = EventClusteringLock(
            self._redis,
            event_id,
            ttl_seconds=self._config.clustering_lock_ttl_seconds,
        )
        delay = self._config.clustering_lock_retry_base_delay_seconds
        attempts = self._config.clustering_lock_retry_attempts
        for attempt in range(1, attempts + 1):
            if await lock.acquire():
                return lock
            logger.info(
                "clustering_lock_retry",
                event_id=str(event_id),
                attempt=attempt,
                delay_seconds=delay,
            )
            if attempt < attempts:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 8.0)

        raise ClusteringLockBusyError(str(event_id))
