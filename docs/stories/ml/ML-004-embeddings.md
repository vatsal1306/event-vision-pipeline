# ML-004 — InsightFace R100 embeddings and MobileFaceNet fallback

**Type:** Feature  
**Depends on:** ML-002  
**Area:** `backend/app/ml/embedding/`

## Goal

`BaseEmbeddingModel` 512-d L2-normalized float32. Primary `InsightFaceR100` from PicSee backbone + checkpoint. `extract_batch` default 64. `MobileFaceNet` TFLite CPU sequential for fallback. Wire registry `embedding_model=r100|mbf`.

## References

- `docs/component_ai_ml.md` §5
- Copy `adaface_insightface/backbones.py`, `EmbeddingNet.py` as needed under `backend/app/ml/` or `backend/models/adaface_insightface/`
- Normalize `(x/255-0.5)/0.5` or torchvision equivalent — **must match PicSee** or matching will break

## Create / edit

- `base.py`, `insightface_r100.py`, `mobilefacenet.py`
- GPU OOM: catch and retry smaller batch
- Warn if L2 norm not ~1

## Acceptance

- [ ] Same crop twice → cosine similarity ~1
- [ ] Output shape (N, 512)
- [ ] CPU MBF path runs without CUDA
