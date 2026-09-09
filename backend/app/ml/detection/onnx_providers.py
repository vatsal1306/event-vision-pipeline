"""ONNX Runtime execution provider selection."""

from __future__ import annotations


def get_onnxruntime_providers(device: str) -> list[str]:
    """Return ONNX Runtime providers for the resolved compute device.

    Priority:
    - ``cuda`` → CUDAExecutionProvider, then CPU
    - ``mps`` → CPU only (CoreML EP is incompatible with SCRFD ``det_10g.onnx`` at 128×128)
    - ``cpu`` → CPU only
    - ``auto`` → CUDA if available, else CPU (CoreML is skipped on Apple Silicon)

    PyTorch models (R100, AdaFace) still use ``mps`` via ``resolve_device()``; only ONNX
    inference avoids CoreML because of shape-rank errors on multi-scale SCRFD.

    Args:
        device: Resolved device string from ``resolve_device()``.

    Returns:
        Provider list suitable for ``onnxruntime.InferenceSession``.
    """
    import onnxruntime as ort

    available = set(ort.get_available_providers())
    providers: list[str] = []

    if device == "cuda" and "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")
    elif device == "auto" and "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")
    # mps and auto-without-cuda: CPU only — do not use CoreMLExecutionProvider for SCRFD.

    providers.append("CPUExecutionProvider")
    return providers
