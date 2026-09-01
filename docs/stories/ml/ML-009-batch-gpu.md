# ML-009 — Batch embedding extraction for GPU throughput

**Type:** Enhancement  
**Depends on:** ML-008  
**Area:** `face_tasks.py` `process_photo_batch`

## Goal

Optional batch task: N photo ids, detect/crop/filter all, one `extract_batch`, bulk insert embeddings, single clustering run. Use from upload complete when ≥50 pending photos or a periodic sweeper.

## References

- `docs/component_ai_ml.md` §12.3
- Batch 50–100 photos

## Requirements

- Memory: do not load 100 full-res 30MB images at once — download/process sequentially into crop list then embed
- Same quality rules as single-photo path

## Acceptance

- [ ] Batch of 3 fixtures produces same embedding count as 3 single tasks (± quality)
