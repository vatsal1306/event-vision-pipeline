"""Shared fixtures for ML detection tests."""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.ml.config import get_ml_config
from app.ml.detection.face_cropper import FaceCropper
from app.ml.detection.scrfd import SCRFDDetector

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PICSEE_FACE_CROPPER = Path(
    "/Users/vatsal/Documents/picsee/tmp/code/pix-workers/face_rec_service/embedding/utils/face_cropper.py"
)


def scrfd_model_available() -> bool:
    """Return True when the SCRFD ONNX weights exist locally."""
    return get_ml_config().scrfd_model_path.exists()


def run_ml_integration_tests() -> bool:
    """Return True when integration tests should load real models."""
    return os.environ.get("RUN_ML_TESTS", "1") == "1"


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
def scrfd_detector() -> SCRFDDetector:
    """SCRFD detector backed by local ONNX weights."""
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
def face_cropper(scrfd_detector: SCRFDDetector) -> FaceCropper:
    """Face cropper bound to a live SCRFD detector."""
    return FaceCropper(detector=scrfd_detector)
