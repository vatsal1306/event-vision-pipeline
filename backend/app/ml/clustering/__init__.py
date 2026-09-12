"""Incremental face clustering (ML-005 / ML-006 / ML-007)."""

from app.ml.clustering.cluster_manager import ClusterManager
from app.ml.clustering.clustering_config import CLUSTER_TYPE, SWEEPER_TYPE, sweeper_type_config
from app.ml.clustering.incremental_clusterer import IncrementalClusterer
from app.ml.clustering.locks import (
    CLUSTERING_LOCK_KEY_TEMPLATE,
    FACE_PIPELINE_LOCK_KEY_TEMPLATE,
    EventClusteringLock,
)
from app.ml.clustering.recovery import (
    MergeResult,
    OrphanClusterMerge,
    OrphanCropRecovery,
    RecoveryPipelineResult,
    RecoveryResult,
)
from app.ml.clustering.types import (
    ClusteringInput,
    ClusteringResult,
    ClusteringTypeConfig,
    ExistingCluster,
    ExpandedCluster,
    MergedCluster,
    NewCluster,
)

__all__ = [
    "CLUSTERING_LOCK_KEY_TEMPLATE",
    "FACE_PIPELINE_LOCK_KEY_TEMPLATE",
    "CLUSTER_TYPE",
    "ClusterManager",
    "EventClusteringLock",
    "MergeResult",
    "OrphanClusterMerge",
    "OrphanCropRecovery",
    "RecoveryPipelineResult",
    "RecoveryResult",
    "SWEEPER_TYPE",
    "ClusteringInput",
    "ClusteringResult",
    "ClusteringTypeConfig",
    "ExpandedCluster",
    "ExistingCluster",
    "IncrementalClusterer",
    "MergedCluster",
    "NewCluster",
    "sweeper_type_config",
]
