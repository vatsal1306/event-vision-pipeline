# coding: utf-8

# --------------------------------------------------------
# Fast R-CNN
# Copyright (c) 2015 Microsoft
# Licensed under The MIT License [see LICENSE for details]
# Written by Ross Girshick
# --------------------------------------------------------

from .nms.py_cpu_nms import py_cpu_nms

try:
    from .nms.cpu_nms import cpu_nms as _cpu_nms
except ImportError:
    _cpu_nms = None


def nms(dets, thresh):
    """Dispatch to Cython NMS when available, otherwise pure Python."""
    if dets.shape[0] == 0:
        return []
    if _cpu_nms is not None:
        return _cpu_nms(dets, thresh)
    return py_cpu_nms(dets, thresh)
