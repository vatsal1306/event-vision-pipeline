"""Age detector integration test (loads local ViT snapshot)."""

from __future__ import annotations

import pytest

from app.ml.config import get_ml_config
from app.ml.quality.age_detector import AgeDetector
from tests.ml.conftest import age_model_available, run_ml_integration_tests

pytestmark = pytest.mark.ml


def test_age_detector_loads_local_snapshot_and_returns_adult_age(
    quality_filter,
) -> None:
    """Local HuggingFace snapshot should produce a plausible adult age."""
    if not run_ml_integration_tests():
        pytest.skip("RUN_ML_TESTS!=1")
    if not age_model_available():
        pytest.skip("Age model snapshot missing")

    _, crop = quality_filter
    config = get_ml_config()
    detector = AgeDetector(model_path=config.age_model_path, device="cpu")
    try:
        age, confidence = detector.estimate(crop.aligned_face)
    finally:
        detector.close()

    assert confidence > 0.0
    assert age >= config.age_min_threshold
