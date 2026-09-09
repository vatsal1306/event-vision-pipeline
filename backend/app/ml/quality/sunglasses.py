"""Optional sunglasses detection wrapper."""

from __future__ import annotations

import importlib.util

import cv2
import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class SunglassesDetector:
    """Detect sunglasses using the optional ``glasses-detector`` package.

    On Python 3.10 the upstream package is unavailable (requires 3.12+). In that
    case initialization succeeds but ``available`` is ``False`` and predictions
    always return ``False``.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        kind: str = "sunglasses",
        size: str = "medium",
        padding_ratio: float = 0.3,
    ) -> None:
        """Attempt to load ``glasses-detector`` when the runtime supports it."""
        self.threshold = threshold
        self.padding_ratio = padding_ratio
        self._available = False
        self._classifier = None
        self._output_format = "proba"

        if importlib.util.find_spec("glasses_detector") is None:
            logger.warning(
                "sunglasses_detector_unavailable",
                reason="glasses-detector package not installed (requires Python 3.12+)",
            )
            return

        from glasses_detector import GlassesClassifier

        self._classifier = GlassesClassifier(kind=kind, size=size)
        self._available = True
        logger.info(
            "sunglasses_detector_loaded",
            device=str(getattr(self._classifier, "device", "unknown")),
        )

    @property
    def available(self) -> bool:
        """Return ``True`` when the underlying classifier loaded successfully."""
        return self._available

    def detect(self, face_crop_bgr: np.ndarray) -> tuple[bool, float | None]:
        """Return whether sunglasses are present and the raw probability."""
        if not self._available or self._classifier is None:
            return False, None

        rgb = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2RGB)
        padded = self._pad_image(rgb, self.padding_ratio)
        probability = float(self._classifier.predict(padded, format=self._output_format))
        return probability >= self.threshold, probability

    @staticmethod
    def _pad_image(image_rgb: np.ndarray, padding_ratio: float) -> np.ndarray:
        height, width = image_rgb.shape[:2]
        top = bottom = int(height * padding_ratio)
        left = right = int(width * padding_ratio)
        return cv2.copyMakeBorder(
            image_rgb,
            top,
            bottom,
            left,
            right,
            cv2.BORDER_CONSTANT,
            value=(0, 0, 0),
        )

    def close(self) -> None:
        """Release classifier resources."""
        self._classifier = None
        logger.debug("sunglasses_detector_closed")
