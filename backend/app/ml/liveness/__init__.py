"""Liveness detection module.

Basic server-side checks to distinguish a live selfie from a photograph
of a photograph or a static screen image.  Phase 1 uses heuristic checks;
advanced liveness is planned for Phase 2.

Key classes (implemented in ML-007):
- ``BasicLivenessDetector`` — Heuristic checks (face size, sharpness,
  colour saturation, detection confidence).
"""

from __future__ import annotations
