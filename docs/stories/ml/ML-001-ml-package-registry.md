# ML-001 — ML Package Foundation, MLConfig, and ModelRegistry

**Type:** Feature
**Depends on:** None
**Area:** `backend/app/ml/`

## Goal

Create the `backend/app/ml/` package tree, a centralised `MLConfig` that reads all
thresholds/paths from env vars with sensible defaults, and a thread-safe lazy
`ModelRegistry` singleton that loads models **only inside Celery workers** — never in
FastAPI request workers.

## PicSee Integration Context

This story establishes the foundation that all subsequent ML stories depend on.
The model files are sourced from two PicSee repositories:

| Source Repo | Path | What to copy |
|-------------|------|--------------|
| **clustering_pipeline** | `MODELS/` | `det_10g.onnx`, `blur_model_tflite_may6_ckpt49.tflite`, `ypr_model_float32.tflite`, `model_v1_scratch_training_epoch_20_r100.pt`, `preprocessed_transformation_mbf_model_w12m_RE10.tflite` |
| **pix-workers** | `face_rec_service/models/` | `resnet22.onnx` (70 MB), `FaceBoxesProd.onnx` (3.9 MB) — 3DDFA_V2 YPR |
| **pix-workers** | `face_rec_service/cvlface_adaface_vit_base_kprpe_webface12m/` | AdaFace VIT-KPRPE model + code (439 MB `model.pt`, 2 MB `aligner.pt`) |
| **pix-workers** | `face_rec_service/cvlface_DFA_mobilenet/` | DFA Mobilenet aligner (2 MB `model.pt`) |

## Package Structure

```
backend/app/ml/
├── __init__.py
├── config.py                # MLConfig (pydantic-settings)
├── model_registry.py        # Lazy singleton ModelRegistry
├── detection/
│   ├── __init__.py
│   ├── scrfd.py             # SCRFD ONNX detector (from PicSee)
│   └── face_cropper.py      # ArcFace 112×112 alignment (from PicSee)
├── quality/
│   ├── __init__.py
│   ├── blur_detector.py     # TFLite blur classifier (from PicSee)
│   ├── ypr_tflite.py        # TFLite YPR fallback (from PicSee)
│   ├── ypr_3ddfa.py         # 3DDFA_V2 ONNX YPR (from pix-workers)
│   ├── age_detector.py      # ViT age classifier (HuggingFace auto-download)
│   ├── sunglasses.py        # glasses-detector wrapper (pip install)
│   └── quality_filter.py    # Orchestrates all quality gates
├── embedding/
│   ├── __init__.py
│   ├── base.py              # BaseEmbeddingModel ABC
│   ├── arcface_r100.py      # ArcFace R100 PyTorch (from PicSee)
│   ├── adaface_vit_kprpe.py # AdaFace VIT-KPRPE (from pix-workers)
│   ├── mobilefacenet.py     # MBF TFLite CPU fallback (from PicSee)
│   └── dual_embedder.py     # Dual-model orchestrator
├── clustering/
│   ├── __init__.py
│   ├── incremental_clusterer.py  # DBSCAN + Agglomerative (from PicSee)
│   ├── clustering_config.py      # Cluster vs Sweeper configs (from pix-workers)
│   ├── cluster_manager.py        # pgvector persistence
│   └── recovery/
│       ├── __init__.py
│       ├── orphan_crops.py       # High-angle crop recovery (from pix-workers)
│       └── orphan_clusters.py    # Orphan cluster reassignment (from pix-workers)
├── matching/
│   ├── __init__.py
│   ├── selfie_matcher.py    # Cosine similarity guest matching
│   └── liveness.py          # BasicLivenessDetector
├── pipeline.py              # FaceService — orchestrates full pipeline
├── face_preprocess.py       # ArcFace alignment utils (from PicSee)
└── vendor/
    ├── adaface_insightface/  # R100/MBF backbone code (from PicSee)
    ├── cvlface_vit_kprpe/    # VIT-KPRPE model code (from pix-workers)
    ├── cvlface_dfa_mobilenet/ # DFA aligner code (from pix-workers)
    └── ypr_3ddfa_v2/         # 3DDFA_V2 code (from pix-workers)
```

## MLConfig

