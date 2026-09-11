"""Recover unassigned high-angle faces by matching PYR centroids."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import numpy as np
import structlog

from app.ml.clustering.recovery.similarity import pairwise_cosine_similarity, update_pyr_centroid
from app.ml.clustering.recovery.types import CropAssignment, RecoveryResult
from app.ml.clustering.types import ClusteringResult, ExistingCluster, ExpandedCluster

if TYPE_CHECKING:
    from app.ml.clustering.cluster_manager import ClusterManager

logger = structlog.get_logger(__name__)


class OrphanCropRecovery:
    """Assign sweeper leftovers to clusters that already have a PYR centroid."""

    def __init__(self, cluster_manager: ClusterManager) -> None:
        """Bind recovery to a cluster manager for loads and writes.

        Args:
            cluster_manager: Persistence bridge for the current DB session.
        """
        self._manager = cluster_manager

    async def recover(self, event_id: UUID) -> RecoveryResult:
        """Match unclustered sweeper-range faces to PYR centroids.

        Only clusters that already have ``pyr_centroid`` are candidates (pix-workers
        behaviour). Unmatched faces stay ``cluster_id = NULL``.

        Args:
            event_id: Event whose leftover high-angle faces should be recovered.

        Returns:
            Counts and per-crop assignment details for this pass.
        """
        config = self._manager.ml_config
        if not config.orphan_recovery_enabled:
            logger.info("orphan_crop_recovery_skipped", event_id=str(event_id))
            return RecoveryResult(recovered=0, still_orphaned=0)

        threshold = config.orphan_crop_similarity_threshold
        batch_size = config.clustering_batch_size
        details: list[dict[str, object]] = []
        recovered = 0
        attempted_ids: set[UUID] = set()

        while True:
            orphans = await self._manager.load_orphan_crops(
                event_id,
                limit=batch_size,
                exclude_ids=attempted_ids,
            )
            if not orphans:
                break

            attempted_ids.update(UUID(crop_id) for crop_id in orphans)
            pyr_clusters = await self._manager.load_pyr_clusters(event_id)
            if not pyr_clusters:
                logger.info(
                    "orphan_crop_recovery_no_pyr_clusters",
                    event_id=str(event_id),
                    orphan_count=len(orphans),
                )
                break

            assignments = match_orphan_crops(orphans, pyr_clusters, threshold)
            if assignments:
                await self._manager.apply_orphan_crop_assignments(
                    event_id,
                    orphans,
                    pyr_clusters,
                    assignments,
                )
                recovered += len(assignments)
                details.extend(
                    {
                        "crop_id": item.crop_id,
                        "assigned_cluster_id": item.cluster_id,
                        "similarity": item.similarity,
                    }
                    for item in assignments
                )

        still_orphaned = await self._manager.count_orphan_crops(event_id)
        logger.info(
            "orphan_crop_recovery_complete",
            event_id=str(event_id),
            recovered=recovered,
            still_orphaned=still_orphaned,
        )
        return RecoveryResult(
            recovered=recovered,
            still_orphaned=still_orphaned,
            details=details,
        )


def match_orphan_crops(
    orphans: dict[str, np.ndarray],
    pyr_clusters: dict[str, ExistingCluster],
    threshold: float,
) -> list[CropAssignment]:
    """Return assignments whose best PYR cosine similarity meets ``threshold``.

    Args:
        orphans: Crop id → embedding.
        pyr_clusters: Cluster id → snapshot (must include ``pyr_centroid``).
        threshold: Inclusive cosine similarity gate.

    Returns:
        One assignment per orphan that beat the threshold. Order follows
        sorted crop ids.
    """
    if not orphans or not pyr_clusters:
        return []

    crop_ids = sorted(orphans)
    valid_cluster_ids = [
        cluster_id
        for cluster_id in sorted(pyr_clusters)
        if pyr_clusters[cluster_id].pyr_centroid is not None
    ]
    if not valid_cluster_ids:
        return []
    orphan_matrix = np.stack([orphans[crop_id] for crop_id in crop_ids])
    centroid_matrix = np.stack(
        [
            np.asarray(pyr_clusters[cluster_id].pyr_centroid, dtype=np.float32)
            for cluster_id in valid_cluster_ids
        ]
    )

    similarities = pairwise_cosine_similarity(orphan_matrix, centroid_matrix)
    assignments: list[CropAssignment] = []
    for row_index, crop_id in enumerate(crop_ids):
        best_idx = int(np.argmax(similarities[row_index]))
        best_similarity = float(similarities[row_index, best_idx])
        if best_similarity >= threshold:
            assignments.append(
                CropAssignment(
                    crop_id=crop_id,
                    cluster_id=valid_cluster_ids[best_idx],
                    similarity=best_similarity,
                )
            )
    return assignments


def assignments_to_expanded_clusters(
    orphans: dict[str, np.ndarray],
    pyr_clusters: dict[str, ExistingCluster],
    assignments: list[CropAssignment],
) -> list[ExpandedCluster]:
    """Group crop assignments and compute one PYR update per target cluster.

    Args:
        orphans: Crop embeddings used to update PYR centroids.
        pyr_clusters: Snapshots from before this batch of writes.
        assignments: Matches from ``match_orphan_crops``.

    Returns:
        ``ExpandedCluster`` rows that grow size/PYR but leave the main centroid.
    """
    grouped: dict[str, list[CropAssignment]] = {}
    for assignment in assignments:
        grouped.setdefault(assignment.cluster_id, []).append(assignment)

    expanded: list[ExpandedCluster] = []
    for cluster_id, group in grouped.items():
        existing = pyr_clusters[cluster_id]
        new_vectors = [orphans[item.crop_id] for item in group]
        new_pyr, new_pyr_size = update_pyr_centroid(existing, new_vectors)
        expanded.append(
            ExpandedCluster(
                cluster_id=cluster_id,
                new_crop_ids=[item.crop_id for item in group],
                new_centroid=None,
                new_size=existing.size + len(group),
                new_pyr_centroid=new_pyr,
                new_pyr_size=new_pyr_size,
            )
        )
    return expanded


def expanded_result_from_assignments(
    orphans: dict[str, np.ndarray],
    pyr_clusters: dict[str, ExistingCluster],
    assignments: list[CropAssignment],
) -> ClusteringResult:
    """Wrap orphan-crop assignments as a clustering persist payload.

    Args:
        orphans: Crop embeddings.
        pyr_clusters: Cluster snapshots.
        assignments: Matches to persist.

    Returns:
        Result containing only ``expanded_clusters``.
    """
    return ClusteringResult(
        expanded_clusters=assignments_to_expanded_clusters(orphans, pyr_clusters, assignments)
    )
