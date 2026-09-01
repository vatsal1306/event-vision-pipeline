# ML-007 — Selfie matching and basic liveness

**Type:** Feature  
**Depends on:** ML-002, ML-004, ML-006  
**Area:** `backend/app/ml/matching/selfie_matcher.py`, `liveness/basic_liveness.py`

## Goal

Detect best face, crop, quality (lenient messaging), embed, cosine vs cluster centroids threshold 0.55, max 5 clusters, load distinct photo_ids. Alternative SQL `<=>` operator isolated in one method. `BasicLivenessDetector`: face size 15–85%, det score 0.7, Laplacian 50, saturation > 20.

## References

- `docs/component_ai_ml.md` §8–9
- Liveness is **quality**, not a hard security product

## Create / edit

- `MatchResult` statuses exactly as spec
- If liveness fails, return status that frontend can map (e.g. `low_quality`) with failed_checks

## Acceptance

- [ ] Synthetic centroid identical to query → matched
- [ ] Far vector → no_match
- [ ] Blank image → no_face_detected