```python
class MLConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ML_")

    # Device
    device: str = "auto"  # "auto" | "cuda" | "cpu"

    # Model paths (relative to backend/ or absolute)
    models_dir: str = "models"
    scrfd_model: str = "det_10g.onnx"
    r100_model: str = "model_v1_scratch_training_epoch_20_r100.pt"
    adaface_model_dir: str = "cvlface_adaface_vit_base_kprpe_webface12m"
    dfa_aligner_dir: str = "cvlface_DFA_mobilenet"
    mbf_model: str = "preprocessed_transformation_mbf_model_w12m_RE10.tflite"
    blur_model: str = "blur_model_tflite_may6_ckpt49.tflite"
    ypr_tflite_model: str = "ypr_model_float32.tflite"
    ypr_3ddfa_config: str = "ypr_3ddfa_v2/resnet_config.yml"
    resnet22_onnx: str = "resnet22.onnx"
    faceboxes_onnx: str = "FaceBoxesProd.onnx"

    # Detection
    scrfd_det_thresh: float = 0.5
    scrfd_nms_thresh: float = 0.4
    scrfd_input_sizes: list[int] = [640, 128]

    # Quality thresholds
    blur_threshold: float = 0.5
    yaw_threshold: float = 45.0
    pitch_threshold: float = 35.0
    roll_threshold: float = 45.0
    age_min_threshold: int = 5       # Below this = skip
    sunglasses_threshold: float = 0.5

    # Embedding
    embedding_model: str = "dual"  # "r100" | "adaface" | "mbf" | "dual"
    embedding_batch_size: int = 64

    # Clustering
    dbscan_eps: float = 0.45
    dbscan_min_samples: int = 1
    agglo_threshold: float = 0.45
    clustering_batch_size: int = 5000
    sweeper_pyr_min: float = 47.0
    sweeper_pyr_max: float = 120.0

    # Selfie matching
    selfie_match_threshold: float = 0.55
    max_cluster_matches: int = 5

    # Liveness
    liveness_face_ratio_min: float = 0.15
    liveness_face_ratio_max: float = 0.85
    liveness_det_score_min: float = 0.7
    liveness_sharpness_min: float = 50.0
    liveness_saturation_min: float = 20.0

    # YPR model choice
    ypr_model_type: str = "3ddfa"  # "3ddfa" | "tflite"

    # Feature flags
    face_processing_enabled: bool = False
    dual_model_enabled: bool = True
    age_detection_enabled: bool = True
    sunglasses_detection_enabled: bool = True
    sweeper_enabled: bool = True
    orphan_recovery_enabled: bool = True
```

## ModelRegistry Requirements

- Thread-safe double-checked locking singleton (no `import torch` at module import time)
- `get_model(name: str)` → lazy-loads on first access via `register_model_loader()`
- Only callable from Celery workers or test code — FastAPI startup must NOT trigger model loading
- `resolved_device` property: `cuda` if available, else `mps` on Apple Silicon, else `cpu`
- `unload_all()` for graceful shutdown / test teardown

## Implementation Notes (ML-001 — completed)

**Scope delivered (foundation only):**

- `MLConfig`, `get_ml_config()`, `ModelRegistry`, `get_model_registry()`, `register_model_loader()`
- `resolve_device()` supporting `auto` / `cuda` / `mps` / `cpu`
- Empty subpackage tree (`detection/`, `quality/`, `embedding/`, `clustering/`, `matching/`, `vendor/`)
- `backend/models/README.md` with manual copy instructions for PicSee weight files
- `backend/README_ML.md` agent reference document
- Tests in `backend/tests/ml/` (config, registry, import safety, FastAPI boot)

**Deferred to later stories:**

| Item | Story |
|------|-------|
| `detection/scrfd.py`, `face_cropper.py`, `face_preprocess.py` | ML-002 |
| `register_model_loader("scrfd", ...)` and SCRFD inference | ML-002 |
| `vendor/` PicSee code copies | ML-002 through ML-004 |
| Quality modules | ML-003 |
| Embedding modules | ML-004 |
| Clustering modules | ML-005, ML-006, ML-007 |
| Matching / liveness | ML-008 |
| `pipeline.py` FaceService | ML-009 |

**Design decisions (differs from original draft):**

- Model loaders use `register_model_loader(name, fn)` instead of hardcoded `get_detector()` methods — later stories register their own loaders
- `get_model("scrfd")` raises `ModelNotRegisteredError` until ML-002 registers the loader
- Non-worker model loading: **warns** by default (local dev + pytest friendly); set `ML_STRICT_WORKER_ONLY=true` on production ML host to block
- Torch pinned to **2.6.0** (pix-workers, Python 3.10) not 2.7.1 (clustering_pipeline requires Python 3.12)
- Model weights are **not copied by the story** — developer copies manually per `backend/models/README.md`

## Create / Edit

| File | Action |
|------|--------|
| `backend/app/ml/__init__.py` | Create — export `MLConfig`, `get_model_registry` |
| `backend/app/ml/config.py` | Create — `MLConfig` pydantic-settings class |
| `backend/app/ml/model_registry.py` | Create — `ModelRegistry` singleton |
| `backend/app/ml/vendor/` | Create — placeholder; code copied in ML-002+ |
| `backend/models/README.md` | Create — manual copy instructions for weight files |

## Acceptance

- [x] `MLConfig` reads all values from env vars with `ML_` prefix; defaults match values above
- [x] `ModelRegistry` returns the same instance across threads
- [x] FastAPI starts successfully **without any model files present** on disk
- [x] `get_model(name)` lazy-loads via registered loaders; second call returns same object (tested with registered test loader; `scrfd` loader deferred to ML-002)
- [x] `resolved_device` returns `"cuda"` on GPU box, `"mps"` on Apple Silicon, `"cpu"` otherwise
- [x] Importing `backend.app.ml` does NOT import `torch`, `onnxruntime`, or `tensorflow`
