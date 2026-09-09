# coding: utf-8

from __future__ import annotations

import os.path as osp
from pathlib import Path

import cv2
import numpy as np
import onnxruntime
import torch
import yaml

from .utils.box_utils import decode
from .utils.config import cfg
from .utils.nms_wrapper import nms
from .utils.prior_box import PriorBox

confidence_threshold = 0.05
top_k = 5000
keep_top_k = 750
nms_threshold = 0.3
vis_thres = 0.5
resize = 1

scale_flag = True
HEIGHT, WIDTH = 720, 1080


def _resolve_onnx_path(config_path: Path, onnx_rel_path: str) -> str:
    """Resolve an ONNX path from a YAML config entry."""
    candidate = Path(onnx_rel_path)
    if candidate.is_absolute():
        return str(candidate)
    return str((config_path.parent / candidate).resolve())


class FaceBoxes_ONNX:
    """FaceBoxes ONNX detector used by 3DDFA_V2 YPR."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "resnet_config.yml"
        else:
            config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"3DDFA config not found: {config_path}")

        with config_path.open("r", encoding="utf-8") as handle:
            resnet_cfg = yaml.safe_load(handle)

        onnx_path = _resolve_onnx_path(config_path, resnet_cfg["faceboxesprod_onnx"])
        if not osp.exists(onnx_path):
            raise FileNotFoundError(
                f"FaceBoxes ONNX model not found at {onnx_path}. "
                "Copy FaceBoxesProd.onnx into backend/models/."
            )
        self.session = onnxruntime.InferenceSession(onnx_path, None)

    def __call__(self, img_):
        img_raw = img_.copy()

        scale = 1
        if scale_flag:
            h, w = img_raw.shape[:2]
            if h > HEIGHT:
                scale = HEIGHT / h
            if w * scale > WIDTH:
                scale *= WIDTH / (w * scale)

            if scale == 1:
                img_raw_scale = img_raw
            else:
                h_s = int(scale * h)
                w_s = int(scale * w)
                img_raw_scale = cv2.resize(img_raw, dsize=(w_s, h_s))

            img = np.float32(img_raw_scale)
        else:
            img = np.float32(img_raw)

        im_height, im_width, _ = img.shape
        scale_bbox = torch.Tensor([im_width, im_height, im_width, im_height])

        img -= (104, 117, 123)
        img = img.transpose(2, 0, 1)
        img = img[np.newaxis, ...]

        out = self.session.run(None, {"input": img})
        loc, conf = out[0], out[1]
        loc = torch.from_numpy(loc)

        priorbox = PriorBox(image_size=(im_height, im_width))
        priors = priorbox.forward()
        prior_data = priors.data
        boxes = decode(loc.data.squeeze(0), prior_data, cfg["variance"])

        if scale_flag:
            boxes = boxes * scale_bbox / scale / resize
        else:
            boxes = boxes * scale_bbox / resize

        boxes = boxes.cpu().numpy()
        scores = conf[0][:, 1]

        inds = np.where(scores > confidence_threshold)[0]
        boxes = boxes[inds]
        scores = scores[inds]

        order = scores.argsort()[::-1][:top_k]
        boxes = boxes[order]
        scores = scores[order]

        dets = np.hstack((boxes, scores[:, np.newaxis])).astype(np.float32, copy=False)
        keep = nms(dets, nms_threshold)
        dets = dets[keep, :]
        dets = dets[:keep_top_k, :]

        det_bboxes = []
        for b in dets:
            if b[4] > vis_thres:
                xmin, ymin, xmax, ymax, score = b[0], b[1], b[2], b[3], b[4]
                bbox = [xmin, ymin, xmax, ymax, score]
                det_bboxes.append(bbox)

        return det_bboxes
