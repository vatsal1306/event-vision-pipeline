"""Shared fixtures for ML detection tests."""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.ml.config import get_ml_config
from app.ml.model_registry import ModelRegistry, get_model_registry

EMBEDDING_DIM = 512

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PICSEE_FACE_CROPPER = Path(
    "/Users/vatsal/Documents/picsee/tmp/code/pix-workers/face_rec_service/embedding/utils/face_cropper.py"
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark ``tests/ml/integration`` as slow model-backed tests.

    GitHub CI keeps using ``-m "not ml"`` so these never run on the CPU runner.
    Local ``make test`` still collects them; they skip unless models exist.
    """
    del config
    for item in items:
        path = Path(str(item.fspath))
        if "tests/ml/integration" in path.as_posix():
            item.add_marker(pytest.mark.ml)
            item.add_marker(pytest.mark.slow)


def _register_default_loaders() -> None:
    """Register ML loaders without importing heavy deps at conftest import time."""
    from app.ml.registry_bootstrap import register_default_model_loaders

    register_default_model_loaders()


@pytest.fixture(scope="session", autouse=True)
def _initialize_ml_test_runtime() -> None:
    """Register loaders once; pre-import torch only for local ML integration runs."""
    _register_default_loaders()
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


def r100_model_available() -> bool:
    """Return True when ArcFace R100 PyTorch weights exist locally."""
    return get_ml_config().r100_model_path.exists()


def adaface_models_available() -> bool:
    """Return True when AdaFace VIT-KPRPE and DFA aligner exports exist."""
    config = get_ml_config()
    adaface_dir = config.adaface_model_path
    aligner_dir = config.dfa_aligner_path
    return (
        adaface_dir.is_dir()
        and (adaface_dir / "config.json").exists()
        and aligner_dir.is_dir()
        and (aligner_dir / "config.json").exists()
    )


def mbf_model_available() -> bool:
    """Return True when MobileFaceNet TFLite weights exist locally."""
    return get_ml_config().mbf_model_path.exists()


def embedding_models_available() -> bool:
    """Return True when primary embedding model assets exist locally."""
    return r100_model_available()


def _l2_normalize(vector: np.ndarray) -> np.ndarray:
    """Return a unit-length float32 vector."""
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise ValueError("Cannot L2-normalize a zero vector.")
    return (vector / norm).astype(np.float32)


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to ``tests/ml/fixtures``."""
    return FIXTURES_DIR


@pytest.fixture
def synthetic_embedding() -> np.ndarray:
    """Random 512-d L2-normalized embedding."""
    rng = np.random.default_rng(123)
    return _l2_normalize(rng.standard_normal(EMBEDDING_DIM).astype(np.float32))


@pytest.fixture
def well_separated_embeddings() -> np.ndarray:
    """Three clusters of five embeddings each, clearly separated in 512-d."""
    rng = np.random.default_rng(7)
    rows: list[np.ndarray] = []
    for _cluster in range(3):
        center = _l2_normalize(rng.standard_normal(EMBEDDING_DIM).astype(np.float32))
        for _ in range(5):
            noise = rng.standard_normal(EMBEDDING_DIM).astype(np.float32) * 0.001
            rows.append(_l2_normalize(center + noise))
    return np.stack(rows, axis=0)


@pytest.fixture
def overlapping_embeddings() -> np.ndarray:
    """Two nearby clusters that clustering may merge depending on eps."""
    rng = np.random.default_rng(11)
    first = _l2_normalize(rng.standard_normal(EMBEDDING_DIM).astype(np.float32))
    second = _l2_normalize(first + rng.standard_normal(EMBEDDING_DIM).astype(np.float32) * 0.2)
    rows: list[np.ndarray] = []
    for center in (first, second):
        for _ in range(4):
            noise = rng.standard_normal(EMBEDDING_DIM).astype(np.float32) * 0.001
            rows.append(_l2_normalize(center + noise))
    return np.stack(rows, axis=0)


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
    _register_default_loaders()
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
    _register_default_loaders()
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
