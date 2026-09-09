# ML-002 — SCRFD Face Detection and ArcFace 112×112 Crop

**Type:** Feature
**Depends on:** ML-001
**Area:** `backend/app/ml/detection/`

## Goal

Port the PicSee SCRFD face detector and `FaceCropper` alignment module to produce
112×112 ArcFace-aligned face crops from raw event photos. Multi-scale detection
(640 + 128) ensures both large close-up faces and small distant faces in group shots
are captured.

## PicSee Source Files

| PicSee File | SpotMe Target | Notes |
|-------------|---------------|-------|
| `clustering_pipeline/fixed_fr_id_cluster_merge_final.ipynb` → SCRFD class (Cells 2–8) | `backend/app/ml/detection/scrfd.py` | ONNX-based, multi-scale autodetect |
| `clustering_pipeline/fixed_fr_id_cluster_merge_final.ipynb` → FaceCropper class (Cells 9–12) | `backend/app/ml/detection/face_cropper.py` | 5-point landmark alignment |
| `clustering_pipeline/adaface_insightface/face_preprocess.py` | `backend/app/ml/face_preprocess.py` | `SimilarityTransform`-based alignment |
| `pix-workers/face_rec_service/embedding/utils/face_cropper.py` | Reference for production behavior | Same logic, cleaned up |

## Model File

| File | Source | Size | Format |
|------|--------|------|--------|
| `det_10g.onnx` | `clustering_pipeline/MODELS/` | 16 MB | ONNX |

## SCRFD Implementation Details

```python
class SCRFDDetector:
    """SCRFD multi-scale face detector using ONNX Runtime."""

    DEFAULT_DET_THRESH = 0.5
    NMS_THRESH = 0.4
    INPUT_SIZES = [640, 128]  # Multi-scale: large faces + small distant faces

    def detect(self, image_bgr: np.ndarray) -> list[DetectedFace]:
        """
        Detect all faces in a BGR image.

        Returns list of DetectedFace with:
        - bbox: normalized [x, y, w, h] in 0–1 range
        - landmarks: 5-point array [[x1,y1], ..., [x5,y5]] in pixel coords
        - score: detection confidence float
        """
```

### Multi-scale Strategy (from PicSee)
1. Run SCRFD at 640×640 → catches large/medium faces
2. Run SCRFD at 128×128 → catches small distant faces in group shots
3. Combine detections with NMS to remove duplicates
4. Return all faces (not just the largest/center one — that's PicSee production behavior)

### Key Differences from pix-workers
- pix-workers `FaceCropper.get_all_face_crops(img, get_faces=1)` picks one face (closest to center) for selfie crops
- SpotMe upload pipeline: **detect ALL faces** (`get_faces=0`)
- SpotMe selfie matching: **detect ONE face** (`get_faces=1`, largest or center)

## FaceCropper Implementation

```python
class FaceCropper:
    """Crops and aligns faces to 112×112 using ArcFace 5-point landmark template."""

    ARCFACE_TEMPLATE = np.array([
        [38.2946, 51.6963], [73.5318, 51.5014],
        [56.0252, 71.7366], [41.5493, 92.3655],
        [70.7299, 92.2041]
    ], dtype=np.float32)

    def crop_all(self, image_bgr: np.ndarray, detected_faces: list[DetectedFace]) -> list[FaceCrop]:
        """
        Crop and align all detected faces.

        Each FaceCrop contains:
        - aligned_face: (112, 112, 3) BGR numpy array
        - source_detection: reference to the DetectedFace
        - alignment_matrix: the SimilarityTransform used
        """
```

### Alignment Algorithm (must match PicSee exactly)
1. Use `skimage.transform.SimilarityTransform` to estimate transform from 5 landmarks → ArcFace template
2. Apply `cv2.warpAffine` with the estimated matrix
3. Output: 112×112 BGR crop
4. **Fallback**: if landmarks are missing, use bbox center-crop + resize (rare edge case)

## Data Classes

```python
@dataclass
class DetectedFace:
    bbox: np.ndarray          # [x, y, w, h] normalized 0–1
    bbox_pixel: np.ndarray    # [x, y, w, h] in pixel coords
    landmarks: np.ndarray     # shape (5, 2), pixel coords
    score: float              # detection confidence

@dataclass
class FaceCrop:
    aligned_face: np.ndarray  # (112, 112, 3) BGR
    source_detection: DetectedFace
    source_photo_id: uuid.UUID | None = None
```

## Create / Edit

| File | Action |
|------|--------|
| `backend/app/ml/detection/__init__.py` | Create |
| `backend/app/ml/detection/scrfd.py` | Create — port SCRFD from PicSee notebook |
| `backend/app/ml/detection/face_cropper.py` | Create — port FaceCropper from PicSee |
| `backend/app/ml/face_preprocess.py` | Copy from `clustering_pipeline/adaface_insightface/face_preprocess.py` |
| Unit tests with a 1-face JPEG and a 0-face JPEG | Create |

## Requirements

- Input: BGR numpy array from `cv2.imdecode` (raw photo bytes → numpy)
- ONNX Runtime execution providers: `["CUDAExecutionProvider", "CPUExecutionProvider"]` with automatic fallback
- Store **normalized 0–1 bbox** in DB (matches `face_embeddings.bbox_x/y/w/h` REAL columns)
- Return **pixel-coord landmarks** for alignment (not stored in DB)
- HEIC/HEIF: handled upstream by photo processing (convert to JPEG/PNG before detection)
- Thread-safe: ONNX session is shareable across threads

## Implementation Notes (ML-002 — completed)

**Source:** Ported from pix-workers `face_rec_service/embedding/utils/face_cropper.py` (SCRFD +
`estimate_norm`/`norm_crop` alignment). Legacy `face_preprocess.preprocess()` copied from
PicSee `clustering_pipeline/adaface_insightface/face_preprocess.py` for bbox-only fallback.

**Design decisions:**

| Topic | Decision |
|-------|----------|
| ONNX providers | CUDA → CPU; **no CoreML on Mac** (SCRFD 128×128 incompatible with CoreML EP) |
| Alignment path | Primary: pix-workers `norm_crop` (ArcFace template). Fallback: PicSee `preprocess()` bbox crop |
| Bbox clipping | Raw SCRFD boxes clipped to image bounds before normalizing to `[0, 1]` for DB storage |
| Registry | `register_model_loader("scrfd", ...)` in `detection/registry.py`; import `app.ml.detection` to register |
| Selfie vs upload | `crop_all()` = all faces; `crop_primary()` = nose-closest-to-center (pix-workers `get_faces=1`) |

**Tests:** `tests/ml/test_scrfd_crop.py` + fixtures in `tests/ml/fixtures/`. PicSee parity test
compares bbox/landmarks/score against pix-workers SCRFD on the same image.

## Acceptance

- [x] No-face image → empty list, no exception
- [x] Known fixture (1-face photo) → exactly 1 `DetectedFace` with 5 landmarks
- [x] Crop output shape is `(112, 112, 3)` dtype `uint8`
- [x] Group photo fixture (3+ faces) → 3+ detections
- [x] Normalized bbox values are all in `[0.0, 1.0]` (clipped to image bounds)
- [x] Multi-scale detects small faces that single 640×640 pass misses
