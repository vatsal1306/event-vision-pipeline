# BE-011 — Share links and event settings

**Type:** Feature  
**Depends on:** BE-005  
**Area:** `backend/app/api/v1/sharing.py`, `backend/app/services/sharing_service.py`

## Goal

GET master + guest URLs; toggle each link active; PUT `download_enabled`. Public `GET /api/v1/event/{slug}/info` for landing pages (no secrets).

## References

- `docs/component_backend.md` §6.2 Sharing + EventPublicInfo
- `docs/PRD.md` §5.1.7
- Inactive link: guest/couple auth must fail with clear code (enforce in BE-012)

## Create / edit

- Photographer-only mutating routes on `/api/v1/events/{id}/...`
- Public info: name, dates, studio_name, studio_logo_url (presign logo), flags

## Acceptance

- [ ] Toggle persists
- [ ] Public info works without JWT
- [ ] Unknown slug 404
