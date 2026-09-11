"""AdaFace VIT-KPRPE secondary embedding model from pix-workers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
import structlog
from torchvision.transforms import Compose, Normalize, ToTensor

from app.ml.embedding.base import BaseEmbeddingModel, l2_normalize
from app.ml.embedding.batch_utils import extract_batch_with_oom_retry
from app.ml.embedding.cvlface_loader import load_cvlface_model
from app.ml.torch_process_cache import get_or_create

logger = structlog.get_logger(__name__)


class AdaFaceVitKprpe(BaseEmbeddingModel):
    """AdaFace VIT-KPRPE with DFA Mobilenet keypoint aligner."""

    model_name = "adaface_vit_kprpe"

    def __init__(
        self,
        model_dir: Path | str,
        aligner_dir: Path | str,
        device: str = "cpu",
    ) -> None:
        """Load VIT-KPRPE and DFA aligner from local HuggingFace exports.

        Args:
            model_dir: Path to ``cvlface_adaface_vit_base_kprpe_webface12m``.
            aligner_dir: Path to ``cvlface_DFA_mobilenet``.
            device: Resolved torch device string.
        """
        import torch

        model_path = Path(model_dir)
        aligner_path = Path(aligner_dir)
        if not model_path.is_dir():
            raise FileNotFoundError(f"AdaFace model directory not found: {model_path}")
        if not aligner_path.is_dir():
            raise FileNotFoundError(f"DFA aligner directory not found: {aligner_path}")

        self._device = torch.device(device)
        self._model_dir = model_path
        self._aligner_dir = aligner_path
        self._transform = Compose(
            [
                ToTensor(),
                Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
            ]
        )

        logger.info(
            "adaface_vit_kprpe_loading",
            model_dir=str(model_path),
            aligner_dir=str(aligner_path),
        )
        self._model, self._aligner = get_or_create(
            f"adaface:{model_path.resolve()}:{aligner_path.resolve()}:{self._device}",
            lambda: _load_adaface_pair(model_path, aligner_path, self._device),
        )

        logger.info("adaface_vit_kprpe_loaded", device=str(self._device))

    def _to_rgb_tensor(self, face_bgr: np.ndarray) -> np.ndarray:
        """Convert BGR uint8 crop to a normalized CHW float32 array."""
        rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        tensor = self._transform(rgb)
        return np.asarray(tensor.detach().cpu().numpy(), dtype=np.float32)

    def extract_single(self, face_bgr: np.ndarray) -> np.ndarray:
        """Extract a single L2-normalized embedding."""
        batch = self.extract_batch([face_bgr], batch_size=1)
        return np.asarray(batch[0], dtype=np.float32)

    def extract_batch(
        self,
        faces: list[np.ndarray],
        batch_size: int = 64,
    ) -> np.ndarray:
        """Two-stage batch inference with CUDA OOM retry."""
        return extract_batch_with_oom_retry(
            faces,
            batch_size,
            self._extract_batch_internal,
            model_name=self.model_name,
        )

    def _extract_batch_internal(
        self,
        faces: list[np.ndarray],
        batch_size: int,
    ) -> np.ndarray:
        import torch

        if not faces:
            return np.empty((0, self.EMBEDDING_DIM), dtype=np.float32)

        all_embeddings: list[np.ndarray] = []

        with torch.no_grad():
            for start in range(0, len(faces), batch_size):
                batch_faces = faces[start : start + batch_size]
                tensors = [torch.from_numpy(self._to_rgb_tensor(face)) for face in batch_faces]
                input_tensor = torch.stack(tensors).to(self._device)

                _aligned_x, orig_ldmks, _aligned_ldmks, _score, _thetas, _bbox = self._aligner(
                    input_tensor
                )
                keypoints = orig_ldmks.to(self._device)
                outputs = self._model(input_tensor, keypoints)
                all_embeddings.append(outputs.detach().cpu().numpy())

        stacked = np.concatenate(all_embeddings, axis=0)
        return l2_normalize(stacked, axis=1)

    def close(self) -> None:
        """Release this wrapper. Process-level AdaFace/DFA weights stay loaded."""
        logger.debug(
            "adaface_vit_kprpe_closed",
            model_dir=str(self._model_dir),
            aligner_dir=str(self._aligner_dir),
        )


def _load_adaface_pair(model_path: Path, aligner_path: Path, device: Any) -> tuple[Any, Any]:
    """Load VIT-KPRPE and DFA aligner once per process."""
    model = load_cvlface_model(model_path)
    aligner = load_cvlface_model(aligner_path)
    model.to(device)
    aligner.to(device)
    return model, aligner
