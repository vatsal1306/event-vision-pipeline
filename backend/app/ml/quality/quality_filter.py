"""Quality gate orchestrator for face crops."""

from __future__ import annotations

import structlog

from app.ml.detection.types import FaceCrop
from app.ml.quality.age_detector import DEFAULT_FAILED_AGE, AgeDetector
from app.ml.quality.blur_detector import BlurDetector
from app.ml.quality.sunglasses import SunglassesDetector
from app.ml.quality.types import QualityResult
from app.ml.quality.ypr_3ddfa import YPRPredictor

logger = structlog.get_logger(__name__)


class QualityFilter:
    """Runs blur, YPR, age, and sunglasses gates on ArcFace-aligned crops."""

    def __init__(
        self,
        blur_detector: BlurDetector,
        ypr_predictor: YPRPredictor,
        age_detector: AgeDetector | None = None,
        sunglasses_detector: SunglassesDetector | None = None,
        *,
        age_detection_enabled: bool = True,
        sunglasses_detection_enabled: bool = True,
        age_min_threshold: int = 5,
    ) -> None:
        """Create a quality filter from pre-loaded model components."""
        self._blur_detector = blur_detector
        self._ypr_predictor = ypr_predictor
        self._age_detector = age_detector
        self._sunglasses_detector = sunglasses_detector
        self._age_detection_enabled = age_detection_enabled
        self._sunglasses_detection_enabled = sunglasses_detection_enabled
        self._age_min_threshold = age_min_threshold

    def filter(self, face_crop: FaceCrop) -> QualityResult:
        """Run quality gates with early exit on hard rejects.

        Model inference failures use pass-on-error semantics: the crop is treated
        as passed and a warning is logged.
        """
        metadata: dict[str, object] = {}
        crop = face_crop.aligned_face

        blur_score: float | None = None
        ypr: tuple[float, float, float] | None = None
        age: int | None = None
        has_sunglasses = False

        try:
            is_blurry, blur_score = self._blur_detector.is_blurry(crop)
        except Exception as exc:
            logger.warning("blur_detector_failed_pass_on_error", error=str(exc))
            metadata["blur_error"] = str(exc)
            is_blurry = False
            blur_score = None

        metadata["blur_score"] = blur_score
        if is_blurry:
            return QualityResult(
                passed=False,
                reject_reason="blur",
                blur_score=blur_score,
                ypr=None,
                age=None,
                has_sunglasses=False,
                metadata=metadata,
            )

        try:
            ypr, is_extreme, ypr_error = self._ypr_predictor.estimate(crop)
        except Exception as exc:
            logger.warning("ypr_predictor_failed_pass_on_error", error=str(exc))
            metadata["ypr_error"] = str(exc)
            ypr, is_extreme, ypr_error = None, False, True

        metadata["ypr"] = ypr
        metadata["ypr_backend"] = self._ypr_predictor.backend
        if ypr_error:
            metadata["ypr_pass_on_error"] = True
        elif is_extreme and ypr is not None:
            return QualityResult(
                passed=False,
                reject_reason="ypr",
                blur_score=blur_score,
                ypr=ypr,
                age=None,
                has_sunglasses=False,
                metadata=metadata,
            )

        if self._age_detection_enabled and self._age_detector is not None:
            try:
                estimated_age, age_confidence = self._age_detector.estimate(crop)
                metadata["age_confidence"] = age_confidence
                if estimated_age == DEFAULT_FAILED_AGE:
                    metadata["age_pass_on_error"] = True
                    logger.warning("age_detector_low_confidence_pass_on_error")
                else:
                    age = estimated_age
                    if age < self._age_min_threshold:
                        return QualityResult(
                            passed=False,
                            reject_reason="age",
                            blur_score=blur_score,
                            ypr=ypr,
                            age=age,
                            has_sunglasses=False,
                            metadata=metadata,
                        )
            except Exception as exc:
                logger.warning("age_detector_failed_pass_on_error", error=str(exc))
                metadata["age_error"] = str(exc)
                metadata["age_pass_on_error"] = True

        if self._sunglasses_detection_enabled and self._sunglasses_detector is not None:
            try:
                has_sunglasses, sunglasses_probability = self._sunglasses_detector.detect(crop)
                metadata["sunglasses_probability"] = sunglasses_probability
                metadata["sunglasses_available"] = self._sunglasses_detector.available
            except Exception as exc:
                logger.warning("sunglasses_detector_failed_pass_on_error", error=str(exc))
                metadata["sunglasses_error"] = str(exc)

        return QualityResult(
            passed=True,
            reject_reason=None,
            blur_score=blur_score,
            ypr=ypr,
            age=age,
            has_sunglasses=has_sunglasses,
            metadata=metadata,
        )

    def close(self) -> None:
        """Release all underlying detectors."""
        self._blur_detector.close()
        self._ypr_predictor.close()
        if self._age_detector is not None:
            self._age_detector.close()
        if self._sunglasses_detector is not None:
            self._sunglasses_detector.close()
