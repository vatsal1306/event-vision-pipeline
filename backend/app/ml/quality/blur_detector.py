"""TFLite blur classifier for face crops."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import structlog
import tensorflow as tf

logger = structlog.get_logger(__name__)


class BlurDetector:
    """TFLite blur classifier ported from PicSee ``FaceModel_blur_detector``.

    The model outputs a blur score in ``[0, 1]`` where **higher values indicate
    more blur**. Faces with scores above ``blur_threshold`` are rejected.
    """

    INPUT_SIZE = 112

    def __init__(self, model_path: Path | str, threshold: float = 0.5) -> None:
        """Load the blur TFLite model.

        Args:
            model_path: Path to ``blur_model_tflite_may6_ckpt49.tflite``.
            threshold: Reject crops whose blur score exceeds this value.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Blur model file not found: {path}")

        self._interpreter = tf.lite.Interpreter(model_path=str(path))
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()
        self.threshold = threshold
        self._model_path = path

    def score(self, face_crop_bgr: np.ndarray) -> float:
        """Return the blur score for a BGR face crop.

        Args:
            face_crop_bgr: ``112×112`` BGR numpy array.

        Returns:
            Blur score in ``[0, 1]`` (higher = blurrier).
        """
        input_tensor = self._preprocess(face_crop_bgr)
        self._interpreter.set_tensor(self._input_details[0]["index"], input_tensor)
        self._interpreter.invoke()
        output_data = self._interpreter.get_tensor(self._output_details[0]["index"])
        return float(output_data.reshape(-1)[0])

    def is_blurry(self, face_crop_bgr: np.ndarray) -> tuple[bool, float]:
        """Check whether a crop exceeds the blur threshold.

        Returns:
            Tuple of ``(is_blurry, blur_score)``.
        """
        blur_score = self.score(face_crop_bgr)
        return blur_score > self.threshold, blur_score

    def _preprocess(self, face_crop_bgr: np.ndarray) -> np.ndarray:
        if face_crop_bgr is None:
            raise ValueError("Input face crop is None")

        rgb = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2RGB)
        if rgb.shape[:2] != (self.INPUT_SIZE, self.INPUT_SIZE):
            rgb = cv2.resize(rgb, (self.INPUT_SIZE, self.INPUT_SIZE))

        tensor = np.transpose(np.expand_dims(rgb, axis=0), (0, 3, 1, 2)).astype(np.float32) / 255.0
        return tensor

    def close(self) -> None:
        """Release interpreter resources (no-op for TFLite, kept for symmetry)."""
        logger.debug("blur_detector_closed", model_path=str(self._model_path))
