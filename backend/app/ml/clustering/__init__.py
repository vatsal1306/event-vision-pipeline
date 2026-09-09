"""Incremental face clustering (ML-005)."""

from app.ml.clustering.clustering_config import CLUSTER_TYPE, SWEEPER_TYPE, sweeper_type_config
from app.ml.clustering.incremental_clusterer import IncrementalClusterer
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
    "CLUSTER_TYPE",
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
