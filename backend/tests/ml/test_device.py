"""Unit tests for ONNX device resolution (no ml extra required)."""

from __future__ import annotations

from app.ml.device import resolve_onnx_device


def test_resolve_onnx_device_maps_mps_to_cpu() -> None:
    """MPS is a PyTorch-only backend; ONNX inference stays on CPU."""
    assert resolve_onnx_device("mps") == "cpu"


def test_resolve_onnx_device_explicit_cpu() -> None:
    """Explicit CPU should remain CPU for ONNX workloads."""
    assert resolve_onnx_device("cpu") == "cpu"
