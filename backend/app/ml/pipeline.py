"""High-level ML pipeline orchestrator.

This module will coordinate the full upload-time and match-time pipelines,
calling detection → quality filtering → embedding → clustering in sequence.

Implementation arrives in **ML-008** (FaceService and Celery face tasks).
"""

from __future__ import annotations
