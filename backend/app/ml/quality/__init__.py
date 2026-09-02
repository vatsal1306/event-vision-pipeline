"""Quality filtering module.

Rejects low-quality face crops that would produce unreliable embeddings.
Two filters run in sequence: blur detection and head-pose estimation.

Key classes (implemented in ML-003):
- ``BlurDetector``   — TFLite model scoring image sharpness.
- ``PoseEstimator``  — TFLite model estimating yaw / pitch / roll.
- ``QualityFilter``  — Composite gate combining blur + pose checks.
"""

from __future__ import annotations

from typing import Any


class QualityFilter:
    """Composite quality gate combining blur and head-pose checks.

    Instantiated by ``ModelRegistry.get_quality_filter()`` with loaded
    blur and pose models.  Skeleton only — full logic in ML-003.
    """

    def __init__(self, blur: Any, pose: Any) -> None:
        self.blur = blur
        self.pose = pose
