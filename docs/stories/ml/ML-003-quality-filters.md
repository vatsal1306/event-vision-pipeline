# ML-003 — Blur and head-pose quality gates

**Type:** Feature  
**Depends on:** ML-001  
**Area:** `backend/app/ml/quality/`

## Goal

TFLite blur classifier and YPR estimator from PicSee weights. `QualityFilter` combines them. Defaults: blur 0.5, yaw 45, pitch 35, roll 45. YPR model failure **must not crash** — PicSee returned pass with None; production should log warning and **pass** (lenient) OR fail closed — **use pass-on-YPR-error** to match PicSee and avoid dropping good faces.

## References

- `docs/component_ai_ml.md` §6
- PicSee `REJECTED_IMAGES` logic — we do not copy to folders; we skip embedding and still may increment detected face_count on photo

## Create / edit

- `blur_detector.py`, `pose_estimator.py`, `QualityResult` dataclass
- Tests with mock interpreter if tflite files absent in CI (skip or inject fake)

## Acceptance

- [ ] `QualityFilter.filter` returns passed/reason
- [ ] Thresholds from MLConfig
