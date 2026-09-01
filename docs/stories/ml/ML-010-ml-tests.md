# ML-010 — ML tests, fixtures, CI skip rules

**Type:** Hardening  
**Depends on:** ML-008  
**Area:** `backend/tests/ml/`

## Goal

Unit tests for detection/embedding/clustering/matching without requiring GPU. Integration test full pipeline marked `@pytest.mark.ml` skipped if `RUN_ML_TESTS!=1` or weights missing. Fixtures: small images with known face counts.

## References

- `docs/component_ai_ml.md` §13, §15
- Do not commit large private wedding photos

## Create / edit

- `tests/ml/fixtures/` synthetic or CC0 faces
- Mock SCRFD in clustering tests

## Acceptance

- [ ] Default CI pytest excludes slow GPU tests
- [ ] `RUN_ML_TESTS=1` path documented in backend README
