"""SCRFD multi-scale face detector using ONNX Runtime."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from app.ml.detection.onnx_providers import get_onnxruntime_providers
from app.ml.detection.types import DetectedFace

ort.set_default_logger_severity(3)


class SCRFDDetector:
    """SCRFD face detector with multi-scale autodetect (640 + 128).

    Ported from pix-workers ``SCRFD`` for PicSee production parity.
    """

    DEFAULT_DET_THRESH = 0.5
    NMS_THRESH = 0.4
    INPUT_SIZES = [640, 128]

    def __init__(
        self,
        model_path: Path | str,
        device: str = "cpu",
        det_thresh: float = DEFAULT_DET_THRESH,
        nms_thresh: float = NMS_THRESH,
        input_sizes: list[int] | None = None,
    ) -> None:
        """Initialise the ONNX SCRFD session.

        Args:
            model_path: Path to ``det_10g.onnx``.
            device: Resolved device string (``cuda``, ``mps``, ``cpu``).
            det_thresh: Minimum detection confidence.
            nms_thresh: Non-maximum suppression IoU threshold.
            input_sizes: Multi-scale input sizes (default ``[640, 128]``).
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"SCRFD model file not found: {path}")

        providers = get_onnxruntime_providers(device)
        self._session = ort.InferenceSession(str(path), providers=providers)
        self._model_path = path
        self._device = device
        self.det_thresh = det_thresh
        self.nms_thresh = nms_thresh
        self.input_sizes = input_sizes or self.INPUT_SIZES

        self._batched = False
        self._center_cache: dict[tuple[int, int, int], np.ndarray] = {}
        self._init_model_vars()

    def _init_model_vars(self) -> None:
        """Parse ONNX model metadata (strides, keypoints, anchors)."""
        input_cfg = self._session.get_inputs()[0]
        input_shape = input_cfg.shape
        if isinstance(input_shape[2], str):
            self._input_size: tuple[int, int] | None = None
        else:
            self._input_size = tuple(input_shape[2:4][::-1])

        self._input_name = input_cfg.name
        outputs = self._session.get_outputs()
        if len(outputs[0].shape) == 3:
            self._batched = True
        self._output_names = [output.name for output in outputs]

        self._input_mean = 127.5
        self._input_std = 128.0
        self._use_kps = False
        self._num_anchors = 1
        output_count = len(outputs)

        if output_count == 6:
            self._fmc = 3
            self._feat_stride_fpn = [8, 16, 32]
            self._num_anchors = 2
        elif output_count == 9:
            self._fmc = 3
            self._feat_stride_fpn = [8, 16, 32]
            self._num_anchors = 2
            self._use_kps = True
        elif output_count == 10:
            self._fmc = 5
            self._feat_stride_fpn = [8, 16, 32, 64, 128]
        elif output_count == 15:
            self._fmc = 5
            self._feat_stride_fpn = [8, 16, 32, 64, 128]
            self._use_kps = True
        else:
            raise ValueError(f"Unsupported SCRFD ONNX output count: {output_count}")

    def close(self) -> None:
        """Release ONNX session resources."""
        del self._session

    def detect(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        """Detect all faces in a BGR image using multi-scale SCRFD.

        Args:
            image_bgr: BGR image from ``cv2.imdecode``.

        Returns:
            Detected faces with normalized bbox, pixel bbox, landmarks, and score.
        """
        if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
            raise ValueError("Expected a BGR image with shape (H, W, 3).")

        bboxes, keypoints = self._autodetect(image_bgr, max_num=0)
        if bboxes.size == 0:
            return []

        image_height, image_width = image_bgr.shape[:2]
        detections: list[DetectedFace] = []
        for index, raw_bbox in enumerate(bboxes):
            x1, y1, x2, y2, score = raw_bbox
            landmarks = (
                keypoints[index].astype(np.float32)
                if keypoints is not None and keypoints.shape[0] > index
                else np.zeros((5, 2), dtype=np.float32)
            )
            detections.append(
                self._to_detected_face(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    score=float(score),
                    landmarks=landmarks,
                    image_width=image_width,
                    image_height=image_height,
                )
            )
        return detections

    def detect_at_scale(
        self,
        image_bgr: np.ndarray,
        input_size: int,
        max_num: int = 0,
    ) -> list[DetectedFace]:
        """Run detection at a single scale (used for multi-scale regression tests)."""
        bboxes, keypoints = self._detect(
            image_bgr,
            input_size=(input_size, input_size),
            thresh=self.det_thresh,
            max_num=max_num,
        )
        if bboxes.size == 0:
            return []

        image_height, image_width = image_bgr.shape[:2]
        detections: list[DetectedFace] = []
        for index, raw_bbox in enumerate(bboxes):
            x1, y1, x2, y2, score = raw_bbox
            landmarks = (
                keypoints[index].astype(np.float32)
                if keypoints is not None and keypoints.shape[0] > index
                else np.zeros((5, 2), dtype=np.float32)
            )
            detections.append(
                self._to_detected_face(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    score=float(score),
                    landmarks=landmarks,
                    image_width=image_width,
                    image_height=image_height,
                )
            )
        return detections

    @staticmethod
    def _to_detected_face(
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        score: float,
        landmarks: np.ndarray,
        image_width: int,
        image_height: int,
    ) -> DetectedFace:
        """Convert raw SCRFD box coordinates to clipped ``DetectedFace`` values."""
        clipped_x1 = float(np.clip(x1, 0, image_width))
        clipped_y1 = float(np.clip(y1, 0, image_height))
        clipped_x2 = float(np.clip(x2, 0, image_width))
        clipped_y2 = float(np.clip(y2, 0, image_height))
        width = max(clipped_x2 - clipped_x1, 0.0)
        height = max(clipped_y2 - clipped_y1, 0.0)
        bbox_pixel = np.array([clipped_x1, clipped_y1, width, height], dtype=np.float32)
        bbox_normalized = np.array(
            [
                clipped_x1 / image_width,
                clipped_y1 / image_height,
                width / image_width,
                height / image_height,
            ],
            dtype=np.float32,
        )
        return DetectedFace(
            bbox=bbox_normalized,
            bbox_pixel=bbox_pixel,
            landmarks=landmarks,
            score=score,
        )

    def _autodetect(
        self,
        image_bgr: np.ndarray,
        max_num: int = 0,
        metric: str = "default",
    ) -> tuple[np.ndarray, np.ndarray | None]:
        """Multi-scale detection matching pix-workers ``SCRFD.autodetect``."""
        if len(self.input_sizes) < 2:
            return self._detect(
                image_bgr,
                input_size=(self.input_sizes[0], self.input_sizes[0]),
                thresh=self.det_thresh,
                max_num=max_num,
                metric=metric,
            )

        primary_size, secondary_size = self.input_sizes[0], self.input_sizes[1]
        det_primary, kps_primary = self._detect(
            image_bgr,
            input_size=(primary_size, primary_size),
            thresh=self.det_thresh,
            max_num=0,
        )
        det_secondary, kps_secondary = self._detect(
            image_bgr,
            input_size=(secondary_size, secondary_size),
            thresh=self.det_thresh,
            max_num=0,
        )

        if det_primary.shape[0] == 0 and det_secondary.shape[0] == 0:
            return np.array([]), None
        if det_primary.shape[0] > 0 and det_secondary.shape[0] == 0:
            bboxes_all, kpss_all = det_primary, kps_primary
        elif det_primary.shape[0] == 0 and det_secondary.shape[0] > 0:
            bboxes_all, kpss_all = det_secondary, kps_secondary
        else:
            bboxes_all = np.concatenate([det_primary, det_secondary], axis=0)
            if self._use_kps and kps_primary is not None and kps_secondary is not None:
                kpss_all = np.concatenate([kps_primary, kps_secondary], axis=0)
            else:
                kpss_all = None

        keep = self._nms(bboxes_all)
        bboxes_all = bboxes_all[keep, :]
        if self._use_kps and kpss_all is not None:
            kpss_all = kpss_all[keep, :, :]

        if max_num > 0 and bboxes_all.shape[0] > max_num:
            bboxes_all, kpss_all = self._select_top_faces(
                image_bgr,
                bboxes_all,
                kpss_all,
                max_num=max_num,
                metric=metric,
            )
        return bboxes_all, kpss_all

    def _detect(
        self,
        image_bgr: np.ndarray,
        input_size: tuple[int, int],
        thresh: float,
        max_num: int = 0,
        metric: str = "default",
    ) -> tuple[np.ndarray, np.ndarray | None]:
        """Single-scale SCRFD detection."""
        image_ratio = float(image_bgr.shape[0]) / image_bgr.shape[1]
        model_ratio = float(input_size[1]) / input_size[0]
        if image_ratio > model_ratio:
            new_height = input_size[1]
            new_width = int(new_height / image_ratio)
        else:
            new_width = input_size[0]
            new_height = int(new_width * image_ratio)
        scale = float(new_height) / image_bgr.shape[0]

        resized = cv2.resize(image_bgr, (new_width, new_height))
        det_image = np.zeros((input_size[1], input_size[0], 3), dtype=np.uint8)
        det_image[:new_height, :new_width, :] = resized

        scores_list, bboxes_list, kpss_list = self._forward(det_image, thresh)
        scores = np.vstack(scores_list)
        order = scores.ravel().argsort()[::-1]
        bboxes = np.vstack(bboxes_list) / scale
        keypoints = np.vstack(kpss_list) / scale if self._use_kps else None

        pre_det = np.hstack((bboxes, scores)).astype(np.float32, copy=False)
        pre_det = pre_det[order, :]
        keep = self._nms(pre_det)
        det = pre_det[keep, :]
        if self._use_kps and keypoints is not None:
            keypoints = keypoints[order, :, :]
            keypoints = keypoints[keep, :, :]

        if max_num > 0 and det.shape[0] > max_num:
            det, keypoints = self._select_top_faces(
                image_bgr,
                det,
                keypoints,
                max_num=max_num,
                metric=metric,
            )
        return det, keypoints

    def _forward(
        self,
        image_bgr: np.ndarray,
        threshold: float,
    ) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray]]:
        """Run ONNX forward pass at the current padded resolution."""
        height, width = image_bgr.shape[:2]
        blob = cv2.dnn.blobFromImage(
            image_bgr,
            scalefactor=1.0 / self._input_std,
            size=(width, height),
            mean=(self._input_mean, self._input_mean, self._input_mean),
            swapRB=True,
        )
        net_outputs = self._session.run(self._output_names, {self._input_name: blob})

        input_height = blob.shape[2]
        input_width = blob.shape[3]
        scores_list: list[np.ndarray] = []
        bboxes_list: list[np.ndarray] = []
        kpss_list: list[np.ndarray] = []

        for index, stride in enumerate(self._feat_stride_fpn):
            if self._batched:
                scores = net_outputs[index][0]
                bbox_preds = net_outputs[index + self._fmc][0] * stride
                kps_preds = (
                    net_outputs[index + self._fmc * 2][0] * stride if self._use_kps else None
                )
            else:
                scores = net_outputs[index]
                bbox_preds = net_outputs[index + self._fmc] * stride
                kps_preds = net_outputs[index + self._fmc * 2] * stride if self._use_kps else None

            grid_height = input_height // stride
            grid_width = input_width // stride
            cache_key = (grid_height, grid_width, stride)
            if cache_key in self._center_cache:
                anchor_centers = self._center_cache[cache_key]
            else:
                anchor_centers = np.stack(
                    np.mgrid[:grid_height, :grid_width][::-1],
                    axis=-1,
                ).astype(np.float32)
                anchor_centers = (anchor_centers * stride).reshape((-1, 2))
                if self._num_anchors > 1:
                    anchor_centers = np.stack([anchor_centers] * self._num_anchors, axis=1)
                    anchor_centers = anchor_centers.reshape((-1, 2))
                if len(self._center_cache) < 100:
                    self._center_cache[cache_key] = anchor_centers

            positive_indices = np.where(scores >= threshold)[0]
            decoded_bboxes = self._distance_to_bbox(anchor_centers, bbox_preds)
            scores_list.append(scores[positive_indices])
            bboxes_list.append(decoded_bboxes[positive_indices])

            if self._use_kps and kps_preds is not None:
                decoded_keypoints = self._distance_to_keypoints(anchor_centers, kps_preds).reshape(
                    (-1, 5, 2)
                )
                kpss_list.append(decoded_keypoints[positive_indices])

        return scores_list, bboxes_list, kpss_list

    @staticmethod
    def _distance_to_bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
        """Decode distance predictions to axis-aligned boxes."""
        x1 = points[:, 0] - distance[:, 0]
        y1 = points[:, 1] - distance[:, 1]
        x2 = points[:, 0] + distance[:, 2]
        y2 = points[:, 1] + distance[:, 3]
        return np.stack([x1, y1, x2, y2], axis=-1)

    @staticmethod
    def _distance_to_keypoints(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
        """Decode distance predictions to five keypoints."""
        predictions: list[np.ndarray] = []
        for index in range(0, distance.shape[1], 2):
            px = points[:, index % 2] + distance[:, index]
            py = points[:, index % 2 + 1] + distance[:, index + 1]
            predictions.append(px)
            predictions.append(py)
        return np.stack(predictions, axis=-1)

    def _nms(self, detections: np.ndarray) -> list[int]:
        """Standard greedy NMS on ``[x1, y1, x2, y2, score]`` detections."""
        if detections.shape[0] == 0:
            return []
        x1 = detections[:, 0]
        y1 = detections[:, 1]
        x2 = detections[:, 2]
        y2 = detections[:, 3]
        scores = detections[:, 4]
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]
        keep: list[int] = []
        while order.size > 0:
            current = order[0]
            keep.append(int(current))
            xx1 = np.maximum(x1[current], x1[order[1:]])
            yy1 = np.maximum(y1[current], y1[order[1:]])
            xx2 = np.minimum(x2[current], x2[order[1:]])
            yy2 = np.minimum(y2[current], y2[order[1:]])
            width = np.maximum(0.0, xx2 - xx1 + 1)
            height = np.maximum(0.0, yy2 - yy1 + 1)
            intersection = width * height
            overlap = intersection / (areas[current] + areas[order[1:]] - intersection)
            remaining = np.where(overlap <= self.nms_thresh)[0]
            order = order[remaining + 1]
        return keep

    @staticmethod
    def _select_top_faces(
        image_bgr: np.ndarray,
        bboxes: np.ndarray,
        keypoints: np.ndarray | None,
        max_num: int,
        metric: str,
    ) -> tuple[np.ndarray, np.ndarray | None]:
        """Select top faces by area or center distance (pix-workers behaviour)."""
        area = (bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])
        image_center = (image_bgr.shape[0] // 2, image_bgr.shape[1] // 2)
        offsets = np.vstack(
            [
                (bboxes[:, 0] + bboxes[:, 2]) / 2 - image_center[1],
                (bboxes[:, 1] + bboxes[:, 3]) / 2 - image_center[0],
            ]
        )
        offset_dist_squared = np.sum(np.power(offsets, 2.0), 0)
        values = area if metric == "max" else area - offset_dist_squared * 2.0
        selected = np.argsort(values)[::-1][:max_num]
        trimmed_keypoints = keypoints[selected, :] if keypoints is not None else None
        return bboxes[selected, :], trimmed_keypoints
