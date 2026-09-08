"""Tests for ONNX execution provider selection."""

from __future__ import annotations

from app.ml.detection.onnx_providers import get_onnxruntime_providers


def test_mps_device_uses_cpu_only_for_onnx() -> None:
    """Apple MPS must not map to CoreML for SCRFD (128×128 pass fails on M2)."""
    providers = get_onnxruntime_providers("mps")
    assert providers == ["CPUExecutionProvider"]
    assert "CoreMLExecutionProvider" not in providers


def test_cpu_device_uses_cpu_only() -> None:
    """Explicit CPU should return CPUExecutionProvider only."""
    assert get_onnxruntime_providers("cpu") == ["CPUExecutionProvider"]
