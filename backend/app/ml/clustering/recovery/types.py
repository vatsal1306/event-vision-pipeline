"""Result types for orphan crop and orphan cluster recovery."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CropAssignment:
    """One orphan crop matched to a cluster via PYR-centroid similarity."""

    crop_id: str
    cluster_id: str
    similarity: float


@dataclass(frozen=True)
class ClusterMergeAssignment:
    """One small cluster absorbed into an established cluster."""

    orphan_id: str
    target_id: str
    similarity: float
    match_type: str


@dataclass
class RecoveryResult:
    """Outcome of orphan-crop recovery for one event."""

    recovered: int
    still_orphaned: int
    details: list[dict[str, object]] = field(default_factory=list)


@dataclass
class MergeResult:
    """Outcome of orphan-cluster merge for one event."""

    merged_count: int
    remaining_orphans: int
    details: list[dict[str, object]] = field(default_factory=list)


@dataclass
class RecoveryPipelineResult:
    """Combined crop recovery + cluster merge after clustering/sweeper."""

    crop_result: RecoveryResult
    merge_result: MergeResult
    skipped: bool = False

    @classmethod
    def disabled(cls) -> RecoveryPipelineResult:
        """Return an empty result used when the feature flag is off."""
        return cls(
            crop_result=RecoveryResult(recovered=0, still_orphaned=0),
            merge_result=MergeResult(merged_count=0, remaining_orphans=0),
            skipped=True,
        )
