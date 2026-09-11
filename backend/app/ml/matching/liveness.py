"""Phase 1 heuristic liveness checks for guest selfies."""

from __future__ import annotations

import cv2
import numpy as np

from app.ml.config import MLConfig, get_ml_config
from app.ml.detection.types import DetectedFace
from app.ml.matching.types import LivenessResult


class BasicLivenessDetector:
    """Quality-focused anti-spoof heuristics (not a deep-learning liveness model).

    Catches obvious non-selfies (tiny/huge face, low detector confidence, blurry
    or greyscale printouts). Sophisticated presentation attacks are out of scope.
    """

    def __init__(self, config: MLConfig | None = None) -> None:
        """Create a detector bound to ML liveness thresholds.

        Args:
            config: Optional settings override. Defaults to ``get_ml_config()``.
        """
        self._config = config or get_ml_config()

    def check(self, image_bgr: np.ndarray, detected_face: DetectedFace) -> LivenessResult:
        """Run face-size, detection-score, sharpness, and saturation checks.

        Args:
            image_bgr: Full selfie frame in BGR.
            detected_face: Primary SCRFD detection already chosen for this selfie.

        Returns:
            ``LivenessResult`` with per-check booleans and numeric diagnostics.

        Raises:
            ValueError: If ``image_bgr`` is not a 3-channel image.
        """
        if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
            raise ValueError("Expected a BGR selfie image with shape (H, W, 3).")

        config = self._config
        face_ratio = _normalized_face_area(detected_face)
        checks = {
            "face_size": (
                config.liveness_face_ratio_min <= face_ratio <= config.liveness_face_ratio_max
            ),
            "detection_confidence": float(detected_face.score) >= config.liveness_det_score_min,
        }

        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        checks["sharpness"] = sharpness >= config.liveness_sharpness_min

        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        saturation = float(hsv[:, :, 1].mean())
        checks["color_present"] = saturation > config.liveness_saturation_min

        failed_checks = [name for name, passed in checks.items() if not passed]
        return LivenessResult(
            passed=not failed_checks,
            checks=checks,
            failed_checks=failed_checks,
            face_size_ratio=face_ratio,
            sharpness=sharpness,
            saturation=saturation,
        )


def _normalized_face_area(detected_face: DetectedFace) -> float:
    """Return bbox area as a fraction of the image (normalized ``w * h``)."""
    width = float(detected_face.bbox[2])
    height = float(detected_face.bbox[3])
    return max(0.0, width * height)
