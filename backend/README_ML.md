# ML Pipeline — Agent Reference (ML-001+)

This document tracks ML infrastructure decisions for AI agents working on later stories.

## Package Layout

```
backend/app/ml/
├── config.py           # MLConfig (pydantic-settings, ML_ env prefix)
├── device.py           # resolve_device() — cuda / mps / cpu
├── exceptions.py       # ModelNotRegisteredError, ModelLoadError
├── model_registry.py   # Thread-safe lazy singleton + register_model_loader()
├── detection/          # ML-002 — SCRFD + FaceCropper (done)
│   ├── scrfd.py
│   ├── face_cropper.py
│   ├── types.py
│   ├── onnx_providers.py
│   └── registry.py
├── face_preprocess.py  # ML-002 — ArcFace alignment utils
├── quality/            # ML-003 — blur, YPR, age, sunglasses (done)
│   ├── blur_detector.py
│   ├── ypr_3ddfa.py
│   ├── ypr_tflite.py
│   ├── age_detector.py
│   ├── sunglasses.py
│   ├── quality_filter.py
│   ├── types.py
│   └── registry.py
├── embedding/          # ML-004
├── clustering/         # ML-005, ML-006, ML-007
├── matching/           # ML-008
└── vendor/             # PicSee / pix-workers code copies
    └── ypr_3ddfa_v2/   # 3DDFA FaceBoxes + TDDFA ONNX (ML-003)
```

Model weight files live in `backend/models/` (git-ignored).

## Configuration

- **Class:** `app.ml.config.MLConfig`
- **Accessor:** `get_ml_config()` (cached singleton)
- **Env prefix:** `ML_` (e.g. `ML_DEVICE=cpu`, `ML_BLUR_THRESHOLD=0.6`)
- **Path resolution:** Relative paths resolve against `backend/` via `models_path` and `resolve_model_path()`

### Device Selection

`ML_DEVICE` accepts `auto`, `cuda`, `mps`, or `cpu`.

| Value | Behaviour |
|-------|-----------|
| `auto` | CUDA if available, else CPU for ONNX; PyTorch still uses MPS on Apple Silicon |
| `cuda` | CUDA if available, else CPU |
| `mps` | PyTorch on Apple MPS; **ONNX SCRFD uses CPU** (CoreML EP breaks 128×128 pass) |
| `cpu` | Always CPU |

Use `ModelRegistry.resolved_device` or `resolve_device(config.device)` — both lazy-import torch.

## Model Registry

- **Accessor:** `get_model_registry()`
- **Pattern:** Later stories call `register_model_loader("scrfd", loader_fn)` at module import time
- **Loading:** `registry.get_model("scrfd")` lazy-loads once per process, thread-safe
- **Teardown:** `registry.unload_all()` for tests and worker shutdown

### Worker Context Policy (ML-001 decision)

- **Default:** Warn but allow model loading outside Celery workers (local dev + pytest)
- **Strict mode:** Set `ML_STRICT_WORKER_ONLY=true` to block non-worker loads (production ML host)
- FastAPI startup never calls `get_model()` — models load only when explicitly requested

## Dependencies

ML packages are optional. Install with:

```bash
cd backend
uv sync --extra dev --extra ml
```

### Pinned Versions (PicSee compatibility, Python 3.10)

| Package | Version | Source |
|---------|---------|--------|
| torch | 2.6.0 | pix-workers production |
| torchvision | 0.21.0 | pix-workers production |
| onnxruntime | >=1.20.1 | pix-workers + clustering_pipeline |
| tensorflow | >=2.16 | TFLite models (blur, YPR, MBF) |

> Note: `clustering_pipeline` pins torch 2.7.1 but requires Python 3.12. We use pix-workers'
> torch 2.6.0 for Python 3.10 compatibility.

## What ML-001 Delivered vs Deferred

| Delivered (ML-001) | Deferred to |
|--------------------|-------------|
| `MLConfig` with all thresholds/paths | — |
| `ModelRegistry` singleton + loader registration API | — |
| Empty subpackage tree | — |
| `resolve_device()` with cuda/mps/cpu | — |
| Import safety (no torch/onnx/tf at import) | — |
| SCRFD detector + FaceCropper | ML-002 (done) |
| Vendor code copies | ML-003 (ypr_3ddfa_v2), ML-004 |
| Model weight files on disk | Manual copy by developer |
| Quality filters | ML-003 (done) |
| Embeddings (R100, AdaFace, MBF) | ML-004 |
| Clustering | ML-005/ML-006 |
| FaceService + Celery tasks | ML-009 |

## ML-003 — Quality Filters

| Module | Purpose |
|--------|---------|
| `quality/blur_detector.py` | TFLite blur score — reject when score **>** `ML_BLUR_THRESHOLD` |
| `quality/ypr_3ddfa.py` | 3DDFA_V2 ONNX YPR (primary) + unified `YPRPredictor` |
| `quality/ypr_tflite.py` | TFLite YPR fallback |
| `quality/age_detector.py` | Local ViT snapshot (`ML_AGE_MODEL_DIR`, default `vit-age-classifier`) |
| `quality/sunglasses.py` | Optional `glasses-detector` (Python 3.12+ only; inactive on 3.10) |
| `quality/quality_filter.py` | Orchestrator with early exit + pass-on-error |
| `quality/registry.py` | Registers `blur_detector`, `ypr_predictor`, `age_detector`, `sunglasses_detector`, `quality_filter` |

