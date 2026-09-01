# ML-002 — SCRFD detection and ArcFace 112 crop

**Type:** Feature  
**Depends on:** ML-001  
**Area:** `backend/app/ml/detection/`

## Goal

Port PicSee SCRFD (`det_10g.onnx`) with multi-scale 640 and 128, det 0.5, NMS 0.4, CUDA EP with CPU fallback. `FaceCropper` 5-point `SimilarityTransform` to 112×112; bbox fallback if landmarks missing. `get_all_face_crops` behavior: all faces, not one.

## References

- `docs/component_ai_ml.md` §4 (implement DetectedFace, SCRFDDetector, FaceCropper)
- PicSee notebook SCRFD class — **match preprocess/postprocess**, do not invent a different detector

## Create / edit

- `scrfd.py`, `face_cropper.py`
- Copy `face_preprocess.py` from PicSee if that is the alignment source of truth
- Unit tests with a tiny JPEG (1 face) and a no-face image

## Requirements

- BGR numpy from cv2
- Normalized bbox 0–1 **or** pixel — pick one, document, use consistently in DB (backend schema is REAL bbox_x/y/w/h — store normalized 0–1 as the SQL comments imply)
- `max_num=0` all faces

## Acceptance

- [ ] No-face image → empty list, no exception
- [ ] Known fixture returns ≥1 face with landmarks
- [ ] Crop output shape (112, 112, 3)
