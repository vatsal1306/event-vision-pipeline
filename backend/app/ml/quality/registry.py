"""Model loader registration for quality filters."""

from __future__ import annotations

from app.ml.model_registry import ModelRegistry, register_model_loader
from app.ml.quality.age_detector import AgeDetector
from app.ml.quality.blur_detector import BlurDetector
from app.ml.quality.quality_filter import QualityFilter
from app.ml.quality.sunglasses import SunglassesDetector
from app.ml.quality.ypr_3ddfa import YPRPredictor


def _load_blur_detector(registry: ModelRegistry) -> BlurDetector:
    config = registry.config
    return BlurDetector(
        model_path=config.blur_model_path,
        threshold=config.blur_threshold,
    )


def _load_ypr_predictor(registry: ModelRegistry) -> YPRPredictor:
    config = registry.config
    return YPRPredictor(
        model_type=config.ypr_model_type,
        config_path=config.ypr_3ddfa_config_path,
        tflite_model_path=config.ypr_tflite_model_path,
        yaw_threshold=config.yaw_threshold,
        pitch_threshold=config.pitch_threshold,
        roll_threshold=config.roll_threshold,
    )


def _load_age_detector(registry: ModelRegistry) -> AgeDetector | None:
    config = registry.config
    if not config.age_detection_enabled:
        return None
    return AgeDetector(
        model_path=config.age_model_path,
        device=registry.resolved_device,
    )


def _load_sunglasses_detector(registry: ModelRegistry) -> SunglassesDetector | None:
    config = registry.config
    if not config.sunglasses_detection_enabled:
        return None
    return SunglassesDetector(threshold=config.sunglasses_threshold)


def _load_quality_filter(registry: ModelRegistry) -> QualityFilter:
    config = registry.config
    return QualityFilter(
        blur_detector=registry.get_model("blur_detector"),
        ypr_predictor=registry.get_model("ypr_predictor"),
        age_detector=registry.get_model("age_detector"),
        sunglasses_detector=registry.get_model("sunglasses_detector"),
        age_detection_enabled=config.age_detection_enabled,
        sunglasses_detection_enabled=config.sunglasses_detection_enabled,
        age_min_threshold=config.age_min_threshold,
    )


def register_quality_loaders() -> None:
    """Register blur, YPR, age, sunglasses, and quality filter loaders."""
    register_model_loader("blur_detector", _load_blur_detector)
    register_model_loader("ypr_predictor", _load_ypr_predictor)
    register_model_loader("age_detector", _load_age_detector)
    register_model_loader("sunglasses_detector", _load_sunglasses_detector)
    register_model_loader("quality_filter", _load_quality_filter)


register_quality_loaders()
