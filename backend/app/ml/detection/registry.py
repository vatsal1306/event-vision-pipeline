"""SCRFD model loader registration for the global model registry."""

from __future__ import annotations

from app.ml.detection.scrfd import SCRFDDetector
from app.ml.model_registry import ModelRegistry, register_model_loader


def _load_scrfd(registry: ModelRegistry) -> SCRFDDetector:
    """Construct a configured SCRFD detector from registry settings."""
    config = registry.config
    return SCRFDDetector(
        model_path=config.scrfd_model_path,
        device=registry.resolved_device,
        det_thresh=config.scrfd_det_thresh,
        nms_thresh=config.scrfd_nms_thresh,
        input_sizes=config.scrfd_input_sizes,
    )


def register_detection_loaders() -> None:
    """Register SCRFD and related detection model loaders."""
    register_model_loader("scrfd", _load_scrfd)


register_detection_loaders()
