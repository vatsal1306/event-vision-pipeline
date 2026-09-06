# ML-003 — Quality Filters: Blur, Head Pose (3DDFA_V2), Age, and Sunglasses

**Type:** Feature
**Depends on:** ML-001, ML-002
**Area:** `backend/app/ml/quality/`

## Goal

Implement four quality gates that filter detected face crops **before** embedding
generation. Faces failing quality checks are still counted in `photo.face_count` but
are NOT embedded — saving GPU compute and preventing low-quality embeddings from
degrading cluster accuracy.

This story ports two filters from PicSee (blur, YPR) and adds two new filters from
pix-workers production (age, sunglasses). The YPR module is upgraded from TFLite to
the more accurate 3DDFA_V2 ONNX model, with TFLite as fallback.

## Filter Summary

| Filter | Model | Source | Purpose | Threshold |
|--------|-------|--------|---------|-----------|
| **Blur** | `blur_model_tflite_may6_ckpt49.tflite` (2 MB) | PicSee `MODELS/` | Reject blurry/out-of-focus faces | score < 0.5 = blurry → reject |
| **YPR (primary)** | 3DDFA_V2: `resnet22.onnx` (70 MB) + `FaceBoxesProd.onnx` (4 MB) | pix-workers (just downloaded) | Reject extreme head poses | yaw > 45°, pitch > 35°, roll > 45° |
| **YPR (fallback)** | `ypr_model_float32.tflite` (816 KB) | PicSee `MODELS/` | CPU-only fallback if 3DDFA_V2 fails | Same thresholds |
| **Age** | `nateraw/vit-age-classifier` (auto-download from HuggingFace) | pix-workers `age_detect.py` | Flag children (age < 5) for special handling | age < 5 → flag, don't embed |
| **Sunglasses** | `glasses-detector` (pip install) | pix-workers `sunglasses_detect.py` | Flag sunglasses faces for reduced match confidence | prob ≥ 0.5 → flag (soft gate, still embed) |

## PicSee / pix-workers Source Files

| Source File | SpotMe Target | Notes |
|-------------|---------------|-------|
| PicSee notebook → `FaceModel_blur_detector` (Cell 16) | `quality/blur_detector.py` | TFLite inference, 112×112 input |
| PicSee notebook → `YPRPredictor` (Cell 15) | `quality/ypr_tflite.py` | Simple TFLite regression |
| pix-workers → `embedding/utils/YPR_MODEL_3DDFA_V2/ypr_predictor.py` | `quality/ypr_3ddfa.py` | 3D face reconstruction → pose angles |
| pix-workers → `embedding/utils/YPR_MODEL_3DDFA_V2/TDDFA_ONNX.py` | `vendor/ypr_3ddfa_v2/` | ONNX inference for 3DMM params |
| pix-workers → `embedding/utils/YPR_MODEL_3DDFA_V2/FaceBoxes/` | `vendor/ypr_3ddfa_v2/` | FaceBoxes ONNX detector for YPR |
| pix-workers → `embedding/utils/age_detect.py` | `quality/age_detector.py` | ViT age classifier |
| pix-workers → `embedding/utils/sunglasses_detect.py` | `quality/sunglasses.py` | glasses-detector wrapper |

## 3DDFA_V2 YPR Details

The 3DDFA_V2 model provides significantly more accurate head pose estimation than the
simple TFLite regressor because it performs **full 3D face reconstruction**:

1. **FaceBoxes ONNX** detects the face bounding box in the 112×112 crop
2. **ResNet22 ONNX** regresses 62 3DMM (3D Morphable Model) parameters
3. From the first 12 parameters (3×4 projection matrix), extract rotation matrix → yaw/pitch/roll angles

### Build Requirement
The 3DDFA_V2 FaceBoxes module uses a **Cython NMS extension** that must be compiled:
```bash
cd vendor/ypr_3ddfa_v2/FaceBoxes
bash build_cpu_nms.sh  # Compiles cpu_nms.pyx → .so
```
The pix-workers repo already has a pre-compiled `.so` for `x86_64-linux` at:
`pix-workers/face_rec_service/embedding/utils/YPR_MODEL_3DDFA_V2/FaceBoxes/utils/nms/cpu_nms.cpython-312-x86_64-linux-gnu.so`

For the ML server (Linux x86_64), this `.so` may be directly usable. Otherwise compile from `cpu_nms.pyx`.

