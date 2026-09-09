"""Clustering type configuration for regular and sweeper passes."""

from __future__ import annotations

from app.ml.clustering.types import ClusteringTypeConfig
from app.ml.config import get_ml_config

CLUSTER_TYPE = ClusteringTypeConfig(
    name="cluster",
    creates_new_clusters=True,
    expands_existing=True,
    allows_merge_clusters=True,
    centroid_field="centroid",
    pyr_range=(0.0, 47.0),
)


def sweeper_type_config() -> ClusteringTypeConfig:
    """Build sweeper config using PYR bounds from ``MLConfig``."""
    config = get_ml_config()
    return ClusteringTypeConfig(
        name="sweeper",
        creates_new_clusters=False,
        expands_existing=True,
        allows_merge_clusters=False,
        centroid_field="centroid",
        pyr_range=(config.sweeper_pyr_min, config.sweeper_pyr_max),
    )


SWEEPER_TYPE = sweeper_type_config()
