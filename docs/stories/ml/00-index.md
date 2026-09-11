# ML Stories — Index (Revised with PicSee Integration)

> **Revision Date:** September 2026
> **Previous Version:** 10 stories (ML-001 → ML-010), pre-PicSee integration
> **Current Version:** 11 stories (ML-001 → ML-011), fully integrated with PicSee pipeline

## Source Repositories

| Repo | Path | What It Provides |
|------|------|-----------------|
| **PicSee clustering_pipeline** | `/Users/vatsal/Documents/picsee/clustering_pipeline` | SCRFD, FaceCropper, Blur/YPR TFLite, R100 embeddings, DBSCAN+Agglomerative clustering, model weights |
| **PicSee pix-workers** | `/Users/vatsal/Documents/picsee/tmp/code/pix-workers` | AdaFace VIT-KPRPE, 3DDFA_V2 YPR, age/sunglasses detection, sweeper/orphan recovery algorithms, production clustering service |

## Deployment Constraint

**Do NOT deploy face processing workers on the production app EC2** (`m6i.xlarge`, CPU-only).
All ML inference runs on a **separate ML host** (GPU instance, size TBD).
Until the ML host is provisioned, BE-013 uses a stub `FaceService` that returns `no_match`.

## Model Inventory

| Model | File | Size | Format | Available |
|-------|------|------|--------|-----------|
| SCRFD Face Detector | `det_10g.onnx` | 16 MB | ONNX | ✅ |
| ArcFace R100 | `model_v1_scratch_training_epoch_20_r100.pt` | 249 MB | PyTorch | ✅ |
| AdaFace VIT-KPRPE | `cvlface_adaface_vit_base_kprpe_webface12m/model.pt` | 439 MB | PyTorch | ✅ |
| DFA Mobilenet Aligner | `cvlface_DFA_mobilenet/model.pt` | 2 MB | PyTorch | ✅ |
| MobileFaceNet (CPU fallback) | `preprocessed_transformation_mbf_model_w12m_RE10.tflite` | 13 MB | TFLite | ✅ |
| Blur Classifier | `blur_model_tflite_may6_ckpt49.tflite` | 2 MB | TFLite | ✅ |
| YPR TFLite (fallback) | `ypr_model_float32.tflite` | 816 KB | TFLite | ✅ |
| YPR 3DDFA_V2 | `resnet22.onnx` + `FaceBoxesProd.onnx` | 74 MB | ONNX | ✅ (downloaded) |
| Age Classifier | `nateraw/vit-age-classifier` | ~350 MB | HuggingFace | ✅ (auto-download) |
| Sunglasses Classifier | `glasses-detector` | pip | Python package | ✅ (pip install) |
| Human/Non-Human | `HNH_MODEL_NORMALIZED_SCRIPTED.PT` | ~50 MB | TorchScript | ❌ Not available |

## Story Dependency Graph

```
ML-001 (Foundation)
  ├──→ ML-002 (Detection + Crop)
  │      ├──→ ML-003 (Quality Filters)
  │      ├──→ ML-004 (Dual Embeddings)
  │      └──────────────────────────────┐
  ├──→ ML-005 (Clustering Algorithm)    │
  │      │                              │
  │      ▼                              ▼
  │    ML-006 (Cluster Persistence) ← BE-003
  │      │
  │      ▼
  │    ML-007 (Recovery Algorithms)
  │      │
  │      ▼
  │    ML-008 (Selfie Match + Liveness) ← ML-002, ML-003, ML-004
  │      │
  │      ▼
  └──→ ML-009 (FaceService + Celery)
         │
         ▼
       ML-010 (Bulk Processing)
         │
         ▼
       ML-011 (Tests + CI)
```

## Stories Summary

| ID | Title | Status | Priority | Effort |
|----|-------|--------|----------|--------|
| **ML-001** | ML Package, MLConfig, ModelRegistry | Done | P0 | S |
| **ML-002** | SCRFD Detection + ArcFace 112×112 Crop | Done | P0 | M |
| **ML-003** | Quality Filters (Blur, 3DDFA_V2 YPR, Age, Sunglasses) | Pending | P0 | L |
| **ML-004** | Dual-Model Embeddings (R100 + AdaFace VIT-KPRPE) | Pending | P0 | L |
| **ML-005** | Incremental Clustering + Sweeper Config | Done | P0 | M |
| **ML-006** | Cluster Persistence (pgvector) | Done | P0 | M |
| **ML-007** | Advanced Clustering Recovery (Orphan Crops + Clusters) | Done | P1 | M |
| **ML-008** | Selfie Matching + Basic Liveness | Pending | P0 | M |
| **ML-009** | FaceService Orchestration + Celery Tasks | Pending | P0 | M |
| **ML-010** | Bulk Upload Processing Pipeline | Pending | P0 | L |
| **ML-011** | ML Tests + CI Skip Rules | Pending | P1 | M |

## Key Changes from Previous ML Stories

| Previous Story | What Changed |
|---------------|-------------|
| ML-001 | Expanded model inventory (AdaFace, 3DDFA_V2, age, sunglasses) |
| ML-002 | Same scope, more detailed PicSee source references |
| ML-003 | **Major expansion**: added 3DDFA_V2 ONNX YPR (primary), age detection, sunglasses detection |
| ML-004 | **Major expansion**: now DUAL-model (R100 + AdaFace VIT-KPRPE), not just R100 + MBF fallback |
| ML-005 | Added sweeper config from pix-workers production |
| ML-006 | Added PYR centroid + secondary centroid columns for dual-model |
| ML-007 | **NEW story**: orphan crop recovery + orphan cluster merge (from pix-workers) |
| ML-008 (was ML-007) | Added dual-model cross-validation for selfie matching |
| ML-009 (was ML-008) | Same scope, clarified deployment constraints |
| ML-010 (was ML-009) | Renamed to bulk processing, added memory management + progress tracking |
| ML-011 (was ML-010) | Same scope, expanded test matrix |

## Recommended Implementation Order

### Phase A: Core Pipeline (can process photos)
1. ML-001 → ML-002 → ML-004 (R100 only first) → ML-005 → ML-006

### Phase B: Quality + Accuracy (production-grade accuracy)
2. ML-003 → ML-004 (add AdaFace dual) → ML-007

### Phase C: Guest Experience (selfie matching works)
3. ML-008 → ML-009 → ML-010

### Phase D: CI + Polish
4. ML-011
