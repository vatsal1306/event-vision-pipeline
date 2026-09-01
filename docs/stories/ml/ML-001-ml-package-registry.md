# ML-001 — ML package layout, MLConfig, ModelRegistry skeleton

**Type:** Foundation  
**Depends on:** BE-001  
**Area:** `backend/app/ml/`

## Goal

Create the package tree from `docs/component_ai_ml.md` §3 and a lazy singleton `ModelRegistry` that does not load GPU models until first `get_*`. `MLConfig` with all thresholds and paths from §11.2.

## References

- `docs/component_ai_ml.md` §3, §11
- `backend/AGENTS.md` AI/ML Pipeline
- `.gitignore` `backend/models/*.pt`, `*.onnx`, `*.tflite` except optional `.gitkeep`

## Create / edit

- `app/ml/__init__.py`, `config.py`, `model_registry.py`, `pipeline.py` placeholder
- Subpackages: detection, embedding, quality, clustering, matching, liveness (empty `__init__.py`)
- Document `README` in `backend/models/` how to copy weights from PicSee `MODELS/`
- Device `cuda` if `torch.cuda.is_available()` else `cpu`

## Requirements

- Thread-safe singleton double-checked lock as in spec
- No import of onnxruntime/torch at registry import time if it slows API workers — **API processes should not load R100**. Registry is for Celery GPU/CPU workers. Provide `get_face_service()` only used from workers/tests.

## Acceptance

- [ ] `MLConfig` reads env
- [ ] Registry returns same instance
- [ ] FastAPI app still starts without model files present
