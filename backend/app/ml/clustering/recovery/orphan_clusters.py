"""Merge tiny clusters into larger same-person clusters."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING
from uuid import UUID

import numpy as np
import structlog

from app.ml.clustering.recovery.similarity import (
    dual_centroid_similarity_matrix,
    match_type_name,
    weighted_l2_centroid,
)
from app.ml.clustering.recovery.types import ClusterMergeAssignment, MergeResult
from app.ml.clustering.types import ClusteringResult, ExistingCluster, MergedCluster

if TYPE_CHECKING:
    from app.ml.clustering.cluster_manager import ClusterManager

logger = structlog.get_logger(__name__)


class OrphanClusterMerge:
    """Absorb clusters at or below ``orphan_cluster_max_size`` into larger ones."""

    def __init__(self, cluster_manager: ClusterManager) -> None:
        """Bind merge logic to a cluster manager.

        Args:
            cluster_manager: Persistence bridge for the current DB session.
        """
        self._manager = cluster_manager

    async def merge(self, event_id: UUID) -> MergeResult:
        """Merge small clusters into established clusters when similar enough.

        Established means ``cluster_size > max_orphan_size``. Dual-centroid
        comparison takes the max of centroid-vs-centroid, centroid-vs-PYR, and
        PYR-vs-PYR.

        Args:
            event_id: Event whose clusters should be considered.

        Returns:
            Merge counts and per-orphan details.
        """
        config = self._manager.ml_config
        if not config.orphan_recovery_enabled:
            logger.info("orphan_cluster_merge_skipped", event_id=str(event_id))
            return MergeResult(merged_count=0, remaining_orphans=0)

        clusters = await self._manager.load_event_clusters(event_id)
        max_orphan_size = config.orphan_cluster_max_size
        threshold = config.orphan_cluster_merge_threshold
        orphans, established = partition_orphan_clusters(clusters, max_orphan_size)

        if not orphans or not established:
            remaining = len(orphans)
            logger.info(
                "orphan_cluster_merge_nothing_to_do",
                event_id=str(event_id),
                orphan_count=remaining,
                established_count=len(established),
            )
            return MergeResult(merged_count=0, remaining_orphans=remaining)

        assignments = match_orphan_clusters(orphans, established, threshold)
        if assignments:
            result = merges_to_clustering_result(orphans, established, assignments)
            await self._manager.apply_clustering_result(event_id, result)

        remaining = await self._manager.count_orphan_clusters(event_id, max_orphan_size)
        logger.info(
            "orphan_cluster_merge_complete",
            event_id=str(event_id),
            merged_count=len(assignments),
            remaining_orphans=remaining,
        )
        return MergeResult(
            merged_count=len(assignments),
            remaining_orphans=remaining,
            details=[
                {
                    "orphan_id": item.orphan_id,
                    "target_id": item.target_id,
                    "similarity": item.similarity,
                    "match_type": item.match_type,
                }
                for item in assignments
            ],
        )


def partition_orphan_clusters(
    clusters: dict[str, ExistingCluster],
    max_orphan_size: int,
) -> tuple[dict[str, ExistingCluster], dict[str, ExistingCluster]]:
    """Split clusters into small (orphan) and established groups.

    Args:
        clusters: All clusters for an event.
        max_orphan_size: Inclusive size cap for orphan clusters.

    Returns:
        ``(orphans, established)`` dictionaries keyed by cluster id.
    """
    orphans: dict[str, ExistingCluster] = {}
    established: dict[str, ExistingCluster] = {}
    for cluster_id, cluster in clusters.items():
        if cluster.size <= max_orphan_size:
            orphans[cluster_id] = cluster
        else:
            established[cluster_id] = cluster
    return orphans, established


def match_orphan_clusters(
    orphans: dict[str, ExistingCluster],
    established: dict[str, ExistingCluster],
    threshold: float,
) -> list[ClusterMergeAssignment]:
    """Pick the best established cluster for each orphan above ``threshold``.

    Args:
        orphans: Small clusters.
        established: Clusters larger than the orphan size cap.
        threshold: Inclusive cosine similarity gate.

    Returns:
        One assignment per orphan that matched, sorted by orphan id.
    """
    if not orphans or not established:
        return []

    orphan_ids = sorted(orphans)
    established_ids = sorted(established)
    orphan_centroids = np.stack([orphans[item].centroid for item in orphan_ids])
    established_centroids = np.stack([established[item].centroid for item in established_ids])

    orphan_pyr_mask = np.array(
        [orphans[item].pyr_centroid is not None for item in orphan_ids],
        dtype=bool,
    )
    established_pyr_mask = np.array(
        [established[item].pyr_centroid is not None for item in established_ids],
        dtype=bool,
    )
    orphan_pyr = _stack_pyr_or_zeros(orphans, orphan_ids)
    established_pyr = _stack_pyr_or_zeros(established, established_ids)

    similarities, match_codes = dual_centroid_similarity_matrix(
        orphan_centroids,
        orphan_pyr,
        orphan_pyr_mask,
        established_centroids,
        established_pyr,
        established_pyr_mask,
    )

    assignments: list[ClusterMergeAssignment] = []
    for row_index, orphan_id in enumerate(orphan_ids):
        best_idx = int(np.argmax(similarities[row_index]))
        best_similarity = float(similarities[row_index, best_idx])
        if best_similarity >= threshold:
            assignments.append(
                ClusterMergeAssignment(
                    orphan_id=orphan_id,
                    target_id=established_ids[best_idx],
                    similarity=best_similarity,
                    match_type=match_type_name(int(match_codes[row_index, best_idx])),
                )
            )
    return assignments


def merges_to_clustering_result(
    orphans: dict[str, ExistingCluster],
    established: dict[str, ExistingCluster],
    assignments: list[ClusterMergeAssignment],
) -> ClusteringResult:
    """Group orphan merges by target and build persistable merge records.

    Args:
        orphans: Small-cluster snapshots.
        established: Target snapshots (pre-merge).
        assignments: Matches from ``match_orphan_clusters``.

    Returns:
        ``ClusteringResult`` with one ``MergedCluster`` per target.
    """
    grouped: dict[str, list[ClusterMergeAssignment]] = defaultdict(list)
    for assignment in assignments:
        grouped[assignment.target_id].append(assignment)

    merged: list[MergedCluster] = []
    for target_id, group in grouped.items():
        target = established[target_id]
        absorbed = [orphans[item.orphan_id] for item in group]
        members = [target, *absorbed]
        new_centroid = weighted_l2_centroid(
            [cluster.centroid for cluster in members],
            [cluster.size for cluster in members],
        )
        merged.append(
            MergedCluster(
                surviving_cluster_id=target_id,
                absorbed_cluster_ids=[item.orphan_id for item in group],
                new_centroid=new_centroid,
                all_crop_ids=[],
                new_size=target.size + sum(cluster.size for cluster in absorbed),
            )
        )
    return ClusteringResult(merged_clusters=merged)


def _stack_pyr_or_zeros(
    clusters: dict[str, ExistingCluster],
    ordered_ids: list[str],
) -> np.ndarray | None:
    """Stack PYR centroids, substituting zeros where PYR is missing."""
    if not any(clusters[item].pyr_centroid is not None for item in ordered_ids):
        return None
    dim = int(clusters[ordered_ids[0]].centroid.shape[0])
    rows: list[np.ndarray] = []
    for cluster_id in ordered_ids:
        pyr = clusters[cluster_id].pyr_centroid
        if pyr is None:
            rows.append(np.zeros(dim, dtype=np.float32))
        else:
            rows.append(np.asarray(pyr, dtype=np.float32).reshape(-1))
    return np.stack(rows)
