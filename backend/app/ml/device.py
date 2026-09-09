"""Compute device resolution for ML inference."""

from __future__ import annotations

from typing import Any, Literal

DeviceName = Literal["auto", "cuda", "cpu", "mps"]
ResolvedDevice = Literal["cuda", "cpu", "mps"]
OnnxResolvedDevice = Literal["cuda", "cpu"]

_SUPPORTED_DEVICES: frozenset[str] = frozenset({"auto", "cuda", "cpu", "mps"})


def _import_torch() -> Any:
    """Import PyTorch lazily so ``app.ml`` stays lightweight at import time."""
    try:
        import torch
    except ImportError:
        return None
    return torch


def resolve_device(device: str = "auto") -> ResolvedDevice:
    """Resolve a configured device string to a concrete runtime device.

    Resolution order for ``auto``:
    1. CUDA when available
    2. Apple MPS when available
    3. CPU

    Args:
        device: One of ``auto``, ``cuda``, ``cpu``, or ``mps``.

    Returns:
        The resolved device name used for model placement.

    Raises:
        ValueError: If ``device`` is not a supported value.
    """
    normalized = device.lower().strip()
    if normalized not in _SUPPORTED_DEVICES:
        supported = ", ".join(sorted(_SUPPORTED_DEVICES))
        raise ValueError(f"Unsupported device '{device}'. Expected one of: {supported}.")

    if normalized == "cpu":
        return "cpu"

    torch = _import_torch()
    if torch is None:
        return "cpu"

    if normalized == "cuda":
        return "cuda" if torch.cuda.is_available() else "cpu"

    if normalized == "mps":
        mps_backend = getattr(torch.backends, "mps", None)
        if mps_backend is not None and mps_backend.is_available():
            return "mps"
        return "cpu"

    if torch.cuda.is_available():
        return "cuda"

    mps_backend = getattr(torch.backends, "mps", None)
    if mps_backend is not None and mps_backend.is_available():
        return "mps"

    return "cpu"


def _cuda_onnx_available() -> bool:
    """Return True when ONNX Runtime can use the CUDA execution provider."""
    try:
        import onnxruntime as ort
    except ImportError:
        return False
    return "CUDAExecutionProvider" in ort.get_available_providers()


def resolve_onnx_device(device: str = "auto") -> OnnxResolvedDevice:
    """Resolve a device string for ONNX Runtime inference.

    ONNX models (SCRFD, FaceBoxes, ResNet22) never use Apple MPS or CoreML in this
    codebase. For ``auto``, ``cpu``, and ``mps``, this returns ``cpu`` without importing
    PyTorch, avoiding torch/triton re-registration conflicts when PyTorch models load in
    the same process (for example ViT age via ``transformers``).

    CUDA availability is checked via ONNX Runtime providers, not ``torch.cuda``.

    Args:
        device: One of ``auto``, ``cuda``, ``cpu``, or ``mps``.

    Returns:
        Either ``cuda`` (when CUDA EP is usable) or ``cpu``.

    Raises:
        ValueError: If ``device`` is not a supported value.
    """
    normalized = device.lower().strip()
    if normalized not in _SUPPORTED_DEVICES:
        supported = ", ".join(sorted(_SUPPORTED_DEVICES))
        raise ValueError(f"Unsupported device '{device}'. Expected one of: {supported}.")

    if normalized in {"cpu", "mps"}:
        return "cpu"

    if normalized == "cuda":
        return "cuda" if _cuda_onnx_available() else "cpu"

    # auto: prefer CUDA EP when available; otherwise CPU (including Apple Silicon).
    return "cuda" if _cuda_onnx_available() else "cpu"
