"""Thread-safe singleton model loader and cache.

The ``ModelRegistry`` ensures each ML model is loaded exactly **once** per
process and shared across all Celery tasks within that process.  Models are
loaded lazily on first access — importing this module does **not** trigger
GPU memory allocation.

Usage in Celery workers / tests::

    registry = ModelRegistry.get_instance()
    detector = registry.get_detector()
    embedder = registry.get_embedder()

API (FastAPI) processes should **never** call ``get_detector()`` or other
model accessors.  Use ``get_face_service()`` only from worker code.

See ``docs/component_ai_ml.md`` §11.1 for the design rationale.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from app.ml.config import get_ml_config

if TYPE_CHECKING:
    from app.ml.config import MLConfig

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Singleton model loader and cache.

    Loads models lazily on first use and caches them in memory.
    Each Celery worker process gets its own model instances.

    The double-checked locking pattern ensures thread safety without
    acquiring the lock on the fast path (subsequent accesses).
    """

    _instance: ModelRegistry | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._models: dict[str, Any] = {}
        self._config: MLConfig = get_ml_config()

    # ── Singleton accessor ───────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> ModelRegistry:
        """Return the singleton ``ModelRegistry``, creating it on first call.

        Uses double-checked locking for thread safety without contention
        on the hot path.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    logger.info("model_registry_initialising")
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Destroy the singleton (test helper).

        This is only intended for use in tests — it releases any loaded
        models and allows ``get_instance`` to create a fresh registry.
        """
        with cls._lock:
            cls._instance = None

    # ── Model accessors (lazy loading) ───────────────────────────────

    def get_detector(self) -> Any:
        """Return the SCRFD face detector, loading it on first call.

        Returns:
            An ``SCRFDDetector`` instance.
        """
        if "detector" not in self._models:
            logger.info("loading_scrfd_detector", extra={"path": self._config.scrfd_model_path})

            from app.ml.detection.scrfd import SCRFDDetector

            self._models["detector"] = SCRFDDetector(
                model_path=self._config.scrfd_model_path,
                device=self._config.device,
            )
        return self._models["detector"]

    def get_embedder(self) -> Any:
        """Return the face embedding model, loading it on first call.

        The concrete model class is determined by ``MLConfig.embedding_model``
        (``"r100"`` → InsightFace R100, ``"mbf"`` → MobileFaceNet).

        Returns:
            A ``BaseEmbeddingModel`` subclass instance.
        """
        if "embedder" not in self._models:
            logger.info(
                "loading_embedding_model",
                extra={
                    "model": self._config.embedding_model,
                    "path": self._config.embedding_model_path,
                },
            )

            if self._config.embedding_model == "r100":
                from app.ml.embedding.insightface_r100 import InsightFaceR100

                self._models["embedder"] = InsightFaceR100(
                    model_path=self._config.embedding_model_path,
                    device=self._config.device,
                )
            elif self._config.embedding_model == "mbf":
                from app.ml.embedding.mobilefacenet import MobileFaceNet

                self._models["embedder"] = MobileFaceNet(
                    model_path=self._config.embedding_model_path,
                )
            else:
                msg = f"Unsupported embedding model: {self._config.embedding_model}"
                raise ValueError(msg)

        return self._models["embedder"]

    def get_quality_filter(self) -> Any:
        """Return the quality filter (blur + head-pose), loading on first call.

        Returns:
            A ``QualityFilter`` instance composed of blur and pose estimators.
        """
        if "quality_filter" not in self._models:
            logger.info("loading_quality_filter")

            from app.ml.quality.blur_detector import BlurDetector
            from app.ml.quality.pose_estimator import PoseEstimator

            blur = BlurDetector(
                model_path=self._config.blur_model_path,
                threshold=self._config.blur_threshold,
            )
            pose = PoseEstimator(
                model_path=self._config.ypr_model_path,
                yaw_thresh=self._config.yaw_threshold,
                pitch_thresh=self._config.pitch_threshold,
                roll_thresh=self._config.roll_threshold,
            )
            from app.ml.quality import QualityFilter

            self._models["quality_filter"] = QualityFilter(blur=blur, pose=pose)

        return self._models["quality_filter"]

    def get_face_service(self) -> Any:
        """Return a fully configured ``FaceService`` with all models loaded.

        This is the main entry point for Celery workers — it wires together
        detection, embedding, quality filtering, clustering, matching, and
        liveness into a single orchestrator.

        Returns:
            A ``FaceService`` instance.
        """
        if "face_service" not in self._models:
            logger.info("building_face_service")

            from app.ml.clustering.incremental_clusterer import IncrementalClusterer
            from app.ml.liveness.basic_liveness import BasicLivenessDetector
            from app.ml.matching.selfie_matcher import SelfieMatcher
            from app.services.face_service import FaceService

            self._models["face_service"] = FaceService(
                detector=self.get_detector(),
                embedder=self.get_embedder(),
                quality_filter=self.get_quality_filter(),
                clusterer=IncrementalClusterer(),
                matcher=SelfieMatcher(
                    detector=self.get_detector(),
                    embedder=self.get_embedder(),
                    quality_filter=self.get_quality_filter(),
                ),
                liveness=BasicLivenessDetector(),
            )

        return self._models["face_service"]


def get_face_service() -> Any:
    """Convenience accessor for ``ModelRegistry.get_instance().get_face_service()``.

    Use from Celery tasks and tests only — not from API route handlers.
    """
    return ModelRegistry.get_instance().get_face_service()
