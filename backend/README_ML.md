# ML Pipeline — Agent Reference (ML-001+)

This document tracks ML infrastructure decisions for AI agents working on later stories.

## Package Layout

```
backend/app/ml/
├── config.py           # MLConfig (pydantic-settings, ML_ env prefix)
├── device.py           # resolve_device() — cuda / mps / cpu
├── exceptions.py       # ModelNotRegisteredError, ModelLoadError
├── model_registry.py   # Thread-safe lazy singleton + register_model_loader()
├── detection/          # ML-002
├── quality/            # ML-003
├── embedding/          # ML-004
├── clustering/         # ML-005, ML-006, ML-007
├── matching/           # ML-008
└── vendor/             # PicSee / pix-workers code copies (ML-002+)
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
| `auto` | CUDA if available, else Apple MPS, else CPU |
| `cuda` | CUDA if available, else CPU |
| `mps` | Apple MPS if available, else CPU |
| `cpu` | Always CPU (no torch import required) |

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
| SCRFD detector | ML-002 |
| Face cropper | ML-002 |
| Vendor code copies | ML-002 through ML-004 |
| Model weight files on disk | Manual copy by developer |
| Quality filters | ML-003 |
| Embeddings (R100, AdaFace, MBF) | ML-004 |
| Clustering | ML-005/ML-006 |
| FaceService + Celery tasks | ML-009 |

## Testing

```bash
cd backend
uv run pytest tests/ml/ -v
```

Tests run without model files or GPU. Torch-dependent tests use `pytest.importorskip("torch")`.

## Registering a Model (for ML-002+)

```python
from app.ml.model_registry import register_model_loader, get_model_registry


def _load_scrfd(registry: ModelRegistry) -> SCRFDDetector:
    return SCRFDDetector(
        model_path=registry.config.scrfd_model_path,
        device=registry.resolved_device,
        det_thresh=registry.config.scrfd_det_thresh,
    )


register_model_loader("scrfd", _load_scrfd)

# In Celery task:
detector = get_model_registry().get_model("scrfd")
```