### Fallback Strategy
If 3DDFA_V2 fails to initialize (missing ONNX files, Cython build failure):
- Log warning
- Fall back to TFLite YPR model automatically
- **Never crash the pipeline due to YPR model failure**

## Quality Filter Orchestrator

```python
class QualityFilter:
    """Runs all quality gates on a face crop."""

    def filter(self, face_crop: FaceCrop) -> QualityResult:
        """
        Returns QualityResult with:
        - passed: bool — whether to proceed with embedding
        - reject_reason: str | None — "blur", "ypr", "age", "sunglasses", None
        - blur_score: float
        - ypr: tuple[float, float, float] | None — (yaw, pitch, roll) in degrees
        - age: int | None
        - has_sunglasses: bool
        - metadata: dict — all raw scores for analytics
        """
```

### Filter Behavior Matrix

| Filter | On Failure | Impact on Embedding | Impact on face_count |
|--------|-----------|-------------------|---------------------|
| Blur (< 0.5) | Reject | ❌ Skip embedding | ✅ Still counted |
| YPR (exceeds thresholds) | Reject | ❌ Skip embedding | ✅ Still counted |
| Age (< 5) | Flag | ❌ Skip embedding | ✅ Still counted |
| Sunglasses (≥ 0.5) | Soft flag | ✅ Still embed | ✅ Still counted |
| YPR model error | **Pass-on-error** | ✅ Still embed | ✅ Still counted |
| Blur model error | **Pass-on-error** | ✅ Still embed | ✅ Still counted |
| Age model error | **Pass-on-error** | ✅ Still embed | ✅ Still counted |

**Critical**: Model inference failures → **pass-on-error** (log warning, don't drop faces).
This prevents transient model issues from causing data loss.

## Sweeper-Aware YPR Ranges

From pix-workers `clustering_config.py`, different pipeline stages use different YPR ranges:

| Pipeline Stage | PYR Range | Used For |
|---------------|-----------|----------|
| **Regular clustering** | 0°–47° | Primary embedding + clustering |
| **Sweeper pass** | 47°–120° | Second-pass for high-angle faces (ML-005) |
| **Selfie enrollment** | 0°–30° | Representative crop selection |

The `QualityFilter` must store raw YPR angles so downstream stages can apply their own thresholds.

## Dependencies (pip)

```
glasses-detector>=1.0     # Sunglasses detection
transformers>=4.30        # Age detection (ViT)
```

Age model auto-downloads from HuggingFace on first use (~350 MB). Pre-download in Docker build:
```dockerfile
RUN python -c "from transformers import ViTForImageClassification, ViTImageProcessor; \
    ViTForImageClassification.from_pretrained('nateraw/vit-age-classifier'); \
    ViTImageProcessor.from_pretrained('nateraw/vit-age-classifier')"
```

## Create / Edit

| File | Action |
|------|--------|
| `backend/app/ml/quality/__init__.py` | Create |
| `backend/app/ml/quality/blur_detector.py` | Create — port from PicSee `FaceModel_blur_detector` |
| `backend/app/ml/quality/ypr_3ddfa.py` | Create — port from pix-workers `ypr_predictor.py` |
| `backend/app/ml/quality/ypr_tflite.py` | Create — port from PicSee `YPRPredictor` |
| `backend/app/ml/quality/age_detector.py` | Create — port from pix-workers `age_detect.py` |
| `backend/app/ml/quality/sunglasses.py` | Create — port from pix-workers `sunglasses_detect.py` |
| `backend/app/ml/quality/quality_filter.py` | Create — orchestrator |
| `backend/app/ml/vendor/ypr_3ddfa_v2/` | Copy from pix-workers |
| Unit tests for each filter + integration test for `QualityFilter` | Create |

## Acceptance

- [ ] `QualityFilter.filter()` returns `QualityResult` with all fields populated
- [ ] Blurry crop fixture → `passed=False, reject_reason="blur"`
- [ ] Extreme-angle crop fixture → `passed=False, reject_reason="ypr"`
- [ ] All thresholds configurable via `MLConfig` env vars
- [ ] YPR model failure → `passed=True` (pass-on-error) with warning logged
- [ ] 3DDFA_V2 unavailable → automatic fallback to TFLite YPR
- [ ] Age detection disabled via `ML_AGE_DETECTION_ENABLED=false` → skipped
- [ ] Sunglasses detection is a soft flag — face still gets embedded
- [ ] Raw YPR angles stored in result for downstream sweeper use
