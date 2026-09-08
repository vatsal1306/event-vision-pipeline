"""ArcFace alignment utilities ported from PicSee."""

from __future__ import annotations

import cv2
import numpy as np
from skimage import transform as trans

# ArcFace 5-point template used by pix-workers production (112×112).
_ARCFACE_SRC = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)
_ARCFACE_SRC_BATCH = np.expand_dims(_ARCFACE_SRC, axis=0)


def estimate_norm(landmarks: np.ndarray, image_size: int = 112) -> np.ndarray:
    """Estimate the 2×3 affine transform for ArcFace landmark alignment.

    Ported from pix-workers ``face_cropper.estimate_norm`` for PicSee parity.

    Args:
        landmarks: Five facial landmarks, shape ``(5, 2)``.
        image_size: Output crop size (default 112).

    Returns:
        2×3 affine matrix for ``cv2.warpAffine``.
    """
    tform = trans.SimilarityTransform()
    landmark_homogeneous = np.insert(landmarks, 2, values=np.ones(5), axis=1)
    min_error = float("inf")
    min_matrix: np.ndarray | None = None

    if image_size == 112:
        source_points = _ARCFACE_SRC_BATCH
    else:
        scale_factor = float(image_size) / 112.0
        source_points = _ARCFACE_SRC_BATCH * scale_factor

    for index in range(source_points.shape[0]):
        tform.estimate(landmarks, source_points[index])
        matrix = tform.params[0:2, :]
        results = np.dot(matrix, landmark_homogeneous.T).T
        error = float(np.sum(np.sqrt(np.sum((results - source_points[index]) ** 2, axis=1))))
        if error < min_error:
            min_error = error
            min_matrix = matrix

    if min_matrix is None:
        raise ValueError("Failed to estimate alignment transform from landmarks.")
    return min_matrix


def norm_crop(image_bgr: np.ndarray, landmarks: np.ndarray, image_size: int = 112) -> np.ndarray:
    """Align a face crop using ArcFace 5-point landmarks.

    Args:
        image_bgr: Source BGR image.
        landmarks: Five landmarks in pixel coordinates.
        image_size: Output square size.

    Returns:
        Aligned BGR crop of shape ``(image_size, image_size, 3)``.
    """
    matrix = estimate_norm(landmarks, image_size=image_size)
    return cv2.warpAffine(image_bgr, matrix, (image_size, image_size), borderValue=0.0)


def preprocess(
    image_bgr: np.ndarray,
    bbox: np.ndarray | None = None,
    landmark: np.ndarray | None = None,
    **kwargs: object,
) -> np.ndarray:
    """Legacy PicSee preprocessing with landmark or bbox fallback.

    Copied from ``clustering_pipeline/adaface_insightface/face_preprocess.py``.
    Primary alignment path uses ``norm_crop``; this supports bbox-only fallback.

    Args:
        image_bgr: Source BGR image.
        bbox: Optional pixel bbox ``[x1, y1, x2, y2]``.
        landmark: Optional five landmarks.
        **kwargs: ``image_size`` tuple and optional ``margin`` for bbox crop.

    Returns:
        Preprocessed BGR crop.
    """
    matrix: np.ndarray | None = None
    image_size = kwargs.get("image_size", (112, 112))
    if not isinstance(image_size, tuple):
        raise TypeError("image_size must be a (height, width) tuple.")

    if landmark is not None:
        source = np.array(
            [
                [30.2946, 51.6963],
                [65.5318, 51.5014],
                [48.0252, 71.7366],
                [33.5493, 92.3655],
                [62.7299, 92.2041],
            ],
            dtype=np.float32,
        )
        if image_size[1] == 112:
            source[:, 0] += 8.0
        destination = landmark.astype(np.float32)
        tform = trans.SimilarityTransform()
        tform.estimate(destination, source)
        matrix = tform.params[0:2, :]

    if matrix is None:
        if bbox is None:
            detection = np.zeros(4, dtype=np.int32)
            detection[0] = int(image_bgr.shape[1] * 0.0625)
            detection[1] = int(image_bgr.shape[0] * 0.0625)
            detection[2] = image_bgr.shape[1] - detection[0]
            detection[3] = image_bgr.shape[0] - detection[1]
        else:
            detection = bbox.astype(np.int32)

        margin = int(kwargs.get("margin", 44))
        bounded = np.zeros(4, dtype=np.int32)
        bounded[0] = max(int(detection[0]) - margin // 2, 0)
        bounded[1] = max(int(detection[1]) - margin // 2, 0)
        bounded[2] = min(int(detection[2]) + margin // 2, image_bgr.shape[1])
        bounded[3] = min(int(detection[3]) + margin // 2, image_bgr.shape[0])
        cropped = image_bgr[bounded[1] : bounded[3], bounded[0] : bounded[2], :]
        if len(image_size) > 0:
            return cv2.resize(cropped, (image_size[1], image_size[0]))
        return cropped

    return cv2.warpAffine(
        image_bgr,
        matrix,
        (image_size[1], image_size[0]),
        borderValue=0.0,
        flags=cv2.INTER_AREA,
    )
