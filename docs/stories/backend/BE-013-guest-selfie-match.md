# BE-013 — Guest selfie ingest and matched photo API

**Type:** Feature  
**Depends on:** BE-012; **ML-008 only when an ML host exists**. Until then implement the API with a **stub FaceService** (`status=no_match` or `not_implemented`) so the guest UI can be wired. Do not load PyTorch on the app EC2.  
**Area:** `backend/app/api/v1/guest.py`, `guest_service.py`

## Goal

`POST /event/{slug}/selfie` (multipart image, guest JWT): liveness + match via FaceService, store `selfie_embedding`, `matched_cluster_ids`, `matched_photo_count`, delete selfie object after embedding. `GET guest/photos` returns only matched completed photos. Download originals with analytics.

## References

- `docs/component_backend.md` §6.2 selfie + guest photos
- `docs/component_ai_ml.md` §8, §9, §10
- `docs/PRD.md` §5.3.2–5.3.4
- Match statuses: matched, no_match, no_face_detected, low_quality, processing

## Create / edit

- If ML worker is async, return `processing` and poll — **Phase 1 preferred sync match** because pre-indexed clusters make it fast (<2s). Run match in-request with timeout; if GPU contended, 503 retry.
- Empty clusters → `no_clusters`
- Guest cannot list unmatched photos

## Acceptance

- [ ] Integration test with mocked FaceService returning photo ids
- [ ] GET photos empty on no_match
- [ ] Download disabled honored
