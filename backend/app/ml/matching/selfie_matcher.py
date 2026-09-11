"""Cosine matching of a selfie embedding against event cluster centroids."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import numpy as np
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.clustering.vector_utils import as_float32_vector
from app.ml.config import MLConfig, get_ml_config
from app.ml.matching.types import ClusterCentroid, ClusterMatch, MatchResult, MatchStatus
from app.models.face_cluster import FaceCluster

logger = structlog.get_logger(__name__)

_CONFIDENCE_HIGH = "high"
_CONFIDENCE_LOW = "low"


class SelfieMatcher:
    """Match one selfie embedding to precomputed cluster centroids."""

    def __init__(
        self,
        db: AsyncSession,
        config: MLConfig | None = None,
    ) -> None:
        """Create a matcher bound to one database session.

        Args:
            db: Async SQLAlchemy session used to load cluster centroids.
            config: Optional ML settings override.
        """
        self._db = db
        self._config = config or get_ml_config()

    async def match(
        self,
        selfie_embedding: np.ndarray,
        event_id: uuid.UUID,
        secondary_embedding: np.ndarray | None = None,
    ) -> MatchResult:
        """Compare a selfie embedding with this event's cluster centroids.

        Uses in-memory cosine similarity below ``selfie_pgvector_min_clusters``
        and a pgvector cosine-distance query at or above that count.

        Args:
            selfie_embedding: L2-normalised 512-d primary (R100) vector.
            event_id: Event whose clusters are searched.
            secondary_embedding: Optional AdaFace vector for confidence tags.

        Returns:
            ``MatchResult`` with status ``matched``, ``no_match``, or ``no_clusters``.
        """
        cluster_count = await self._count_clusters(event_id)
        if cluster_count == 0:
            return MatchResult(
                status=MatchStatus.NO_CLUSTERS,
                selfie_embedding=selfie_embedding,
            )

        use_pgvector = cluster_count >= self._config.selfie_pgvector_min_clusters
        if use_pgvector:
            clusters = await self._load_pgvector_candidates(
                event_id,
                selfie_embedding,
                secondary_embedding=secondary_embedding,
            )
        else:
            clusters = await self._load_all_centroids(event_id)

        details = rank_centroid_matches(
            selfie_embedding,
            clusters,
            threshold=self._config.selfie_match_threshold,
            max_matches=self._config.max_cluster_matches,
            secondary_embedding=secondary_embedding,
            dual_model_enabled=self._config.dual_model_enabled,
        )
        if not details:
            return MatchResult(
                status=MatchStatus.NO_MATCH,
                selfie_embedding=selfie_embedding,
            )
        return MatchResult(
            status=MatchStatus.MATCHED,
            matched_cluster_ids=[item.cluster_id for item in details],
            selfie_embedding=selfie_embedding,
            match_details=details,
        )

    async def _count_clusters(self, event_id: uuid.UUID) -> int:
        """Return how many clusters exist for the event."""
        result = await self._db.execute(
            select(func.count()).select_from(FaceCluster).where(FaceCluster.event_id == event_id)
        )
        return int(result.scalar_one())

    async def _load_all_centroids(self, event_id: uuid.UUID) -> list[ClusterCentroid]:
        """Load every centroid for exact in-memory cosine matching."""
        result = await self._db.execute(
            select(
                FaceCluster.id,
                FaceCluster.centroid,
                FaceCluster.secondary_centroid,
            ).where(FaceCluster.event_id == event_id)
        )
        return [_row_to_centroid(row) for row in result.all()]

    async def _load_pgvector_candidates(
        self,
        event_id: uuid.UUID,
        selfie_embedding: np.ndarray,
        secondary_embedding: np.ndarray | None,
    ) -> list[ClusterCentroid]:
        """Load nearest centroids via pgvector cosine distance.

        Fetches a wider candidate pool than ``max_cluster_matches`` so dual-model
        cross-validation still sees primary-only neighbours.
        """
        query_vector = as_float32_vector(selfie_embedding).tolist()
        limit = max(self._config.max_cluster_matches * 4, self._config.max_cluster_matches)
        distance = FaceCluster.centroid.cosine_distance(query_vector)
        result = await self._db.execute(
            select(
                FaceCluster.id,
                FaceCluster.centroid,
                FaceCluster.secondary_centroid,
            )
            .where(FaceCluster.event_id == event_id)
            .order_by(distance)
            .limit(limit)
        )
        clusters = [_row_to_centroid(row) for row in result.all()]
        if secondary_embedding is not None and self._config.dual_model_enabled and clusters:
            logger.debug(
                "selfie_pgvector_candidates",
                event_id=str(event_id),
                candidate_count=len(clusters),
            )
        return clusters


def rank_centroid_matches(
    selfie_embedding: np.ndarray,
    clusters: Sequence[ClusterCentroid],
    *,
    threshold: float,
    max_matches: int,
    secondary_embedding: np.ndarray | None = None,
    dual_model_enabled: bool = False,
) -> list[ClusterMatch]:
    """Rank clusters by primary cosine similarity and apply dual-model tags.

    Primary (R100) similarity decides membership. AdaFace only labels
    ``high`` vs ``low`` confidence. AdaFace-only hits are dropped.

    Args:
        selfie_embedding: L2-normalised primary query vector.
        clusters: Cluster centroid snapshots.
        threshold: Minimum cosine similarity (inclusive).
        max_matches: Maximum clusters to return.
        secondary_embedding: Optional AdaFace query vector.
        dual_model_enabled: When False, every primary match is ``high``.

    Returns:
        Up to ``max_matches`` ``ClusterMatch`` rows, best similarity first.
    """
    if not clusters or max_matches <= 0:
        return []

    query = _l2_normalize(as_float32_vector(selfie_embedding))
    centroids = np.stack([_l2_normalize(item.centroid) for item in clusters])
    similarities = centroids @ query

    primary_hits: list[tuple[int, float]] = []
    for index, similarity in enumerate(similarities):
        score = float(similarity)
        if score >= threshold:
            primary_hits.append((index, score))
    primary_hits.sort(key=lambda item: item[1], reverse=True)

    secondary_ids: set[uuid.UUID] = set()
    if dual_model_enabled and secondary_embedding is not None:
        secondary_ids = _secondary_match_ids(clusters, secondary_embedding, threshold)

    matches: list[ClusterMatch] = []
    for index, score in primary_hits:
        cluster_id = clusters[index].cluster_id
        if dual_model_enabled and secondary_embedding is not None:
            confidence = _CONFIDENCE_HIGH if cluster_id in secondary_ids else _CONFIDENCE_LOW
        else:
            confidence = _CONFIDENCE_HIGH
        matches.append(ClusterMatch(cluster_id=cluster_id, similarity=score, confidence=confidence))
        if len(matches) >= max_matches:
            break
    return matches


def cross_validate(
    primary_matches: list[ClusterMatch],
    secondary_matches: list[ClusterMatch],
) -> list[ClusterMatch]:
    """Tag primary matches as high/low using the secondary model's ID set.

    Secondary-only cluster IDs are discarded.

    Args:
        primary_matches: Clusters that passed the primary threshold.
        secondary_matches: Clusters that passed the secondary threshold.

    Returns:
        Primary matches with confidence rewritten; order preserved.
    """
    secondary_ids = {item.cluster_id for item in secondary_matches}
    return [
        ClusterMatch(
            cluster_id=item.cluster_id,
            similarity=item.similarity,
            confidence=_CONFIDENCE_HIGH if item.cluster_id in secondary_ids else _CONFIDENCE_LOW,
        )
        for item in primary_matches
    ]


def _secondary_match_ids(
    clusters: Sequence[ClusterCentroid],
    secondary_embedding: np.ndarray,
    threshold: float,
) -> set[uuid.UUID]:
    """Return cluster IDs whose secondary centroid is above threshold."""
    query = _l2_normalize(as_float32_vector(secondary_embedding))
    matched: set[uuid.UUID] = set()
    for cluster in clusters:
        if cluster.secondary_centroid is None:
            continue
        centroid = _l2_normalize(cluster.secondary_centroid)
        similarity = float(centroid @ query)
        if similarity >= threshold:
            matched.add(cluster.cluster_id)
    return matched


def _l2_normalize(vector: np.ndarray) -> np.ndarray:
    """Return a float32 unit vector, or the original row when the norm is 0."""
    values = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(values))
    if norm == 0.0:
        return values
    return values / np.float32(norm)


def _row_to_centroid(row: object) -> ClusterCentroid:
    """Convert a SQLAlchemy row into a ``ClusterCentroid``."""
    cluster_id = row[0]
    centroid = as_float32_vector(row[1])
    secondary = as_float32_vector(row[2]) if row[2] is not None else None
    return ClusterCentroid(
        cluster_id=cluster_id,
        centroid=centroid,
        secondary_centroid=secondary,
    )
