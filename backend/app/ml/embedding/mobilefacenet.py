"""MobileFaceNet TFLite CPU fallback embedding model."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import structlog

from app.ml.embedding.base import BaseEmbeddingModel, l2_normalize
from app.ml.tflite_interpreter import create_tflite_interpreter

logger = structlog.get_logger(__name__)


class MobileFaceNetTFLite(BaseEmbeddingModel):
    """Lightweight TFLite CPU fallback (~15 faces/sec on CPU)."""

    model_name = "mobilefacenet"
    INPUT_SIZE = 112

    def __init__(self, model_path: Path | str, num_threads: int | None = 4) -> None:
        """Load the preprocessed MobileFaceNet TFLite model.

        Args:
            model_path: Path to ``preprocessed_transformation_mbf_model_w12m_RE10.tflite``.
            num_threads: CPU thread count for LiteRT inference.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"MobileFaceNet TFLite weights not found: {path}")

        self._interpreter = create_tflite_interpreter(path, num_threads=num_threads)
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()
        self._model_path = path

        logger.info("mobilefacenet_tflite_loaded", model_path=str(path))

    def _preprocess(self, face_bgr: np.ndarray) -> np.ndarray:
        """Prepare a single face crop for TFLite inference.

        The PicSee model expects ``112×112×3`` float32 RGB with pixel values in
        ``[0, 255]`` (no mean/std normalization).
        """
        rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        if rgb.shape[:2] != (self.INPUT_SIZE, self.INPUT_SIZE):
            rgb = cv2.resize(rgb, (self.INPUT_SIZE, self.INPUT_SIZE))
        return rgb.astype(np.float32)

    def extract_single(self, face_bgr: np.ndarray) -> np.ndarray:
        """Sequential TFLite inference for one face."""
        input_data = self._preprocess(face_bgr)
        self._interpreter.set_tensor(self._input_details[0]["index"], input_data)
        self._interpreter.invoke()
        embedding = self._interpreter.get_tensor(self._output_details[0]["index"]).reshape(-1)
        return l2_normalize(embedding)

    def extract_batch(
        self,
        faces: list[np.ndarray],
        batch_size: int = 64,
    ) -> np.ndarray:
        """Sequential extraction — TFLite model has no batch dimension."""
        if not faces:
            return np.empty((0, self.EMBEDDING_DIM), dtype=np.float32)

        embeddings = [self.extract_single(face) for face in faces]
        return np.stack(embeddings, axis=0)

    def close(self) -> None:
        """Release interpreter reference."""
        if hasattr(self, "_interpreter"):
            del self._interpreter
        logger.debug("mobilefacenet_tflite_closed", model_path=str(self._model_path))
