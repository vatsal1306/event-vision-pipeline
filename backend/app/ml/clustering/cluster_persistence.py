"""Write clustering results to ``face_clusters`` / ``face_embeddings``."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.clustering.types import (
    ClusteringResult,
    ExpandedCluster,
    MergedCluster,
    NewCluster,
)
from app.ml.clustering.vector_utils import (
    affected_cluster_ids,
    as_float32_vector,
    as_uuid,
    as_uuids,
    as_vector_list,
    mean_l2_normalized,
)
from app.models.face_cluster import FaceCluster
from app.models.face_embedding import FaceEmbedding


class ClusterPersistence:
    """Apply new, expanded, and merged cluster rows on a session."""

    def __init__(self, db: AsyncSession) -> None:
        """Bind writer to an async SQLAlchemy session.

        Args:
            db: Session used for inserts, updates, and deletes.
        """
        self._db = db

    async def write_result(self, event_id: uuid.UUID, result: ClusteringResult) -> None:
        """Persist one batch without committing.

        Args:
            event_id: Event the result belongs to.
            result: Output of ``IncrementalClusterer.cluster``.
        """
        await self.insert_new_clusters(event_id, result.new_clusters)
        await self.apply_expanded_clusters(event_id, result.expanded_clusters)
        await self.apply_merged_clusters(event_id, result.merged_clusters)
        await self.refresh_secondary_centroids(event_id, result)

    async def insert_new_clusters(
        self, event_id: uuid.UUID, new_clusters: Sequence[NewCluster]
    ) -> None:
        """Insert newly discovered clusters and assign their members."""
        for cluster in new_clusters:
            cluster_id = as_uuid(cluster.cluster_id)
            self._db.add(
                FaceCluster(
                    id=cluster_id,
                    event_id=event_id,
                    centroid=as_vector_list(cluster.centroid),
                    cluster_size=cluster.size,
                    pyr_size=0,
                )
            )
            member_ids = as_uuids(cluster.crop_ids)
            if member_ids:
                await self._db.execute(
                    update(FaceEmbedding)
                    .where(
                        FaceEmbedding.event_id == event_id,
                        FaceEmbedding.id.in_(member_ids),
                    )
                    .values(cluster_id=cluster_id)
                )
        if new_clusters:
            await self._db.flush()

    async def apply_expanded_clusters(
        self, event_id: uuid.UUID, expanded_clusters: Sequence[ExpandedCluster]
    ) -> None:
        """Attach new members and update centroid / PYR fields."""
        now = datetime.now(timezone.utc)
        for expanded in expanded_clusters:
            cluster_id = as_uuid(expanded.cluster_id)
            member_ids = as_uuids(expanded.new_crop_ids)
            if member_ids:
                await self._db.execute(
                    update(FaceEmbedding)
                    .where(
                        FaceEmbedding.event_id == event_id,
                        FaceEmbedding.id.in_(member_ids),
                    )
                    .values(cluster_id=cluster_id)
                )

            values: dict[str, object] = {"updated_at": now}
            if expanded.new_centroid is not None:
                values["centroid"] = as_vector_list(expanded.new_centroid)
            if expanded.new_size is not None:
                values["cluster_size"] = expanded.new_size
            if expanded.new_pyr_centroid is not None:
                values["pyr_centroid"] = as_vector_list(expanded.new_pyr_centroid)
            if expanded.new_pyr_size is not None:
                values["pyr_size"] = expanded.new_pyr_size

            await self._db.execute(
                update(FaceCluster)
                .where(FaceCluster.id == cluster_id, FaceCluster.event_id == event_id)
                .values(**values)
            )

    async def apply_merged_clusters(
        self, event_id: uuid.UUID, merged_clusters: Sequence[MergedCluster]
    ) -> None:
        """Keep the largest survivor, reassign members, delete absorbed rows."""
        now = datetime.now(timezone.utc)
        for merged in merged_clusters:
            survivor_id = as_uuid(merged.surviving_cluster_id)
            absorbed_ids = as_uuids(merged.absorbed_cluster_ids)
            member_ids = as_uuids(merged.all_crop_ids)

            pyr_centroid: list[float] | None = None
            pyr_size = 0
            if absorbed_ids:
                pyr_centroid, pyr_size = await self.merged_pyr_state(survivor_id, absorbed_ids)
                await self._db.execute(
                    update(FaceEmbedding)
                    .where(
                        FaceEmbedding.event_id == event_id,
                        FaceEmbedding.cluster_id.in_(absorbed_ids),
                    )
                    .values(cluster_id=survivor_id)
                )
                await self._db.execute(
                    delete(FaceCluster).where(
                        FaceCluster.event_id == event_id,
                        FaceCluster.id.in_(absorbed_ids),
                    )
                )

            if member_ids:
                await self._db.execute(
                    update(FaceEmbedding)
                    .where(
                        FaceEmbedding.event_id == event_id,
                        FaceEmbedding.id.in_(member_ids),
                    )
                    .values(cluster_id=survivor_id)
                )

            values: dict[str, object] = {
                "centroid": as_vector_list(merged.new_centroid),
                "cluster_size": merged.new_size,
                "updated_at": now,
            }
            if absorbed_ids:
                values["pyr_centroid"] = pyr_centroid
                values["pyr_size"] = pyr_size
            await self._db.execute(
                update(FaceCluster)
                .where(FaceCluster.id == survivor_id, FaceCluster.event_id == event_id)
                .values(**values)
            )

    async def merged_pyr_state(
        self,
        survivor_id: uuid.UUID,
        absorbed_ids: Sequence[uuid.UUID],
    ) -> tuple[list[float] | None, int]:
        """Weighted-merge PYR centroids of survivor and absorbed clusters."""
        result = await self._db.execute(
            select(FaceCluster).where(FaceCluster.id.in_([survivor_id, *absorbed_ids]))
        )
        weighted_sum: np.ndarray | None = None
        total = 0
        for cluster in result.scalars().all():
            if cluster.pyr_centroid is None or cluster.pyr_size <= 0:
                continue
            vector = as_float32_vector(cluster.pyr_centroid) * float(cluster.pyr_size)
            weighted_sum = vector if weighted_sum is None else weighted_sum + vector
            total += cluster.pyr_size
        if weighted_sum is None or total <= 0:
            return None, 0
        centroid = weighted_sum / float(total)
        norm = float(np.linalg.norm(centroid))
        if norm == 0.0:
            return None, 0
        return (centroid / norm).astype(np.float32).tolist(), total

    async def refresh_secondary_centroids(
        self, event_id: uuid.UUID, result: ClusteringResult
    ) -> None:
        """Recompute AdaFace centroids from members that have a secondary vector."""
        cluster_ids = affected_cluster_ids(result)
        if not cluster_ids:
            return
        rows = await self._db.execute(
            select(FaceEmbedding.cluster_id, FaceEmbedding.secondary_embedding).where(
                FaceEmbedding.event_id == event_id,
                FaceEmbedding.cluster_id.in_(cluster_ids),
                FaceEmbedding.secondary_embedding.is_not(None),
            )
        )
        grouped: dict[uuid.UUID, list[np.ndarray]] = {}
        for cluster_id, secondary in rows.all():
            if cluster_id is None or secondary is None:
                continue
            grouped.setdefault(cluster_id, []).append(as_float32_vector(secondary))

        now = datetime.now(timezone.utc)
        for cluster_id in cluster_ids:
            vectors = grouped.get(cluster_id, [])
            centroid = mean_l2_normalized(vectors)
            await self._db.execute(
                update(FaceCluster)
                .where(FaceCluster.id == cluster_id, FaceCluster.event_id == event_id)
                .values(secondary_centroid=centroid, updated_at=now)
            )
