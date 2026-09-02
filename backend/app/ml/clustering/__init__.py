"""Face clustering module.

Groups face embeddings into person-clusters using a two-stage approach:
DBSCAN for initial dense-cluster discovery, then agglomerative clustering
to merge close clusters.

Key classes (implemented in ML-005, ML-006):
- ``IncrementalClusterer`` — Stateless clustering algorithm (ML-005).
- ``ClusterManager``       — pgvector-backed cluster persistence (ML-006).
"""

from __future__ import annotations
