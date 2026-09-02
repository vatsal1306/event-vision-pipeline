# ML Model Weights

This directory contains model weight files used by the AI/ML pipeline.
These files are **git-ignored** — they must be downloaded or copied manually.

## Required Models

| File | Source | Size | Purpose |
|------|--------|------|---------|
| `det_10g.onnx` | PicSee `MODELS/det_10g.onnx` | ~16 MB | SCRFD face detection |
| `model_v1_scratch_training_epoch_20_r100.pt` | PicSee `MODELS/` | ~250 MB | InsightFace R100 embeddings (GPU) |
| `blur_model_tflite_may6_ckpt49.tflite` | PicSee `MODELS/` | ~2 MB | Blur quality classifier |
| `ypr_model_float32.tflite` | PicSee `MODELS/` | ~3 MB | Head pose estimator (yaw/pitch/roll) |

## Optional Models

| File | Source | Size | Purpose |
|------|--------|------|---------|
| `adaface_insightface/` | PicSee `MODELS/adaface_insightface/` | ~250 MB | AdaFace alternative embeddings |

## Setup

Copy from the PicSee clustering pipeline models directory:

```bash
# Adjust the source path to match your PicSee installation
PICSEE_MODELS="/path/to/picsee/clustering_pipeline/MODELS"

cp "$PICSEE_MODELS/det_10g.onnx" .
cp "$PICSEE_MODELS/model_v1_scratch_training_epoch_20_r100.pt" .
cp "$PICSEE_MODELS/blur_model_tflite_may6_ckpt49.tflite" .
cp "$PICSEE_MODELS/ypr_model_float32.tflite" .

# Optional: AdaFace
cp -r "$PICSEE_MODELS/adaface_insightface" .
```

## Verification

After copying, verify the models are detected:

```bash
cd backend/
uv run python -c "from app.ml.config import get_ml_config; c = get_ml_config(); print(f'SCRFD: {c.scrfd_model_path}')"
```
