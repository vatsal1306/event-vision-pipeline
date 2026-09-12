"""Helpers to persist face embedding rows from detection + quality results."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import numpy as np

from app.ml.detection.types import FaceCrop
from app.ml.quality.types import QualityResult
from app.models.face_cluster import EMBEDDING_DIMENSIONS
from app.models.face_embedding import FaceEmbedding

# Quality-rejected faces still need a NOT NULL vector. Clustering and guest
# match ignore ``quality_passed=false``, so this placeholder is never searched.
FAILED_FACE_PLACEHOLDER_EMBEDDING: list[float] = [0.0] * EMBEDDING_DIMENSIONS


@dataclass
class FaceCropWithMeta:
    """A cropped face plus the photo/quality context needed to flush embeddings."""

    crop: FaceCrop
    photo_id: UUID
    event_id: UUID
    quality: QualityResult


def embedding_vector_to_list(vector: np.ndarray) -> list[float]:
    """Convert a float32 embedding array to a pgvector-compatible list."""
    return vector.astype(float).tolist()


def build_face_embedding_row(
    *,
    photo_id: UUID,
    event_id: UUID,
    crop: FaceCrop,
    quality: QualityResult,
    primary: list[float],
    secondary: list[float] | None,
    quality_passed: bool,
) -> FaceEmbedding:
    """Build a ``FaceEmbedding`` row from a crop and quality result.

    Args:
        photo_id: Parent photo UUID.
        event_id: Parent event UUID.
        crop: Aligned face crop with source detection.
        quality: Quality-filter outcome.
        primary: 512-d primary embedding (or placeholder for rejects).
        secondary: Optional AdaFace vector.
        quality_passed: Whether clustering/matching should use this row.

    Returns:
        Unpersisted SQLAlchemy instance.
    """
    bbox = crop.source_detection.bbox
    yaw = pitch = roll = None
    if quality.ypr is not None:
        yaw, pitch, roll = quality.ypr
    return FaceEmbedding(
        photo_id=photo_id,
        event_id=event_id,
        embedding=primary,
        secondary_embedding=secondary,
        bbox_x=float(bbox[0]),
        bbox_y=float(bbox[1]),
        bbox_w=float(bbox[2]),
        bbox_h=float(bbox[3]),
        detection_score=float(crop.source_detection.score),
        blur_score=quality.blur_score,
        yaw=yaw,
        pitch=pitch,
        roll=roll,
        quality_passed=quality_passed,
    )
