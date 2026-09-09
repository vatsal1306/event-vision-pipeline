# coding: utf-8

import os
import os.path as osp

# from utils.functions import (
#     crop_img,
#     parse_roi_box_from_bbox,
#     parse_roi_box_from_landmark,
# )
import pickle
from math import sqrt

import cv2
import numpy as np
import onnxruntime


def resolve_relative_path(relative_path: str, caller_file: str) -> str:
    """
    Resolves a relative path based on the location of the file calling this utility.
    This ensures all relative paths in configs/models/etc are resolved correctly,
    no matter where the script is executed from.
    """
    if os.path.isabs(relative_path):
        return relative_path
    base_dir = os.path.dirname(os.path.abspath(caller_file))
    return os.path.join(base_dir, relative_path)


def crop_img(img, roi_box):
    h, w = img.shape[:2]

    sx, sy, ex, ey = [round(_) for _ in roi_box]
    dh, dw = ey - sy, ex - sx
    if len(img.shape) == 3:
        res = np.zeros((dh, dw, 3), dtype=np.uint8)
    else:
        res = np.zeros((dh, dw), dtype=np.uint8)
    if sx < 0:
        sx, dsx = 0, -sx
    else:
        dsx = 0

    if ex > w:
        ex, dex = w, dw - (ex - w)
    else:
        dex = dw

    if sy < 0:
        sy, dsy = 0, -sy
    else:
        dsy = 0

    if ey > h:
        ey, dey = h, dh - (ey - h)
    else:
        dey = dh

    res[dsy:dey, dsx:dex] = img[sy:ey, sx:ex]
    return res


def parse_roi_box_from_landmark(pts):
    """calc roi box from landmark"""
    bbox = [min(pts[0, :]), min(pts[1, :]), max(pts[0, :]), max(pts[1, :])]
    center = [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]
    radius = max(bbox[2] - bbox[0], bbox[3] - bbox[1]) / 2
    bbox = [center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius]

    llength = sqrt((bbox[2] - bbox[0]) ** 2 + (bbox[3] - bbox[1]) ** 2)
    center_x = (bbox[2] + bbox[0]) / 2
    center_y = (bbox[3] + bbox[1]) / 2

    roi_box = [0] * 4
    roi_box[0] = center_x - llength / 2
    roi_box[1] = center_y - llength / 2
    roi_box[2] = roi_box[0] + llength
    roi_box[3] = roi_box[1] + llength

    return roi_box


def parse_roi_box_from_bbox(bbox):
    left, top, right, bottom = bbox[:4]
    old_size = (right - left + bottom - top) / 2
    center_x = right - (right - left) / 2.0
    center_y = bottom - (bottom - top) / 2.0 + old_size * 0.14
    size = int(old_size * 1.58)

    roi_box = [0] * 4
    roi_box[0] = center_x - size / 2
    roi_box[1] = center_y - size / 2
    roi_box[2] = roi_box[0] + size
    roi_box[3] = roi_box[1] + size

    return roi_box


def _get_suffix(filename):
    """a.jpg -> jpg"""
    pos = filename.rfind(".")
    if pos == -1:
        return ""
    return filename[pos + 1 :]


def _load(fp):
    suffix = _get_suffix(fp)
    if suffix == "npy":
        return np.load(fp)
    elif suffix == "pkl":
        return pickle.load(open(fp, "rb"))


class TDDFA_ONNX(object):
    """Minimal TDDFA_ONNX: For YPR estimation only"""

    def __init__(self, **kvs):
        self.size = kvs.get("size", 120)

        # Resolve ONNX model path from kvs
        onnx_fp = kvs["resnet_onnx"]
        onnx_fp = resolve_relative_path(onnx_fp, __file__)

        if not osp.exists(onnx_fp):
            raise FileNotFoundError(f"[ERROR] ONNX model not found: {onnx_fp}")

        self.session = onnxruntime.InferenceSession(onnx_fp, None)

        # Resolve param mean/std .pkl file
        param_mean_std_fp = kvs.get("param_mean_std", None)
        param_mean_std_fp = resolve_relative_path(param_mean_std_fp, __file__)
        norm_data = _load(param_mean_std_fp)
        self.param_mean = norm_data.get("mean")
        self.param_std = norm_data.get("std")

    def __call__(self, img_ori, objs, **kvs):
        """Run inference and return only 62D param vectors"""
        param_lst = []
        roi_box_lst = []

        crop_policy = kvs.get("crop_policy", "box")

        for obj in objs:
            if crop_policy == "box":
                roi_box = parse_roi_box_from_bbox(obj)
            elif crop_policy == "landmark":
                roi_box = parse_roi_box_from_landmark(obj)
            else:
                raise ValueError(f"Unknown crop policy: {crop_policy}")

            roi_box_lst.append(roi_box)
            img = crop_img(img_ori, roi_box)
            img = cv2.resize(img, (self.size, self.size), interpolation=cv2.INTER_LINEAR)
            img = img.astype(np.float32).transpose(2, 0, 1)[np.newaxis, ...]
            img = (img - 127.5) / 128.0

            param = self.session.run(None, {"input": img})[0]
            param = param.flatten().astype(np.float32)
            param = param * self.param_std + self.param_mean
            param_lst.append(param)

        return param_lst, roi_box_lst
