"""Face detection and ArcFace alignment."""

from __future__ import annotations

from typing import Any

# Side-effect import registers the SCRFD model loader.
from app.ml.detection import registry as _registry  # noqa: F401
from app.ml.detection.types import DetectedFace, FaceCrop

__all__ = [
    "DetectedFace",
    "FaceCrop",
    "FaceCropper",
    "SCRFDDetector",
    "_load_scrfd",
]


def __getattr__(name: str) -> Any:
    """Lazy-load ONNX-backed symbols so ``import app.ml`` stays lightweight."""
    if name == "FaceCropper":
        from app.ml.detection.face_cropper import FaceCropper

        return FaceCropper
    if name == "SCRFDDetector":
        from app.ml.detection.scrfd import SCRFDDetector

        return SCRFDDetector
    if name == "_load_scrfd":
        from app.ml.detection.registry import _load_scrfd

        return _load_scrfd
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
