"""Guest selfie matching and Phase 1 liveness (ML-008)."""

from __future__ import annotations

from app.ml.matching.liveness import BasicLivenessDetector
from app.ml.matching.pipeline import SelfieMatchPipeline, decode_selfie_bytes
from app.ml.matching.selfie_matcher import SelfieMatcher, cross_validate, rank_centroid_matches
from app.ml.matching.types import (
    ClusterCentroid,
    ClusterMatch,
    LivenessResult,
    MatchResult,
    MatchStatus,
)

__all__ = [
    "BasicLivenessDetector",
    "ClusterCentroid",
    "ClusterMatch",
    "LivenessResult",
    "MatchResult",
    "MatchStatus",
    "SelfieMatchPipeline",
    "SelfieMatcher",
    "cross_validate",
    "decode_selfie_bytes",
    "rank_centroid_matches",
]
