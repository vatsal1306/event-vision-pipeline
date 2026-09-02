"""Face detection module.

Contains the SCRFD detector (adapted from the PicSee clustering pipeline)
and the ArcFace 5-point face alignment / cropping utility.

Key classes (implemented in ML-002):
- ``SCRFDDetector`` — ONNX-based multi-scale face detector.
- ``FaceCropper``   — ArcFace-aligned 112x112 face crop extraction.
"""

from __future__ import annotations
