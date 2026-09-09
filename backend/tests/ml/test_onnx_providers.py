"""Tests for ONNX execution provider selection."""

from __future__ import annotations

from app.ml.detection.onnx_providers import get_onnxruntime_providers
from app.ml.device import resolve_onnx_device


def test_mps_device_uses_cpu_only_for_onnx() -> None:
    """Apple MPS must not map to CoreML for SCRFD (128×128 pass fails on M2)."""
    providers = get_onnxruntime_providers("mps")
    assert providers == ["CPUExecutionProvider"]
    assert "CoreMLExecutionProvider" not in providers


def test_cpu_device_uses_cpu_only() -> None:
    """Explicit CPU should return CPUExecutionProvider only."""
    assert get_onnxruntime_providers("cpu") == ["CPUExecutionProvider"]


def test_resolve_onnx_device_maps_mps_to_cpu() -> None:
    """MPS is a PyTorch-only backend; ONNX inference stays on CPU."""
    assert resolve_onnx_device("mps") == "cpu"


def test_resolve_onnx_device_auto_matches_cuda_ep_availability() -> None:
    """Auto should map to CUDA only when the CUDA EP is registered with ORT."""
    import onnxruntime as ort

    available = "CUDAExecutionProvider" in ort.get_available_providers()
    assert resolve_onnx_device("auto") == ("cuda" if available else "cpu")
    assert resolve_onnx_device("cuda") == ("cuda" if available else "cpu")
