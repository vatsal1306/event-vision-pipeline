"""TFLite YPR head pose estimator (PicSee fallback)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import structlog

from app.ml.tflite_interpreter import create_tflite_interpreter

logger = structlog.get_logger(__name__)


class YPRTflitePredictor:
    """TFLite yaw/pitch/roll regressor ported from PicSee ``YPRPredictor``."""

    INPUT_SIZE = 224

    def __init__(
        self,
        model_path: Path | str,
        yaw_threshold: float = 45.0,
        pitch_threshold: float = 35.0,
        roll_threshold: float = 45.0,
    ) -> None:
        """Load the TFLite YPR model.

        Args:
            model_path: Path to ``ypr_model_float32.tflite``.
            yaw_threshold: Maximum absolute yaw in degrees.
            pitch_threshold: Maximum absolute pitch in degrees.
            roll_threshold: Maximum absolute roll in degrees.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"YPR TFLite model file not found: {path}")

        self._interpreter = create_tflite_interpreter(path)
        self._input_index = self._interpreter.get_input_details()[0]["index"]
        self._output_details = self._interpreter.get_output_details()
        self.yaw_threshold = yaw_threshold
        self.pitch_threshold = pitch_threshold
        self.roll_threshold = roll_threshold
        self._model_path = path

    def estimate(self, face_crop_bgr: np.ndarray) -> tuple[tuple[float, float, float] | None, bool]:
        """Estimate head pose and whether it exceeds configured thresholds.

        Args:
            face_crop_bgr: BGR face crop (any size; resized internally to 224×224).

        Returns:
            Tuple of ``(ypr, is_extreme)`` where ``ypr`` is ``(yaw, pitch, roll)`` or
            ``None`` when inference fails.
        """
        img_resized = cv2.resize(face_crop_bgr, (self.INPUT_SIZE, self.INPUT_SIZE))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB).astype(np.float32)
        input_data = np.expand_dims(img_rgb, axis=0)

        self._interpreter.set_tensor(self._input_index, input_data)
        self._interpreter.invoke()

        outputs: dict[str, float] = {}
        for detail in self._output_details:
            name = detail["name"]
            value = self._interpreter.get_tensor(detail["index"])[0]
            outputs[name] = float(value)

        pitch = outputs.get("pitch")
        roll = outputs.get("roll")
        yaw = outputs.get("yaw")
        if pitch is None or roll is None or yaw is None:
            logger.warning(
                "ypr_tflite_missing_outputs",
                model_path=str(self._model_path),
                outputs=list(outputs.keys()),
            )
            return None, False

        ypr = (yaw, pitch, roll)
        is_extreme = self._is_extreme(ypr)
        return ypr, is_extreme

    def _is_extreme(self, ypr: tuple[float, float, float]) -> bool:
        yaw, pitch, roll = ypr
        return (
            abs(yaw) > self.yaw_threshold
            or abs(pitch) > self.pitch_threshold
            or abs(roll) > self.roll_threshold
        )

    def close(self) -> None:
        """Release interpreter resources (no-op for TFLite)."""
        logger.debug("ypr_tflite_closed", model_path=str(self._model_path))
