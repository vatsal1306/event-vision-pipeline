"""Data types for face detection and alignment."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DetectedFace:
    """A single face detected by SCRFD.

    Attributes:
        bbox: Normalized bounding box ``[x, y, w, h]`` in 0–1 range.
        bbox_pixel: Pixel bounding box ``[x, y, w, h]`` (top-left + size).
        landmarks: Five facial landmarks in pixel coordinates, shape ``(5, 2)``.
        score: Detection confidence in ``[0, 1]``.
    """

    bbox: np.ndarray
    bbox_pixel: np.ndarray
    landmarks: np.ndarray
    score: float


@dataclass(frozen=True)
class FaceCrop:
    """An ArcFace-aligned 112×112 face crop."""

    aligned_face: np.ndarray
    source_detection: DetectedFace
    alignment_matrix: np.ndarray | None
    source_photo_id: uuid.UUID | None = None
