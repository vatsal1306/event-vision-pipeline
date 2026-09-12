"""Tests for ML configuration."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.ml.config import MLConfig, get_ml_config


@pytest.fixture(autouse=True)
def _clear_ml_config_cache() -> None:
    """Ensure each test reads fresh ML settings."""
    get_ml_config.cache_clear()
    yield
    get_ml_config.cache_clear()


def test_ml_config_defaults_match_story_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    """Defaults should match docs/stories/ml/ML-001-ml-package-registry.md."""
    for key in list(os.environ):
        if key.startswith("ML_"):
            monkeypatch.delenv(key, raising=False)
    config = MLConfig(_env_file=None)

    assert config.device == "auto"
    assert config.models_dir == "models"
    assert config.scrfd_model == "det_10g.onnx"
    assert config.r100_model == "model_v1_scratch_training_epoch_20_r100.pt"
    assert config.adaface_model_dir == "cvlface_adaface_vit_base_kprpe_webface12m"
    assert config.dfa_aligner_dir == "cvlface_DFA_mobilenet"
    assert config.mbf_model == "preprocessed_transformation_mbf_model_w12m_RE10.tflite"
    assert config.blur_model == "blur_model_tflite_may6_ckpt49.tflite"
    assert config.ypr_tflite_model == "ypr_model_float32.tflite"
    assert config.age_model_dir == "vit-age-classifier"
    assert config.ypr_3ddfa_config == "ypr_3ddfa_v2/resnet_config.yml"
    assert config.resnet22_onnx == "resnet22.onnx"
    assert config.faceboxes_onnx == "FaceBoxesProd.onnx"
    assert config.scrfd_det_thresh == 0.5
    assert config.scrfd_nms_thresh == 0.4
    assert config.scrfd_input_sizes == [640, 128]
    assert config.blur_threshold == 0.5
    assert config.yaw_threshold == 45.0
    assert config.pitch_threshold == 35.0
    assert config.roll_threshold == 45.0
    assert config.age_min_threshold == 5
    assert config.sunglasses_threshold == 0.5
    assert config.embedding_model == "dual"
    assert config.embedding_batch_size == 64
    assert config.download_ahead == 4
    assert config.processing_progress_ttl_seconds == 86400
    assert config.dbscan_eps == 0.45
    assert config.dbscan_min_samples == 1
    assert config.agglo_threshold == 0.45
    assert config.clustering_batch_size == 5000
    assert config.sweeper_pyr_min == 47.0
    assert config.sweeper_pyr_max == 120.0
    assert config.clustering_lock_ttl_seconds == 900
    assert config.clustering_lock_retry_attempts == 6
    assert config.clustering_lock_retry_base_delay_seconds == 0.25
    assert config.orphan_crop_similarity_threshold == 0.55
    assert config.orphan_cluster_merge_threshold == 0.55
    assert config.orphan_cluster_max_size == 3
    assert config.selfie_match_threshold == 0.55
    assert config.max_cluster_matches == 5
    assert config.selfie_pgvector_min_clusters == 500
    assert config.selfie_yaw_threshold == 30.0
    assert config.selfie_pitch_threshold == 30.0
    assert config.selfie_roll_threshold == 30.0
    assert config.liveness_face_ratio_min == 0.15
    assert config.liveness_face_ratio_max == 0.85
    assert config.liveness_det_score_min == 0.7
    assert config.liveness_sharpness_min == 50.0
    assert config.liveness_saturation_min == 20.0
    assert config.ypr_model_type == "3ddfa"
    assert config.face_processing_enabled is False
    assert config.dual_model_enabled is True
    assert config.age_detection_enabled is True
    assert config.sunglasses_detection_enabled is True
    assert config.sweeper_enabled is True
    assert config.orphan_recovery_enabled is True


def test_ml_config_reads_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables with ML_ prefix override defaults."""
    monkeypatch.setenv("ML_DEVICE", "cpu")
    monkeypatch.setenv("ML_BLUR_THRESHOLD", "0.75")
    monkeypatch.setenv("ML_SCRFD_INPUT_SIZES", "[640,128]")
    monkeypatch.setenv("ML_FACE_PROCESSING_ENABLED", "true")

    config = MLConfig()

    assert config.device == "cpu"
    assert config.blur_threshold == 0.75
    assert config.scrfd_input_sizes == [640, 128]
    assert config.face_processing_enabled is True


def test_selfie_match_timeout_default_is_cpu_friendly() -> None:
    """Field default is 180s so local FastAPI first-load is not a 5s 500."""
    assert MLConfig.model_fields["selfie_match_timeout_seconds"].default == 180.0


def test_resolve_model_path_relative_and_absolute() -> None:
    """Model paths resolve relative to backend/ unless absolute."""
    config = MLConfig(models_dir="models")

    relative = config.resolve_model_path("det_10g.onnx")
    assert relative == config.backend_dir / "models" / "det_10g.onnx"

    absolute = config.resolve_model_path("/tmp/custom.onnx")
    assert absolute == Path("/tmp/custom.onnx")
