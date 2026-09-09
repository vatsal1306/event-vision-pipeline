"""3DDFA_V2 ONNX head pose estimator with TFLite fallback."""

from __future__ import annotations

import os
from math import asin, atan2, cos
from pathlib import Path

import numpy as np
import structlog
import yaml

from app.ml.quality.ypr_tflite import YPRTflitePredictor
from app.ml.vendor.ypr_3ddfa_v2.FaceBoxes.FaceBoxes_ONNX import FaceBoxes_ONNX
from app.ml.vendor.ypr_3ddfa_v2.TDDFA_ONNX import TDDFA_ONNX

logger = structlog.get_logger(__name__)


class YPR3DDFAPredictor:
    """3D face reconstruction YPR estimator ported from pix-workers."""

    def __init__(
        self,
        config_path: Path | str,
        yaw_threshold: float = 45.0,
        pitch_threshold: float = 35.0,
        roll_threshold: float = 45.0,
    ) -> None:
        """Initialise FaceBoxes + ResNet22 ONNX models from a YAML config."""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"3DDFA config not found: {path}")

        with path.open("r", encoding="utf-8") as handle:
            cfg = yaml.safe_load(handle)

        config_dir = path.parent
        resolved_cfg = dict(cfg)
        for key in ("onnx_fp", "resnet_onnx", "faceboxesprod_onnx", "param_mean_std"):
            if key in resolved_cfg and resolved_cfg[key] is not None:
                candidate = Path(resolved_cfg[key])
                if not candidate.is_absolute():
                    resolved_cfg[key] = str((config_dir / candidate).resolve())

        os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "True")
        os.environ.setdefault("OMP_NUM_THREADS", "4")

        self._config_path = path
        self.yaw_threshold = yaw_threshold
        self.pitch_threshold = pitch_threshold
        self.roll_threshold = roll_threshold
        self._face_detector = FaceBoxes_ONNX(config_path=path)
        self._tddfa = TDDFA_ONNX(**resolved_cfg)

    def estimate(self, face_crop_bgr: np.ndarray) -> tuple[tuple[float, float, float] | None, bool]:
        """Estimate YPR from a BGR face crop."""
        boxes = self._face_detector(face_crop_bgr)
        if not boxes:
            logger.warning("ypr_3ddfa_no_face_detected", config_path=str(self._config_path))
            return None, False

        if len(boxes) == 1:
            top_box = [boxes[0]]
        else:
            height, width = face_crop_bgr.shape[:2]
            img_cx, img_cy = width / 2, height / 2

            def center_distance(box: list[float]) -> float:
                x1, y1, x2, y2 = box[:4]
                face_cx = (x1 + x2) / 2
                face_cy = (y1 + y2) / 2
                return (face_cx - img_cx) ** 2 + (face_cy - img_cy) ** 2

            top_box = [min(boxes, key=center_distance)]

        param_lst, _ = self._tddfa(face_crop_bgr, top_box)
        if not param_lst:
            logger.warning("ypr_3ddfa_param_estimation_failed", config_path=str(self._config_path))
            return None, False

        try:
            ypr = self._calc_pose(param_lst[0])
        except Exception as exc:
            logger.warning(
                "ypr_3ddfa_pose_error",
                config_path=str(self._config_path),
                error=str(exc),
            )
            return None, False

        return ypr, self._is_extreme(ypr)

    @staticmethod
    def _p2s_rt(projection: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        translation = projection[:, 3]
        row1 = projection[0:1, :3]
        row2 = projection[1:2, :3]
        r1 = row1 / np.linalg.norm(row1)
        r2 = row2 / np.linalg.norm(row2)
        r3 = np.cross(r1, r2)
        rotation = np.concatenate((r1, r2, r3), axis=0)
        return rotation, translation

    @staticmethod
    def _matrix_to_angle(rotation: np.ndarray) -> tuple[float, float, float]:
        if rotation[2, 0] > 0.998:
            x = np.pi / 2
            y = atan2(-rotation[0, 1], -rotation[0, 2])
            z = 0.0
        elif rotation[2, 0] < -0.998:
            x = -np.pi / 2
            y = atan2(rotation[0, 1], rotation[0, 2])
            z = 0.0
        else:
            x = asin(rotation[2, 0])
            y = atan2(rotation[2, 1] / cos(x), rotation[2, 2] / cos(x))
            z = atan2(rotation[1, 0] / cos(x), rotation[0, 0] / cos(x))
        return tuple(angle * 180 / np.pi for angle in (x, y, z))

    def _calc_pose(self, param: np.ndarray) -> tuple[float, float, float]:
        projection = param[:12].reshape(3, -1)
        rotation, _ = self._p2s_rt(projection)
        return self._matrix_to_angle(rotation)

    def _is_extreme(self, ypr: tuple[float, float, float]) -> bool:
        yaw, pitch, roll = ypr
        return (
            abs(yaw) > self.yaw_threshold
            or abs(pitch) > self.pitch_threshold
            or abs(roll) > self.roll_threshold
        )

    def close(self) -> None:
        """Release ONNX session resources (no-op placeholder for registry teardown)."""
        logger.debug("ypr_3ddfa_closed", config_path=str(self._config_path))


class YPRPredictor:
    """Unified YPR predictor with 3DDFA primary and TFLite fallback."""

    BACKEND_3DDFA = "3ddfa"
    BACKEND_TFLITE = "tflite"

    def __init__(
        self,
        *,
        model_type: str,
        config_path: Path | str,
        tflite_model_path: Path | str,
        yaw_threshold: float,
        pitch_threshold: float,
        roll_threshold: float,
    ) -> None:
        """Initialise the preferred backend and optional fallback."""
        self._primary_backend: str | None = None
        self._predictor: YPR3DDFAPredictor | YPRTflitePredictor | None = None
        self._fallback: YPRTflitePredictor | None = None
        self._init_error: str | None = None

        thresholds = {
            "yaw_threshold": yaw_threshold,
            "pitch_threshold": pitch_threshold,
            "roll_threshold": roll_threshold,
        }

        if model_type == self.BACKEND_3DDFA:
            try:
                self._predictor = YPR3DDFAPredictor(config_path=config_path, **thresholds)
                self._primary_backend = self.BACKEND_3DDFA
            except Exception as exc:
                logger.warning(
                    "ypr_3ddfa_init_failed_using_tflite",
                    config_path=str(config_path),
                    error=str(exc),
                )
                self._init_error = str(exc)
                self._predictor = YPRTflitePredictor(model_path=tflite_model_path, **thresholds)
                self._primary_backend = self.BACKEND_TFLITE
        else:
            self._predictor = YPRTflitePredictor(model_path=tflite_model_path, **thresholds)
            self._primary_backend = self.BACKEND_TFLITE

        if self._primary_backend == self.BACKEND_3DDFA:
            self._fallback = YPRTflitePredictor(model_path=tflite_model_path, **thresholds)

    @property
    def backend(self) -> str | None:
        """Return the active primary backend name."""
        return self._primary_backend

    def estimate(
        self,
        face_crop_bgr: np.ndarray,
    ) -> tuple[tuple[float, float, float] | None, bool, bool]:
        """Estimate pose with pass-on-error semantics.

        Returns:
            Tuple of ``(ypr, is_extreme, had_error)``. When ``had_error`` is ``True``,
            callers should treat the crop as passed regardless of ``is_extreme``.
        """
        if self._predictor is None:
            return None, False, True

        try:
            ypr, is_extreme = self._predictor.estimate(face_crop_bgr)
        except Exception as exc:
            logger.warning(
                "ypr_primary_inference_failed",
                backend=self._primary_backend,
                error=str(exc),
            )
            return self._run_fallback_or_error(face_crop_bgr)

        if ypr is None:
            if self._primary_backend == self.BACKEND_3DDFA:
                return None, False, True
            return self._run_fallback_or_error(face_crop_bgr)

        return ypr, is_extreme, False

    def _run_fallback_or_error(
        self,
        face_crop_bgr: np.ndarray,
    ) -> tuple[tuple[float, float, float] | None, bool, bool]:
        if self._fallback is None or self._predictor is self._fallback:
            return None, False, True
        try:
            ypr, is_extreme = self._fallback.estimate(face_crop_bgr)
        except Exception as exc:
            logger.warning("ypr_fallback_inference_failed", error=str(exc))
            return None, False, True
        return ypr, is_extreme, ypr is None

    def close(self) -> None:
        """Release underlying model resources."""
        if self._predictor is not None:
            close = getattr(self._predictor, "close", None)
            if callable(close):
                close()
        if self._fallback is not None and self._fallback is not self._predictor:
            self._fallback.close()
