# ML-006 — ClusterManager persistence on pgvector

**Type:** Feature  
**Depends on:** BE-003, ML-005  
**Area:** `backend/app/ml/clustering/cluster_manager.py`

## Goal

Load event clusters and unclustered embeddings (`cluster_id IS NULL`), apply `ClusteringResult` in a transaction: insert clusters, update centroids/sizes, reassign embeddings, delete merged sources. Batch size 5000.

## References

- `docs/component_ai_ml.md` §7.2
- Store centroid as list/vector compatible with pgvector

## Create / edit

- Use SQLAlchemy 2.0 update/delete
- After merge, no orphan cluster rows

## Acceptance

- [ ] Integration test against test DB: insert embeddings, run apply, cluster_ids set
- [ ] Second batch expands existing cluster
