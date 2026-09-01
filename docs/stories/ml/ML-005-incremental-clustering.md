# ML-005 — Incremental DBSCAN + agglomerative clustering

**Type:** Feature  
**Depends on:** ML-001  
**Area:** `backend/app/ml/clustering/incremental_clusterer.py`

## Goal

Port PicSee two-stage clustering with centroid injection. sklearn `DBSCAN` cosine eps=0.45 min_samples=1; `AgglomerativeClustering` average cosine distance_threshold=0.45. Return `new_clusters`, `expanded_clusters`, `merged_clusters` dataclasses. Weighted centroid update. Ignore DBSCAN label -1 in visualization but handle noise embeddings (assign to new singleton clusters if min_samples=1 typically no noise).

## References

- `docs/component_ai_ml.md` §7.1
- PicSee `update_crops_reject_situation.md` I/O contract
- `face_rec_id` conflict resolver: implement function; production batches use `face_rec_id=None`

## Create / edit

- Pure numpy/sklearn; no DB in this module
- Unit tests with synthetic well-separated vs close embeddings

## Acceptance

- [ ] Two identical embeddings + empty existing → one new cluster size 2
- [ ] New embedding near existing centroid → expanded_clusters
- [ ] Two centroids that should merge → merged_clusters
