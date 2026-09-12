"""End-to-end ML tests against real weights on CPU or GPU.

GitHub CI never collects these (``pytest -m "not ml"``). Locally they skip
when ``RUN_ML_TESTS!=1`` or when model files are missing.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.clustering import CLUSTER_TYPE, ClusteringInput, IncrementalClusterer
from app.ml.config import MLConfig, get_ml_config
from app.ml.embedding.dual_embedder import DualEmbedder
from app.ml.model_registry import ModelRegistry, get_model_registry
from app.ml.registry_bootstrap import register_default_model_loaders
from tests.ml.conftest import (
    adaface_models_available,
    embedding_models_available,
    run_ml_integration_tests,
    scrfd_model_available,
)

pytest.importorskip("onnxruntime")
pytest.importorskip("sklearn")
pytest.importorskip("torch")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _require_live_models(*, dual: bool = False) -> None:
    """Skip when the operator did not opt into live-model runs."""
    if not run_ml_integration_tests():
        pytest.skip("RUN_ML_TESTS!=1")
    if not scrfd_model_available() or not embedding_models_available():
        pytest.skip("SCRFD or R100 model files missing")
    if dual and not adaface_models_available():
        pytest.skip("AdaFace model files missing")


def _aligned_crops(scrfd_detector, face_cropper, load_bgr_image, name: str) -> list[np.ndarray]:
    image = load_bgr_image(name)
    faces = scrfd_detector.detect(image)
    crops = face_cropper.crop_all(image, faces)
    return [crop.aligned_face for crop in crops]


def test_e2e_real_embedding(
    scrfd_detector,
    face_cropper,
    load_bgr_image,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same crop embedded twice with R100 must be nearly identical."""
    _require_live_models()
    monkeypatch.setenv("ML_DEVICE", "cpu")
    monkeypatch.setenv("ML_EMBEDDING_MODEL", "r100")
    monkeypatch.setenv("ML_DUAL_MODEL_ENABLED", "false")
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    register_default_model_loaders()
    embedder = get_model_registry().get_model("dual_embedder")
    assert isinstance(embedder, DualEmbedder)

    crops = _aligned_crops(scrfd_detector, face_cropper, load_bgr_image, "single_face.jpg")
    assert crops, "single_face.jpg should yield at least one crop"
    first = embedder.embed_single(crops[0])
    second = embedder.embed_single(crops[0])
    assert _cosine(first.primary, second.primary) > 0.99


def test_e2e_two_faces_produce_distinct_embeddings(
    scrfd_detector,
    face_cropper,
    load_bgr_image,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two different people in a group photo should not collapse to one identity."""
    _require_live_models()
    monkeypatch.setenv("ML_DEVICE", "cpu")
    monkeypatch.setenv("ML_EMBEDDING_MODEL", "r100")
    monkeypatch.setenv("ML_DUAL_MODEL_ENABLED", "false")
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    register_default_model_loaders()
    embedder = get_model_registry().get_model("dual_embedder")
    assert isinstance(embedder, DualEmbedder)

    crops = _aligned_crops(scrfd_detector, face_cropper, load_bgr_image, "group_photo.jpg")
    if len(crops) < 2:
        pytest.skip("group_photo.jpg did not yield two crops")
    results = embedder.embed_batch(crops[:2])
    similarity = _cosine(results[0].primary, results[1].primary)
    assert similarity < 0.5


def test_e2e_cluster_real_faces(
    scrfd_detector,
    face_cropper,
    load_bgr_image,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embeddings from a group photo should form more than one person cluster."""
    _require_live_models()
    monkeypatch.setenv("ML_DEVICE", "cpu")
    monkeypatch.setenv("ML_EMBEDDING_MODEL", "r100")
    monkeypatch.setenv("ML_DUAL_MODEL_ENABLED", "false")
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    register_default_model_loaders()
    embedder = get_model_registry().get_model("dual_embedder")
    assert isinstance(embedder, DualEmbedder)

    crops = _aligned_crops(scrfd_detector, face_cropper, load_bgr_image, "group_photo.jpg")
    if len(crops) < 3:
        pytest.skip("group_photo.jpg did not yield three crops")
    results = embedder.embed_batch(crops)
    clustered = IncrementalClusterer(MLConfig()).cluster(
        ClusteringInput(
            new_embeddings={
                f"crop-{index}": result.primary for index, result in enumerate(results)
            },
            existing_clusters={},
            clustering_type=CLUSTER_TYPE,
        )
    )
    assert len(clustered.new_clusters) >= 2


def test_r100_adaface_agreement(
    scrfd_detector,
    face_cropper,
    load_bgr_image,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same person stays self-similar in both embedding spaces; a stranger does not."""
    _require_live_models(dual=True)
    monkeypatch.setenv("ML_DEVICE", "cpu")
    monkeypatch.setenv("ML_EMBEDDING_MODEL", "dual")
    monkeypatch.setenv("ML_DUAL_MODEL_ENABLED", "true")
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    register_default_model_loaders()
    embedder = get_model_registry().get_model("dual_embedder")
    assert isinstance(embedder, DualEmbedder)

    same_person = _aligned_crops(scrfd_detector, face_cropper, load_bgr_image, "single_face.jpg")
    others = _aligned_crops(scrfd_detector, face_cropper, load_bgr_image, "group_photo.jpg")
    if not same_person or not others:
        pytest.skip("expected crops from single_face.jpg and group_photo.jpg")

    first = embedder.embed_single(same_person[0])
    second = embedder.embed_single(same_person[0])
    stranger = embedder.embed_single(others[0])
    assert first.secondary is not None
    assert second.secondary is not None
    assert stranger.secondary is not None
    assert _cosine(first.primary, second.primary) > 0.99
    assert _cosine(first.secondary, second.secondary) > 0.99
    assert _cosine(first.primary, stranger.primary) < _cosine(first.primary, second.primary)
    assert _cosine(first.secondary, stranger.secondary) < _cosine(first.secondary, second.secondary)
