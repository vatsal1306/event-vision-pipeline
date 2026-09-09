"""Shared fixtures for ML detection tests."""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.ml.config import get_ml_config
from app.ml.model_registry import ModelRegistry, get_model_registry
from app.ml.registry_bootstrap import register_default_model_loaders

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PICSEE_FACE_CROPPER = Path(
    "/Users/vatsal/Documents/picsee/tmp/code/pix-workers/face_rec_service/embedding/utils/face_cropper.py"
)


@pytest.fixture(scope="session", autouse=True)
def _initialize_ml_test_runtime() -> None:
    """Register loaders once; pre-import torch only for local ML integration runs."""
    register_default_model_loaders()
    if run_ml_integration_tests():
        try:
            import torch  # noqa: F401
        except ImportError:
            pass


def scrfd_model_available() -> bool:
    """Return True when the SCRFD ONNX weights exist locally."""
    return get_ml_config().scrfd_model_path.exists()


def run_ml_integration_tests() -> bool:
    """Return True when integration tests should load real models."""
    return os.environ.get("RUN_ML_TESTS", "1") == "1"


def blur_model_available() -> bool:
    """Return True when blur TFLite weights exist locally."""
    return get_ml_config().blur_model_path.exists()


def ypr_models_available() -> bool:
    """Return True when YPR model assets exist locally."""
    config = get_ml_config()
    return (
        config.ypr_tflite_model_path.exists()
        and config.resnet22_onnx_path.exists()
        and config.faceboxes_onnx_path.exists()
        and config.ypr_3ddfa_config_path.exists()
    )


def quality_models_available() -> bool:
    """Return True when all quality-filter model assets exist locally."""
    return blur_model_available() and ypr_models_available()


def age_model_available() -> bool:
    """Return True when the local ViT age snapshot exists."""
    config = get_ml_config()
    model_dir = config.age_model_path
    return (
        model_dir.exists()
        and (model_dir / "config.json").exists()
        and (
            (model_dir / "model.safetensors").exists() or (model_dir / "pytorch_model.bin").exists()
        )
    )


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to ``tests/ml/fixtures``."""
    return FIXTURES_DIR


@pytest.fixture
def load_bgr_image(fixtures_dir: Path):
    """Load a named fixture image as a BGR numpy array."""

    def _load(name: str) -> np.ndarray:
        path = fixtures_dir / name
        image = cv2.imread(str(path))
        if image is None:
            raise FileNotFoundError(f"Could not read fixture image: {path}")
        return image

    return _load


@pytest.fixture
def scrfd_detector():
    """SCRFD detector backed by local ONNX weights."""
    pytest.importorskip("onnxruntime")
    from app.ml.detection.scrfd import SCRFDDetector

    if not scrfd_model_available() or not run_ml_integration_tests():
        pytest.skip("SCRFD model file missing or RUN_ML_TESTS!=1")
    config = get_ml_config()
    detector = SCRFDDetector(
        model_path=config.scrfd_model_path,
        device="cpu",
        det_thresh=config.scrfd_det_thresh,
        nms_thresh=config.scrfd_nms_thresh,
        input_sizes=config.scrfd_input_sizes,
    )
    yield detector
    detector.close()


@pytest.fixture
def face_cropper(scrfd_detector):
    """Face cropper bound to a live SCRFD detector."""
    from app.ml.detection.face_cropper import FaceCropper

    return FaceCropper(detector=scrfd_detector)


@pytest.fixture
def quality_registry(monkeypatch: pytest.MonkeyPatch):
    """Fresh registry with default loaders registered."""
    monkeypatch.setenv("ML_DEVICE", "cpu")
    monkeypatch.setenv("ML_AGE_DETECTION_ENABLED", "false")
    monkeypatch.setenv("ML_SUNGLASSES_DETECTION_ENABLED", "false")
    register_default_model_loaders()
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    registry = get_model_registry()
    yield registry
    registry.unload_all()
    ModelRegistry.reset_for_tests()
    get_ml_config.cache_clear()


@pytest.fixture
def quality_filter(
    quality_registry,
    scrfd_detector,
    face_cropper,
    load_bgr_image,
    monkeypatch: pytest.MonkeyPatch,
):
    """Quality filter backed by local model weights."""
    monkeypatch.setenv("ML_DEVICE", "cpu")
    monkeypatch.setenv("ML_AGE_DETECTION_ENABLED", "false")
    monkeypatch.setenv("ML_SUNGLASSES_DETECTION_ENABLED", "false")
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    register_default_model_loaders()
    registry = get_model_registry()

    if not run_ml_integration_tests():
        pytest.skip("RUN_ML_TESTS!=1")
    if not quality_models_available():
        pytest.skip("Quality model files missing")

    quality_filter_model = registry.get_model("quality_filter")
    from app.ml.quality.quality_filter import QualityFilter

    assert isinstance(quality_filter_model, QualityFilter)

    image = load_bgr_image("single_face.jpg")
    faces = scrfd_detector.detect(image)
    crops = face_cropper.crop_all(image, faces)
    assert crops, "Expected at least one crop from single_face fixture"

    yield quality_filter_model, crops[0]
