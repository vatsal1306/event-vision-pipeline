"""Data types for face quality filtering."""

from __future__ import annotations

from dataclasses import dataclass, field

# Sentinel returned when age estimation fails; kept here to avoid importing torch in callers.
AGE_ESTIMATION_FAILED = 200


@dataclass(frozen=True)
class QualityResult:
    """Outcome of running all quality gates on a face crop.

    Attributes:
        passed: Whether the crop should proceed to embedding extraction.
        reject_reason: Hard reject reason (``blur``, ``ypr``, ``age``), or ``None``.
        blur_score: Blur classifier score, or ``None`` if blur check did not run.
        ypr: Raw ``(yaw, pitch, roll)`` angles in degrees for downstream sweeper logic.
        age: Estimated age in years, or ``None`` if age detection was skipped or failed.
        has_sunglasses: Soft flag — face may still be embedded when ``True``.
        metadata: Raw scores and diagnostic details for analytics.
    """

    passed: bool
    reject_reason: str | None
    blur_score: float | None
    ypr: tuple[float, float, float] | None
    age: int | None
    has_sunglasses: bool
    metadata: dict[str, object] = field(default_factory=dict)
