"""ML pipeline configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class MLConfig(BaseSettings):
    """Centralised ML thresholds, model paths, and feature flags.

    All settings are overridable via environment variables with the ``ML_`` prefix.
    For example, ``ML_BLUR_THRESHOLD=0.6`` sets ``blur_threshold``.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="ML_",
        extra="ignore",
    )

    # Device
    device: str = "auto"

    # Model paths (relative to backend/ unless absolute)
    models_dir: str = "models"
    scrfd_model: str = "det_10g.onnx"
    r100_model: str = "model_v1_scratch_training_epoch_20_r100.pt"
    adaface_model_dir: str = "cvlface_adaface_vit_base_kprpe_webface12m"
    dfa_aligner_dir: str = "cvlface_DFA_mobilenet"
    mbf_model: str = "preprocessed_transformation_mbf_model_w12m_RE10.tflite"
    blur_model: str = "blur_model_tflite_may6_ckpt49.tflite"
    ypr_tflite_model: str = "ypr_model_float32.tflite"
    ypr_3ddfa_config: str = "ypr_3ddfa_v2/resnet_config.yml"
    resnet22_onnx: str = "resnet22.onnx"
    faceboxes_onnx: str = "FaceBoxesProd.onnx"

    # Detection
    scrfd_det_thresh: float = 0.5
    scrfd_nms_thresh: float = 0.4
    scrfd_input_sizes: list[int] = Field(default_factory=lambda: [640, 128])

    # Quality thresholds
    blur_threshold: float = 0.5
    yaw_threshold: float = 45.0
    pitch_threshold: float = 35.0
    roll_threshold: float = 45.0
    age_min_threshold: int = 5
    sunglasses_threshold: float = 0.5

    # Embedding
    embedding_model: str = "dual"
    embedding_batch_size: int = 64

    # Clustering
    dbscan_eps: float = 0.45
    dbscan_min_samples: int = 1
    agglo_threshold: float = 0.45
    clustering_batch_size: int = 5000
    sweeper_pyr_min: float = 47.0
    sweeper_pyr_max: float = 120.0

    # Selfie matching
    selfie_match_threshold: float = 0.55
    max_cluster_matches: int = 5

    # Liveness
    liveness_face_ratio_min: float = 0.15
    liveness_face_ratio_max: float = 0.85
    liveness_det_score_min: float = 0.7
    liveness_sharpness_min: float = 50.0
    liveness_saturation_min: float = 20.0

    # YPR model
    ypr_model_type: str = "3ddfa"

    # Feature flags
    face_processing_enabled: bool = False
    dual_model_enabled: bool = True
    age_detection_enabled: bool = True
    sunglasses_detection_enabled: bool = True
    sweeper_enabled: bool = True
    orphan_recovery_enabled: bool = True

    # Registry behaviour
    strict_worker_only: bool = False
    warn_on_non_worker_load: bool = True

    @field_validator("scrfd_input_sizes", mode="before")
    @classmethod
    def _parse_scrfd_input_sizes(cls, value: object) -> list[int]:
        """Accept JSON-style list strings from environment variables."""
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned.startswith("[") and cleaned.endswith("]"):
                inner = cleaned[1:-1].strip()
                if not inner:
                    return []
                return [int(part.strip()) for part in inner.split(",") if part.strip()]
            return [int(cleaned)]
        if isinstance(value, (list, tuple)):
            return [int(item) for item in value]
        raise TypeError("scrfd_input_sizes must be a list of integers or a JSON list string")

    @property
    def backend_dir(self) -> Path:
        """Absolute path to the backend project root."""
        return _BACKEND_DIR

    @property
    def models_path(self) -> Path:
        """Absolute path to the directory containing model weight files."""
        path = Path(self.models_dir)
        if path.is_absolute():
            return path
        return _BACKEND_DIR / path

    def resolve_model_path(self, filename: str) -> Path:
        """Resolve a model filename relative to ``models_path``.

        Args:
            filename: Model file or subdirectory path relative to ``models_path``.

        Returns:
            Absolute filesystem path to the model asset.
        """
        candidate = Path(filename)
        if candidate.is_absolute():
            return candidate
        return self.models_path / candidate

    @property
    def scrfd_model_path(self) -> Path:
        """Absolute path to the SCRFD ONNX detector weights."""
        return self.resolve_model_path(self.scrfd_model)

    @property
    def r100_model_path(self) -> Path:
        """Absolute path to the ArcFace R100 PyTorch weights."""
        return self.resolve_model_path(self.r100_model)

    @property
    def adaface_model_path(self) -> Path:
        """Absolute path to the AdaFace model directory."""
        return self.resolve_model_path(self.adaface_model_dir)

    @property
    def dfa_aligner_path(self) -> Path:
        """Absolute path to the DFA Mobilenet aligner directory."""
        return self.resolve_model_path(self.dfa_aligner_dir)

    @property
    def mbf_model_path(self) -> Path:
        """Absolute path to the MobileFaceNet TFLite weights."""
        return self.resolve_model_path(self.mbf_model)

    @property
    def blur_model_path(self) -> Path:
        """Absolute path to the blur classifier TFLite weights."""
        return self.resolve_model_path(self.blur_model)

    @property
    def ypr_tflite_model_path(self) -> Path:
        """Absolute path to the TFLite YPR fallback weights."""
        return self.resolve_model_path(self.ypr_tflite_model)

    @property
    def ypr_3ddfa_config_path(self) -> Path:
        """Absolute path to the 3DDFA_V2 YAML config."""
        return self.resolve_model_path(self.ypr_3ddfa_config)

    @property
    def resnet22_onnx_path(self) -> Path:
        """Absolute path to the 3DDFA_V2 ResNet22 ONNX weights."""
        return self.resolve_model_path(self.resnet22_onnx)

    @property
    def faceboxes_onnx_path(self) -> Path:
        """Absolute path to the FaceBoxes ONNX weights."""
        return self.resolve_model_path(self.faceboxes_onnx)


@lru_cache
def get_ml_config() -> MLConfig:
    """Return the cached ML configuration instance."""
    return MLConfig()
