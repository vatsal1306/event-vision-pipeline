"""Incremental DBSCAN + agglomerative face clustering (PicSee / pix-workers port)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import structlog

from app.ml.clustering.types import (
    EMBEDDING_DIM,
    ClusteringInput,
    ClusteringResult,
    ClusteringTypeConfig,
    ExistingCluster,
    ExpandedCluster,
    MergedCluster,
    NewCluster,
    new_cluster_id,
)
from app.ml.config import MLConfig, get_ml_config

logger = structlog.get_logger(__name__)

_CENTROID_PREFIX = "centroid_"


@dataclass(frozen=True)
class _MemberRecord:
    """One row in the combined embedding matrix."""

    embedding_id: str
    vector: np.ndarray
    is_centroid: bool
    cluster_id: str | None
    weight: int


class IncrementalClusterer:
    """Pure numpy/sklearn incremental clustering with centroid injection.

    Takes new face embeddings plus existing cluster centroids, runs DBSCAN then
    agglomerative merging, and classifies outcomes as new, expanded, or merged
    clusters. Sweeper passes may only expand existing clusters.
    """

    def __init__(self, ml_config: MLConfig | None = None) -> None:
        """Initialise clustering thresholds from ``MLConfig``.

        Args:
            ml_config: Optional configuration override. Defaults to cached
                ``get_ml_config()``.
        """
        self._config = ml_config or get_ml_config()

    @property
    def dbscan_eps(self) -> float:
        """Cosine distance threshold for DBSCAN."""
        return self._config.dbscan_eps

    @property
    def dbscan_min_samples(self) -> int:
        """Minimum samples per DBSCAN micro-cluster."""
        return self._config.dbscan_min_samples

    @property
    def agglo_threshold(self) -> float:
        """Cosine distance threshold for agglomerative merging."""
        return self._config.agglo_threshold

    def cluster(self, clustering_input: ClusteringInput) -> ClusteringResult:
        """Run incremental clustering for one batch of embeddings.

        Args:
            clustering_input: New embeddings, existing clusters, and pass type.

        Returns:
            ClusteringResult describing new, expanded, merged, and unassigned
            crops. Returns an empty result when ``new_embeddings`` is empty.

        Raises:
            ValueError: If embedding vectors are malformed or inconsistent.
        """
        if not clustering_input.new_embeddings:
            return ClusteringResult.empty()

        members = self._build_member_records(
            clustering_input.new_embeddings,
            clustering_input.existing_clusters,
        )
        if not members:
            return ClusteringResult.empty()

        vectors = np.stack([member.vector for member in members], axis=0)
        self._validate_vectors(vectors)

        dbscan_labels = self._perform_dbscan(vectors)
        group_centroids, group_labels = self._compute_group_centroids(vectors, dbscan_labels)
        agglo_labels = self._perform_agglomerative(group_centroids, group_labels)

        dbscan_to_agglo = {db_label: agglo_labels[idx] for idx, db_label in enumerate(group_labels)}
        member_agglo_labels = np.array(
            [dbscan_to_agglo.get(label, -1) for label in dbscan_labels],
            dtype=int,
        )

        return self._build_result(
            members=members,
            dbscan_labels=dbscan_labels,
            member_agglo_labels=member_agglo_labels,
            existing_clusters=clustering_input.existing_clusters,
            clustering_type=clustering_input.clustering_type,
        )

    def _build_member_records(
        self,
        new_embeddings: dict[str, np.ndarray],
        existing_clusters: dict[str, ExistingCluster],
    ) -> list[_MemberRecord]:
        """Merge existing centroids with new crop embeddings."""
        members: list[_MemberRecord] = []

        for cluster_id, cluster in existing_clusters.items():
            centroid_id = f"{_CENTROID_PREFIX}{cluster_id}"
            members.append(
                _MemberRecord(
                    embedding_id=centroid_id,
                    vector=np.asarray(cluster.centroid, dtype=np.float32),
                    is_centroid=True,
                    cluster_id=cluster_id,
                    weight=max(cluster.size, 1),
                )
            )

        for crop_id, embedding in new_embeddings.items():
            members.append(
                _MemberRecord(
                    embedding_id=crop_id,
                    vector=np.asarray(embedding, dtype=np.float32),
                    is_centroid=False,
                    cluster_id=None,
                    weight=1,
                )
            )

        return members

    def _validate_vectors(self, vectors: np.ndarray) -> None:
        """Ensure the embedding matrix has the expected shape."""
        if vectors.ndim != 2:
            raise ValueError("Embeddings must form a 2D matrix.")
        if vectors.shape[1] != EMBEDDING_DIM:
            raise ValueError(
                f"Expected {EMBEDDING_DIM}-dimensional embeddings, "
                f"got dimension {vectors.shape[1]}."
            )

    def _perform_dbscan(self, vectors: np.ndarray) -> np.ndarray:
        """Run DBSCAN with cosine distance on the combined matrix."""
        from sklearn.cluster import DBSCAN

        dbscan = DBSCAN(
            metric="cosine",
            eps=self.dbscan_eps,
            min_samples=self.dbscan_min_samples,
            algorithm="brute",
        )
        labels: np.ndarray = np.asarray(dbscan.fit_predict(vectors), dtype=np.int64)
        return labels

    def _compute_group_centroids(
        self,
        vectors: np.ndarray,
        labels: np.ndarray,
    ) -> tuple[np.ndarray, list[int]]:
        """Compute L2-normalised centroids for each DBSCAN group."""
        unique_labels = sorted({int(label) for label in labels if label >= 0})
        centroids: list[np.ndarray] = []
        for label in unique_labels:
            group_vectors = vectors[labels == label]
            centroid = group_vectors.mean(axis=0)
            centroids.append(self._l2_normalize(centroid))

        if not centroids:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32), []

        return np.stack(centroids, axis=0), unique_labels

    def _perform_agglomerative(
        self,
        group_centroids: np.ndarray,
        group_labels: list[int],
    ) -> np.ndarray:
        """Merge DBSCAN micro-clusters via agglomerative clustering."""
        if len(group_labels) <= 1:
            if not group_labels:
                return np.array([], dtype=np.int64)
            return np.array([0], dtype=np.int64)

        from sklearn.cluster import AgglomerativeClustering

        agglo = AgglomerativeClustering(
            n_clusters=None,
            metric="cosine",
            linkage="average",
            distance_threshold=self.agglo_threshold,
        )
        labels: np.ndarray = np.asarray(agglo.fit_predict(group_centroids), dtype=np.int64)
        return labels

    def _build_result(
        self,
        members: list[_MemberRecord],
        dbscan_labels: np.ndarray,
        member_agglo_labels: np.ndarray,
        existing_clusters: dict[str, ExistingCluster],
        clustering_type: ClusteringTypeConfig,
    ) -> ClusteringResult:
        """Classify agglomerative groups and apply sweeper restrictions."""
        result = ClusteringResult()
        unassigned: set[str] = set()

        for member, dbscan_label in zip(members, dbscan_labels, strict=True):
            if not member.is_centroid and dbscan_label < 0:
                unassigned.add(member.embedding_id)

        for agglo_label in sorted(set(member_agglo_labels)):
            if agglo_label < 0:
                continue

            group_members = [
                member
                for member, label in zip(members, member_agglo_labels, strict=True)
                if label == agglo_label
            ]
            centroid_members = [member for member in group_members if member.is_centroid]
            crop_members = [member for member in group_members if not member.is_centroid]

            if not crop_members and len(centroid_members) <= 1:
                continue

            if not centroid_members:
                self._handle_new_cluster(
                    result=result,
                    crop_members=crop_members,
                    clustering_type=clustering_type,
                    unassigned=unassigned,
                )
            elif len(centroid_members) == 1:
                self._handle_expanded_cluster(
                    result=result,
                    centroid_member=centroid_members[0],
                    crop_members=crop_members,
                    group_members=group_members,
                    existing_clusters=existing_clusters,
                    clustering_type=clustering_type,
                    unassigned=unassigned,
                )
            else:
                self._handle_merged_cluster(
                    result=result,
                    centroid_members=centroid_members,
                    crop_members=crop_members,
                    group_members=group_members,
                    existing_clusters=existing_clusters,
                    clustering_type=clustering_type,
                    unassigned=unassigned,
                )

        result.unassigned_crop_ids = sorted(unassigned)
        return result

    def _handle_new_cluster(
        self,
        result: ClusteringResult,
        crop_members: list[_MemberRecord],
        clustering_type: ClusteringTypeConfig,
        unassigned: set[str],
    ) -> None:
        """Create a new cluster or mark crops unassigned for sweeper."""
        crop_ids = [member.embedding_id for member in crop_members]
        if not clustering_type.creates_new_clusters:
            unassigned.update(crop_ids)
            return

        centroid = self._weighted_centroid(
            vectors=[member.vector for member in crop_members],
            weights=[1] * len(crop_members),
        )
        result.new_clusters.append(
            NewCluster(
                cluster_id=new_cluster_id(),
                centroid=centroid,
                crop_ids=crop_ids,
                size=len(crop_ids),
            )
        )

    def _handle_expanded_cluster(
        self,
        result: ClusteringResult,
        centroid_member: _MemberRecord,
        crop_members: list[_MemberRecord],
        group_members: list[_MemberRecord],
        existing_clusters: dict[str, ExistingCluster],
        clustering_type: ClusteringTypeConfig,
        unassigned: set[str],
    ) -> None:
        """Expand an existing cluster with new crops."""
        cluster_id = centroid_member.cluster_id
        if cluster_id is None or cluster_id not in existing_clusters:
            logger.warning(
                "clustering.expand_missing_cluster",
                cluster_id=cluster_id,
            )
            unassigned.update(member.embedding_id for member in crop_members)
            return

        if not clustering_type.expands_existing:
            unassigned.update(member.embedding_id for member in crop_members)
            return

        crop_ids = [member.embedding_id for member in crop_members]
        if not crop_ids:
            return

        existing = existing_clusters[cluster_id]

        if clustering_type.name == "sweeper":
            new_pyr_centroid, new_pyr_size = self._update_pyr_centroid(
                existing=existing,
                new_vectors=[member.vector for member in crop_members],
            )
            result.expanded_clusters.append(
                ExpandedCluster(
                    cluster_id=cluster_id,
                    new_crop_ids=crop_ids,
                    new_pyr_centroid=new_pyr_centroid,
                    new_pyr_size=new_pyr_size,
                )
            )
            return

        new_centroid = self._weighted_centroid_from_members(group_members)
        result.expanded_clusters.append(
            ExpandedCluster(
                cluster_id=cluster_id,
                new_crop_ids=crop_ids,
                new_centroid=new_centroid,
                new_size=existing.size + len(crop_ids),
            )
        )

    def _handle_merged_cluster(
        self,
        result: ClusteringResult,
        centroid_members: list[_MemberRecord],
        crop_members: list[_MemberRecord],
        group_members: list[_MemberRecord],
        existing_clusters: dict[str, ExistingCluster],
        clustering_type: ClusteringTypeConfig,
        unassigned: set[str],
    ) -> None:
        """Merge multiple existing clusters or block the merge for sweeper."""
        crop_ids = [member.embedding_id for member in crop_members]

        if not clustering_type.allows_merge_clusters:
            unassigned.update(crop_ids)
            return

        surviving_id = self._select_surviving_cluster(centroid_members, existing_clusters)
        absorbed_ids = sorted(
            member.cluster_id
            for member in centroid_members
            if member.cluster_id is not None and member.cluster_id != surviving_id
        )

        surviving_cluster = existing_clusters[surviving_id]
        all_crop_ids = list(surviving_cluster.crop_ids)
        for cluster_id in absorbed_ids:
            all_crop_ids.extend(existing_clusters[cluster_id].crop_ids)
        all_crop_ids.extend(crop_ids)

        new_size = sum(
            existing_clusters[member.cluster_id].size
            for member in centroid_members
            if member.cluster_id is not None
        ) + len(crop_ids)

        result.merged_clusters.append(
            MergedCluster(
                surviving_cluster_id=surviving_id,
                absorbed_cluster_ids=absorbed_ids,
                new_centroid=self._weighted_centroid_from_members(group_members),
                all_crop_ids=all_crop_ids,
                new_size=new_size,
            )
        )

    def _select_surviving_cluster(
        self,
        centroid_members: list[_MemberRecord],
        existing_clusters: dict[str, ExistingCluster],
    ) -> str:
        """Pick the largest cluster as merge survivor; tie-break on cluster id."""
        candidates: list[tuple[str, int]] = []
        for member in centroid_members:
            if member.cluster_id is None:
                continue
            cluster = existing_clusters[member.cluster_id]
            candidates.append((member.cluster_id, cluster.size))

        max_size = max(size for _, size in candidates)
        tied = [cluster_id for cluster_id, size in candidates if size == max_size]
        return min(tied)

    def _weighted_centroid_from_members(self, members: list[_MemberRecord]) -> np.ndarray:
        """Compute a size-weighted centroid for a mixed member group."""
        return self._weighted_centroid(
            vectors=[member.vector for member in members],
            weights=[member.weight for member in members],
        )

    def _weighted_centroid(
        self,
        vectors: list[np.ndarray],
        weights: list[int],
    ) -> np.ndarray:
        """Compute L2-normalised weighted mean of embedding vectors."""
        if not vectors:
            raise ValueError("Cannot compute centroid from an empty vector list.")

        weighted_sum = np.zeros_like(vectors[0], dtype=np.float64)
        total_weight = 0
        for vector, weight in zip(vectors, weights, strict=True):
            weighted_sum += np.asarray(vector, dtype=np.float64) * weight
            total_weight += weight

        if total_weight <= 0:
            raise ValueError("Total weight must be positive for centroid update.")

        centroid = weighted_sum / total_weight
        return self._l2_normalize(centroid.astype(np.float32))

    def _update_pyr_centroid(
        self,
        existing: ExistingCluster,
        new_vectors: list[np.ndarray],
    ) -> tuple[np.ndarray, int]:
        """Update the high-angle centroid without touching the main centroid."""
        if existing.pyr_centroid is None:
            centroid = self._weighted_centroid(new_vectors, [1] * len(new_vectors))
            return centroid, len(new_vectors)

        old_size = existing.pyr_size if existing.pyr_size > 0 else 1
        vectors = [existing.pyr_centroid, *new_vectors]
        weights = [old_size, *[1] * len(new_vectors)]
        centroid = self._weighted_centroid(vectors, weights)
        return centroid, old_size + len(new_vectors)

    @staticmethod
    def _l2_normalize(vector: np.ndarray) -> np.ndarray:
        """Return the L2-normalised copy of a vector."""
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector.astype(np.float32)
        normalized: np.ndarray = (vector / norm).astype(np.float32)
        return normalized
