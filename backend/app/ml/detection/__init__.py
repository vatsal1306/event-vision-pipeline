"""Face detection and ArcFace alignment."""

# Side-effect import registers the SCRFD model loader.
from app.ml.detection import registry as _registry  # noqa: F401
from app.ml.detection.face_cropper import FaceCropper
from app.ml.detection.registry import _load_scrfd
from app.ml.detection.scrfd import SCRFDDetector
from app.ml.detection.types import DetectedFace, FaceCrop

__all__ = [
    "DetectedFace",
    "FaceCrop",
    "FaceCropper",
    "SCRFDDetector",
    "_load_scrfd",
]
