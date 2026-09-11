"""ArcFace ResNet-100 embedding model ported from PicSee."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import structlog

from app.ml.embedding.base import BaseEmbeddingModel, l2_normalize
from app.ml.embedding.batch_utils import extract_batch_with_oom_retry
from app.ml.vendor.adaface_insightface import backbones

logger = structlog.get_logger(__name__)

_SHARED_NET: Any = None
_SHARED_PATH: Path | None = None
_SHARED_LOCK = threading.Lock()


def _shared_r100_net(path: Path, device: Any) -> Any:
    """Return the process-wide R100 module, loading weights once.

    Reconstructing InsightFace R100 in the same process can raise
    ``Only a single TORCH_LIBRARY can be used to register the namespace``.
    Pytest unloads the model registry between files, so we keep the torch
    module alive for the process lifetime.
    """
    global _SHARED_NET, _SHARED_PATH
    import torch

    with _SHARED_LOCK:
        if _SHARED_NET is not None and _SHARED_PATH == path:
            return _SHARED_NET

        net = backbones.get_model("r100", fp16=False)
        state_dict = torch.load(path, map_location=device, weights_only=True)
        net.load_state_dict(state_dict)
        net.to(device)
        net.eval()
        _SHARED_NET = net
        _SHARED_PATH = path
        return net


class ArcFaceR100(BaseEmbeddingModel):
    """ArcFace IR-ResNet-100 embedding model from PicSee production weights."""

    model_name = "r100"

    def __init__(self, model_path: Path | str, device: str = "cpu") -> None:
        """Load R100 PyTorch weights.

        Args:
            model_path: Path to ``model_v1_scratch_training_epoch_20_r100.pt``.
            device: Resolved torch device string.
        """
        import torch

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"ArcFace R100 weights not found: {path}")

        self._device = torch.device(device)
        self._model_path = path
        self._net = _shared_r100_net(path, self._device)
        self._net.to(self._device)
        self._net.eval()

        logger.info("arcface_r100_loaded", model_path=str(path), device=str(self._device))

    def preprocess(self, face_bgr: np.ndarray) -> np.ndarray:
        """Convert a BGR crop to a normalized CHW float32 array.

        Uses PicSee normalization: ``(pixel / 255.0 - 0.5) / 0.5``.
        """
        rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        chw = np.transpose(rgb, (2, 0, 1)).astype(np.float32)
        return (chw / 255.0 - 0.5) / 0.5

    def extract_single(self, face_bgr: np.ndarray) -> np.ndarray:
        """Extract a single L2-normalized embedding."""
        batch = self.extract_batch([face_bgr], batch_size=1)
        return np.asarray(batch[0], dtype=np.float32)

    def extract_batch(
        self,
        faces: list[np.ndarray],
        batch_size: int = 64,
    ) -> np.ndarray:
        """Batch inference with CUDA OOM retry."""
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
            net = self._net
            if net is None:
                raise RuntimeError("ArcFace R100 is closed; load a new wrapper from the registry.")
            for start in range(0, len(faces), batch_size):
                batch_faces = faces[start : start + batch_size]
                tensors = [
                    torch.from_numpy(self.preprocess(face)).unsqueeze(0) for face in batch_faces
                ]
                batch_tensor = torch.cat(tensors, dim=0).to(self._device)
                outputs = net(batch_tensor).detach().cpu().numpy()
                all_embeddings.append(outputs)

        stacked = np.concatenate(all_embeddings, axis=0)
        return l2_normalize(stacked, axis=1)

    def close(self) -> None:
        """Release this wrapper. Process-level weights stay loaded.

        Deleting the shared IResNet and constructing another one in the same
        process can fail with a TORCH_LIBRARY namespace conflict.
        """
        self._net = None
        logger.debug("arcface_r100_closed", model_path=str(self._model_path))
