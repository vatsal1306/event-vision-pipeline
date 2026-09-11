"""Data types for guest selfie matching and Phase 1 liveness."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class MatchStatus(str, Enum):
    """Outcome of the guest selfie matching pipeline."""

    MATCHED = "matched"
    NO_MATCH = "no_match"
    NO_FACE_DETECTED = "no_face_detected"
    LOW_QUALITY = "low_quality"
    NO_CLUSTERS = "no_clusters"
    LIVENESS_FAILED = "liveness_failed"
    CROP_FAILED = "crop_failed"
    INVALID_IMAGE = "invalid_image"


@dataclass(frozen=True)
class ClusterMatch:
    """One cluster that passed the cosine similarity threshold."""

    cluster_id: uuid.UUID
    similarity: float
    confidence: str


@dataclass
class MatchResult:
    """Result of matching a guest selfie against event clusters.

    ``clusters`` is an alias for ``matched_cluster_ids`` so the guest API
    (BE-013) keeps working without a parallel DTO.
    """

    status: MatchStatus
    matched_cluster_ids: list[uuid.UUID] = field(default_factory=list)
    selfie_embedding: np.ndarray | None = None
    match_details: list[ClusterMatch] = field(default_factory=list)
    photo_ids: list[uuid.UUID] = field(default_factory=list)
    quality_issue: str | None = None

    @property
    def clusters(self) -> list[uuid.UUID]:
        """Cluster IDs in the same order as ``match_details``."""
        return self.matched_cluster_ids


@dataclass(frozen=True)
class LivenessResult:
    """Outcome of Phase 1 heuristic liveness checks."""

    passed: bool
    checks: dict[str, bool]
    failed_checks: list[str]
    face_size_ratio: float
    sharpness: float
    saturation: float


@dataclass(frozen=True)
class ClusterCentroid:
    """In-memory snapshot of one event cluster for cosine matching."""

    cluster_id: uuid.UUID
    centroid: np.ndarray
    secondary_centroid: np.ndarray | None = None