### Model Files

| File | Location |
|------|----------|
| Blur TFLite | `models/blur_model_tflite_may6_ckpt49.tflite` |
| YPR TFLite fallback | `models/ypr_model_float32.tflite` |
| 3DDFA ResNet22 | `models/resnet22.onnx` |
| FaceBoxes | `models/FaceBoxesProd.onnx` |
| 3DDFA config + stats | `models/ypr_3ddfa_v2/resnet_config.yml`, `param_mean_std_62d_120x120.pkl` |
| Age ViT snapshot | `models/vit-age-classifier/` (local HuggingFace export) |

Download age model once:

```bash
cd backend
huggingface-cli download nateraw/vit-age-classifier \
  --local-dir models/vit-age-classifier \
  --local-dir-use-symlinks False
```

Keep `config.json`, `preprocessor_config.json`, and `model.safetensors` (drop duplicate `pytorch_model.bin` to save space).

### Filter Behaviour

| Gate | Hard reject? | Embedding |
|------|--------------|-----------|
| Blur (score > threshold) | Yes (`reject_reason="blur"`) | Skip |
| YPR (angle exceeds thresholds) | Yes (`reject_reason="ypr"`) | Skip |
| Age (< `ML_AGE_MIN_THRESHOLD`) | Yes (`reject_reason="age"`) | Skip |
| Sunglasses | No — soft flag only | Still embed |
| Model inference error | No — pass-on-error | Still embed |

**Early exit:** blur → YPR → age → sunglasses. Later gates are skipped after a hard reject.

**Blur semantics (PicSee production):** higher score = blurrier. Reject when `blur_score > ML_BLUR_THRESHOLD` (default `0.5`). Story wording was imprecise; implementation follows PicSee.

**YPR fallback:** TFLite is used only when 3DDFA **fails to initialize** or throws at runtime. When 3DDFA finds no face in the crop, we **pass-on-error** (do not fall back to TFLite).

**3DDFA NMS on macOS:** vendored FaceBoxes uses pure-Python NMS (`py_cpu_nms`) when the Cython extension is unavailable.

**Registry fix (ML-003):** `ModelRegistry` uses `threading.RLock` so composite loaders (e.g. `quality_filter`) can call `get_model()` recursively.

### Usage

```python
import app.ml.detection   # scrfd loader
import app.ml.quality.registry  # quality loaders
from app.ml.model_registry import get_model_registry

registry = get_model_registry()
quality = registry.get_model("quality_filter")

result = quality.filter(face_crop)
if result.passed:
    ...  # proceed to embedding in ML-004
```

Config flags: `ML_AGE_DETECTION_ENABLED`, `ML_SUNGLASSES_DETECTION_ENABLED`, `ML_YPR_MODEL_TYPE` (`3ddfa` | `tflite`).

### Testing

```bash
cd backend
uv run pytest tests/ml/test_quality_filter_unit.py tests/ml/test_quality_integration.py -v
uv run pytest tests/ml/test_age_detector_integration.py -v  # loads ViT; run separately if TF/torch conflict
```

Run age integration test separately from SCRFD tests if you see a Torch/Triton registration error (known TF+torch coexistence issue in one pytest process).

## ML-002 — Detection and Cropping

| Module | Purpose |
|--------|---------|
| `detection/scrfd.py` | `SCRFDDetector` — multi-scale ONNX SCRFD (640+128) |
| `detection/face_cropper.py` | `crop_all()`, `crop_primary()`, detect+crop helpers |
| `detection/types.py` | `DetectedFace`, `FaceCrop` |
| `detection/onnx_providers.py` | CUDA / CoreML / CPU provider selection |
| `detection/registry.py` | Auto-registers `scrfd` loader |
| `face_preprocess.py` | `norm_crop` (pix-workers) + legacy `preprocess()` (PicSee fallback) |

**PicSee parity:** Ported from pix-workers `SCRFD` + `norm_crop`. Parity test in
`tests/ml/test_scrfd_crop.py` compares bbox/landmarks/score against pix-workers on the same image.

**Bbox clipping:** Raw SCRFD boxes are clipped to image bounds before normalizing to `[0, 1]` for DB.

### Usage

```python
import cv2
import app.ml.detection  # registers scrfd loader
from app.ml.detection import FaceCropper
from app.ml.model_registry import get_model_registry

detector = get_model_registry().get_model("scrfd")
image = cv2.imread("photo.jpg")
faces = detector.detect(image)

cropper = FaceCropper(detector=detector)
all_crops = cropper.crop_all(image, faces)       # upload: every face
selfie = cropper.crop_primary(image, faces)      # selfie: nose-closest-to-center
```

## Testing

```bash
cd backend
uv sync --extra dev --extra ml
uv run pytest tests/ml/ -v
```

SCRFD integration tests need `backend/models/det_10g.onnx`. Set `RUN_ML_TESTS=0` to skip without models.
Fixtures: `tests/ml/fixtures/` (see `tests/ml/fixtures/README.md`).

## Registering Models

SCRFD is registered automatically via `import app.ml.detection`. Later stories add their own loaders in
`detection/registry.py` or sibling `registry.py` modules.
