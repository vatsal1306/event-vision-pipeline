"""ML pipeline configuration.

All ML thresholds, model paths, and processing parameters are loaded from
environment variables (prefixed with ``ML_``). This allows operators to
tune the pipeline without code changes.

See ``docs/component_ai_ml.md`` §11.2 for the full parameter reference.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Resolve the backend root so relative model paths work regardless of cwd.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class MLConfig(BaseSettings):
    """ML pipeline configuration loaded from environment variables.

    Every field can be overridden by setting the corresponding ``ML_*``
    environment variable (e.g. ``ML_DEVICE=cpu``).

    Attributes:
        device: Compute device — ``"cuda"`` or ``"cpu"``.  Auto-detected
            if not explicitly set.
        scrfd_model_path: Path to the SCRFD ONNX model file.
        embedding_model: Which embedding model to use (``"r100"`` or ``"mbf"``).
        embedding_model_path: Path to the primary embedding model weights.
        blur_model_path: Path to the TFLite blur classifier.
        ypr_model_path: Path to the TFLite head-pose estimator.
        blur_threshold: Blur score below this is rejected (lower = blurrier).
        yaw_threshold: Maximum absolute yaw in degrees.
        pitch_threshold: Maximum absolute pitch in degrees.
        roll_threshold: Maximum absolute roll in degrees.
        dbscan_eps: DBSCAN epsilon for cosine distance.
        agglo_threshold: Agglomerative clustering distance threshold.
        clustering_batch_size: Max embeddings per clustering run.
        selfie_match_threshold: Cosine similarity threshold for selfie matching.
        max_cluster_matches: Maximum clusters returned per selfie match.
        embedding_batch_size: Faces per GPU forward pass.
    """

    # ── Device ───────────────────────────────────────────────────────
    device: str = "cpu"

    # ── Model paths ──────────────────────────────────────────────────
    scrfd_model_path: str = "models/det_10g.onnx"
    embedding_model: str = "r100"
    embedding_model_path: str = "models/model_v1_scratch_training_epoch_20_r100.pt"
    blur_model_path: str = "models/blur_model_tflite_may6_ckpt49.tflite"
    ypr_model_path: str = "models/ypr_model_float32.tflite"

    # ── Quality thresholds ───────────────────────────────────────────
    blur_threshold: float = 0.5
    yaw_threshold: float = 45.0
    pitch_threshold: float = 35.0
    roll_threshold: float = 45.0

    # ── Clustering ───────────────────────────────────────────────────
    dbscan_eps: float = 0.45
    agglo_threshold: float = 0.45
    clustering_batch_size: int = 5000

    # ── Matching ─────────────────────────────────────────────────────
    selfie_match_threshold: float = 0.55
    max_cluster_matches: int = 5

    # ── Processing ───────────────────────────────────────────────────
    embedding_batch_size: int = 64

    model_config = {
        "env_prefix": "ML_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    # ── Validators ───────────────────────────────────────────────────

    @field_validator("device", mode="before")
    @classmethod
    def _detect_device(cls, v: str) -> str:
        """Auto-detect CUDA availability when device is explicitly ``"cuda"``.

        If ``torch`` is not installed or CUDA is unavailable the device
        silently falls back to ``"cpu"`` — this keeps the config importable
        in environments that lack a GPU (e.g. API workers, CI).
        """
        if v == "cuda":
            try:
                import torch

                if not torch.cuda.is_available():
                    logger.warning("cuda_requested_but_unavailable, falling back to cpu")
                    return "cpu"
            except ImportError:
                logger.warning("torch_not_installed, falling back to cpu")
                return "cpu"
        return v

    @field_validator(
        "scrfd_model_path",
        "embedding_model_path",
        "blur_model_path",
        "ypr_model_path",
        mode="before",
    )
    @classmethod
    def _resolve_model_path(cls, v: str) -> str:
        """Resolve relative model paths against the backend root directory."""
        path = Path(v)
        if not path.is_absolute():
            path = _BACKEND_ROOT / path
        return str(path)

    @field_validator("embedding_model", mode="before")
    @classmethod
    def _validate_embedding_model(cls, v: str) -> str:
        """Ensure the embedding model name is one of the supported choices."""
        allowed = {"r100", "mbf"}
        if v not in allowed:
            msg = f"embedding_model must be one of {allowed}, got {v!r}"
            raise ValueError(msg)
        return v


@lru_cache(maxsize=1)
def get_ml_config() -> MLConfig:
    """Return the singleton ``MLConfig`` instance.

    The config is created once and cached for the lifetime of the process.
    """
    config = MLConfig()
    logger.info(
        "ml_config_loaded",
        extra={
            "device": config.device,
            "embedding_model": config.embedding_model,
            "blur_threshold": config.blur_threshold,
            "selfie_match_threshold": config.selfie_match_threshold,
        },
    )
    return config
