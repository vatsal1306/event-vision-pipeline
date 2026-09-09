"""Integration tests for dual-model face embeddings."""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.config import get_ml_config
from app.ml.embedding.dual_embedder import DualEmbedder
from app.ml.model_registry import ModelRegistry, get_model_registry
from app.ml.registry_bootstrap import register_default_model_loaders
from tests.ml.conftest import (
    adaface_models_available,
    embedding_models_available,
    mbf_model_available,
    run_ml_integration_tests,
)

pytestmark = pytest.mark.ml
pytest.importorskip("torch")


@pytest.fixture
def embedding_registry(monkeypatch: pytest.MonkeyPatch):
    """Fresh registry with embedding loaders and CPU device."""
    monkeypatch.setenv("ML_DEVICE", "cpu")
    register_default_model_loaders()
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    registry = get_model_registry()
    yield registry
    registry.unload_all()
    ModelRegistry.reset_for_tests()
    get_ml_config.cache_clear()


@pytest.fixture
def face_crops(scrfd_detector, face_cropper, load_bgr_image):
    """Aligned face crops from the single-face fixture."""
    image = load_bgr_image("single_face.jpg")
    faces = scrfd_detector.detect(image)
    crops = face_cropper.crop_all(image, faces)
    assert crops, "Expected at least one crop from single_face fixture"
    return [crop.aligned_face for crop in crops]


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def test_r100_embeddings_are_deterministic_and_normalized(
    embedding_registry,
    face_crops,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same crop embedded twice should yield cosine similarity ≈ 1.0."""
    if not run_ml_integration_tests():
        pytest.skip("RUN_ML_TESTS!=1")
    if not embedding_models_available():
        pytest.skip("Embedding model files missing")

    monkeypatch.setenv("ML_EMBEDDING_MODEL", "r100")
    monkeypatch.setenv("ML_DUAL_MODEL_ENABLED", "false")
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    register_default_model_loaders()
    registry = get_model_registry()

    embedder = registry.get_model("dual_embedder")
    assert isinstance(embedder, DualEmbedder)
    assert embedder.mode == "r100"

    first = embedder.embed_batch(face_crops)
    second = embedder.embed_batch(face_crops)

    assert len(first) == len(face_crops)
    for result_a, result_b in zip(first, second):
        assert result_a.primary.shape == (512,)
        assert result_a.secondary is None
        assert abs(np.linalg.norm(result_a.primary) - 1.0) < 1e-4
        assert _cosine_similarity(result_a.primary, result_b.primary) > 0.999


def test_dual_embeddings_primary_and_secondary(
    embedding_registry,
    face_crops,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dual mode should produce both primary and secondary embeddings."""
    if not run_ml_integration_tests():
        pytest.skip("RUN_ML_TESTS!=1")
    if not embedding_models_available() or not adaface_models_available():
        pytest.skip("Dual embedding model files missing")

    monkeypatch.setenv("ML_EMBEDDING_MODEL", "dual")
    monkeypatch.setenv("ML_DUAL_MODEL_ENABLED", "true")
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    register_default_model_loaders()
    registry = get_model_registry()

    embedder = registry.get_model("dual_embedder")
    assert isinstance(embedder, DualEmbedder)
    assert embedder.mode == "dual"

    results = embedder.embed_batch(face_crops)
    assert len(results) == len(face_crops)

    for result in results:
        assert result.primary.shape == (512,)
        assert result.secondary is not None
        assert result.secondary.shape == (512,)
        assert abs(np.linalg.norm(result.primary) - 1.0) < 1e-4
        assert abs(np.linalg.norm(result.secondary) - 1.0) < 1e-4
        assert result.model_primary == "r100"
        assert result.model_secondary == "adaface_vit_kprpe"


def test_mobilefacenet_runs_without_cuda(
    embedding_registry,
    face_crops,
) -> None:
    """MobileFaceNet TFLite path should run on CPU without torch CUDA."""
    if not run_ml_integration_tests():
        pytest.skip("RUN_ML_TESTS!=1")
    if not mbf_model_available():
        pytest.skip("MobileFaceNet TFLite model file missing")

    mbf = embedding_registry.get_model("mobilefacenet")
    embeddings = mbf.extract_batch(face_crops)

    assert embeddings.shape == (len(face_crops), 512)
    norms = np.linalg.norm(embeddings, axis=1)
    np.testing.assert_allclose(norms, 1.0, rtol=1e-4)


def test_dual_embedder_secondary_omitted_on_failure(
    face_crops,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When secondary model fails, primary embeddings should still be returned."""
    if not run_ml_integration_tests():
        pytest.skip("RUN_ML_TESTS!=1")
    if not embedding_models_available():
        pytest.skip("Embedding model files missing")

    monkeypatch.setenv("ML_DEVICE", "cpu")
    monkeypatch.setenv("ML_EMBEDDING_MODEL", "dual")
    monkeypatch.setenv("ML_DUAL_MODEL_ENABLED", "true")
    get_ml_config.cache_clear()
    ModelRegistry.reset_for_tests()
    register_default_model_loaders()
    registry = get_model_registry()

    primary = registry.get_model("arcface_r100")
    fallback = registry.get_model("mobilefacenet")

    class BrokenSecondary:
        model_name = "adaface_vit_kprpe"

        def extract_batch(self, faces: list[np.ndarray], batch_size: int = 64) -> np.ndarray:
            raise RuntimeError("simulated secondary failure")

        def close(self) -> None:
            return None

    embedder = DualEmbedder(
        primary=primary,
        secondary=BrokenSecondary(),
        fallback=fallback,
        config=get_ml_config(),
    )

    results = embedder.embed_batch(face_crops)
    assert len(results) == len(face_crops)
    for result in results:
        assert result.primary.shape == (512,)
        assert result.secondary is None
