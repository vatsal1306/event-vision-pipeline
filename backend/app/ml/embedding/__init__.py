"""Face embedding extraction module.

Contains model wrappers for computing 512-dimensional, L2-normalised
face embeddings from aligned 112x112 face crops.

Key classes (implemented in ML-004):
- ``BaseEmbeddingModel`` — Abstract interface for all embedding models.
- ``InsightFaceR100``    — Primary GPU model (~250 MB, PyTorch).
- ``MobileFaceNet``      — Lightweight CPU fallback (~5 MB).
"""

from __future__ import annotations
