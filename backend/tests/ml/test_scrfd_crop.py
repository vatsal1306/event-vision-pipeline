"""Integration tests for SCRFD detection and ArcFace cropping."""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pytest

pytest.importorskip("onnxruntime")

from app.ml.config import get_ml_config
from app.ml.detection import registry as detection_registry  # noqa: F401
from app.ml.detection.face_cropper import FaceCropper
from app.ml.detection.scrfd import SCRFDDetector
from app.ml.model_registry import get_model_registry, register_model_loader
from tests.ml.conftest import PICSEE_FACE_CROPPER, scrfd_model_available

pytestmark = pytest.mark.ml


def _load_picsee_scrfd():
    """Load pix-workers SCRFD for parity comparison."""
    if not PICSEE_FACE_CROPPER.exists():
        pytest.skip("PicSee pix-workers source not available on this machine")
    spec = importlib.util.spec_from_file_location("picsee_face_cropper", PICSEE_FACE_CROPPER)
    if spec is None or spec.loader is None:
        pytest.skip("Could not load PicSee face_cropper module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["picsee_face_cropper"] = module
    spec.loader.exec_module(module)
    return module


def test_no_face_image_returns_empty_list(
    scrfd_detector: SCRFDDetector,
    load_bgr_image,
) -> None:
    """No-face image should return an empty list without raising."""
    image = load_bgr_image("no_face.jpg")
    assert scrfd_detector.detect(image) == []


def test_blank_image_returns_empty_list(
    scrfd_detector: SCRFDDetector,
    load_bgr_image,
) -> None:
    """Solid-color fixture must not hallucinate a face."""
    image = load_bgr_image("blank_image.jpg")
    assert scrfd_detector.detect(image) == []


def test_single_face_fixture_detects_one_face(
    scrfd_detector: SCRFDDetector,
    load_bgr_image,
) -> None:
    """Known single-face fixture should produce exactly one detection."""
    image = load_bgr_image("single_face.jpg")
    faces = scrfd_detector.detect(image)
    assert len(faces) == 1
    assert faces[0].landmarks.shape == (5, 2)
    assert np.any(faces[0].landmarks)


def test_crop_output_shape_and_dtype(
    scrfd_detector: SCRFDDetector,
    face_cropper: FaceCropper,
    load_bgr_image,
) -> None:
    """Aligned crop must be 112×112 uint8 BGR."""
    image = load_bgr_image("single_face.jpg")
    faces = scrfd_detector.detect(image)
    crops = face_cropper.crop_all(image, faces)
    assert len(crops) == 1
    assert crops[0].aligned_face.shape == (112, 112, 3)
    assert crops[0].aligned_face.dtype == np.uint8


def test_group_photo_detects_three_or_more_faces(
    scrfd_detector: SCRFDDetector,
    load_bgr_image,
) -> None:
    """Group fixture should detect at least three faces."""
    image = load_bgr_image("group_photo.jpg")
    faces = scrfd_detector.detect(image)
    assert len(faces) >= 3


def test_normalized_bbox_values_in_unit_interval(
    scrfd_detector: SCRFDDetector,
    load_bgr_image,
) -> None:
    """Normalized bbox components must lie in [0, 1]."""
    image = load_bgr_image("group_photo.jpg")
    for face in scrfd_detector.detect(image):
        assert np.all(face.bbox >= 0.0)
        assert np.all(face.bbox <= 1.0)


def test_multiscale_detects_at_least_as_many_faces_as_single_640_pass(
    scrfd_detector: SCRFDDetector,
    load_bgr_image,
) -> None:
    """Multi-scale autodetect should not miss faces found only at 128×128."""
    image = load_bgr_image("group_photo.jpg")
    multi_faces = scrfd_detector.detect(image)
    single_scale_faces = scrfd_detector.detect_at_scale(image, input_size=640)
    assert len(multi_faces) >= len(single_scale_faces)


def test_crop_primary_returns_single_crop(
    scrfd_detector: SCRFDDetector,
    face_cropper: FaceCropper,
    load_bgr_image,
) -> None:
    """Primary crop path should return one face from a group image."""
    image = load_bgr_image("group_photo.jpg")
    faces = scrfd_detector.detect(image)
    primary = face_cropper.crop_primary(image, faces)
    assert primary is not None
    assert primary.aligned_face.shape == (112, 112, 3)


def test_model_registry_detects_faces_on_fixture(load_bgr_image) -> None:
    """Registry path (manual REPL flow) should detect faces on Mac and Linux."""
    if not scrfd_model_available():
        pytest.skip("SCRFD model file missing")
    from app.ml.detection.registry import _load_scrfd

    register_model_loader("scrfd", _load_scrfd)
    registry = get_model_registry()
    detector = registry.get_model("scrfd")
    image = load_bgr_image("single_face.jpg")
    faces = detector.detect(image)
    assert len(faces) == 1


def test_model_registry_returns_same_scrfd_instance() -> None:
    """Registry should cache SCRFD across repeated get_model calls."""
    if not scrfd_model_available():
        pytest.skip("SCRFD model file missing")
    from app.ml.detection.registry import _load_scrfd

    register_model_loader("scrfd", _load_scrfd)
    registry = get_model_registry()
    first = registry.get_model("scrfd")
    second = registry.get_model("scrfd")
    assert first is second


def test_picsee_scrfd_parity_on_single_face(load_bgr_image) -> None:
    """SpotMe SCRFD output should match pix-workers on the same image."""
    if not scrfd_model_available():
        pytest.skip("SCRFD model file missing")

    picsee_module = _load_picsee_scrfd()
    config = get_ml_config()
    image = load_bgr_image("single_face.jpg")

    picsee_detector = picsee_module.SCRFD(
        str(config.scrfd_model_path),
        providers=["CPUExecutionProvider"],
    )
    picsee_detector.det_thresh = config.scrfd_det_thresh
    picsee_detector.nms_thresh = config.scrfd_nms_thresh
    picsee_bboxes, picsee_kpss = picsee_detector.autodetect(
        image,
        max_num=0,
        metric="max",
        thresh=config.scrfd_det_thresh,
    )

    spotme_detector = SCRFDDetector(
        model_path=config.scrfd_model_path,
        device="cpu",
        det_thresh=config.scrfd_det_thresh,
        nms_thresh=config.scrfd_nms_thresh,
        input_sizes=config.scrfd_input_sizes,
    )
    spotme_faces = spotme_detector.detect(image)
    spotme_detector.close()

    assert picsee_bboxes.shape[0] == len(spotme_faces)
    assert len(spotme_faces) == 1

    px1, py1, px2, py2, pscore = picsee_bboxes[0]
    face = spotme_faces[0]
    sx1, sy1, sw, sh = face.bbox_pixel
    sx2, sy2 = sx1 + sw, sy1 + sh

    np.testing.assert_allclose([px1, py1, px2, py2], [sx1, sy1, sx2, sy2], rtol=0, atol=1.0)
    assert abs(float(pscore) - face.score) < 1e-4
    assert picsee_kpss is not None
    np.testing.assert_allclose(picsee_kpss[0], face.landmarks, rtol=0, atol=1.0)
