"""ViT age classifier for child detection."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import structlog
import torch
from PIL import Image
from transformers import ViTForImageClassification, ViTImageProcessor

from app.ml.quality.types import AGE_ESTIMATION_FAILED
from app.ml.torch_process_cache import get_or_create

logger = structlog.get_logger(__name__)

DEFAULT_AGE_BINS = torch.tensor([2, 9, 19, 29, 39, 49, 59, 69, 79])
DEFAULT_FAILED_AGE = AGE_ESTIMATION_FAILED


class AgeDetector:
    """Age estimator ported from pix-workers ``age_detect.py``."""

    def __init__(
        self,
        model_path: Path | str,
        device: str = "cpu",
        confidence_threshold: float = 0.5,
    ) -> None:
        """Load a local HuggingFace ViT age classifier snapshot.

        Args:
            model_path: Directory containing ``config.json`` and model weights.
            device: Torch device string.
            confidence_threshold: Minimum softmax confidence to trust the estimate.
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Age model directory not found: {path}. "
                "Download nateraw/vit-age-classifier into backend/models/vit-age-classifier."
            )

        resolved_device = device
        if resolved_device == "auto":
            resolved_device = "cuda" if torch.cuda.is_available() else "cpu"

        self._device = resolved_device
        self._confidence_threshold = confidence_threshold
        self._model_path = path

        processor, model = get_or_create(
            f"age_vit:{path.resolve()}:{self._device}",
            lambda: _load_age_vit(path, self._device),
        )
        self._processor = processor
        self._model = model
        logger.info("age_detector_loaded", model_path=str(path), device=self._device)

    def estimate(self, face_crop_bgr: np.ndarray) -> tuple[int, float]:
        """Estimate age from a BGR face crop.

        Returns:
            Tuple of ``(age, confidence)``. Failed or low-confidence predictions
            return ``DEFAULT_FAILED_AGE`` so callers can treat them as pass-on-error.
        """
        image = self._to_pil(face_crop_bgr)
        inputs = self._processor(images=image, return_tensors="pt").to(self._device)

        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=1)

        predicted_bin = int(probs.argmax(dim=1).item())
        confidence = float(probs[0, predicted_bin].item())
        if confidence <= self._confidence_threshold:
            return DEFAULT_FAILED_AGE, confidence

        ages = DEFAULT_AGE_BINS.to(probs.device)
        smooth_age = int(torch.sum(probs * ages).item())
        return smooth_age, confidence

    @staticmethod
    def _to_pil(face_crop_bgr: np.ndarray) -> Image.Image:
        rgb = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    def close(self) -> None:
        """Release this wrapper. Process-level ViT weights stay loaded."""
        logger.debug("age_detector_closed", model_path=str(self._model_path))


def _load_age_vit(path: Path, device: str) -> tuple[ViTImageProcessor, ViTForImageClassification]:
    """Load the HuggingFace ViT once per process."""
    processor = ViTImageProcessor.from_pretrained(str(path), local_files_only=True)
    model = ViTForImageClassification.from_pretrained(
        str(path),
        local_files_only=True,
    ).to(device)
    model.eval()
    return processor, model
