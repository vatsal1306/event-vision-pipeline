# BE-016 — Photographer profile, logo, watermark, storage usage

**Type:** Feature  
**Depends on:** BE-008  
**Area:** `backend/app/api/v1/profile.py`, profile methods on photographer service

## Goal

GET/PUT profile; multipart logo and watermark to assets bucket; GET storage used/limit/active/archived bytes.

## References

- `docs/component_backend.md` §6.2 Profile, §12.3 recalculate storage
- `docs/PRD.md` §5.1.6

## Create / edit

- Validate image magic bytes (not just content-type)
- Store `logo_url` / `watermark_url` as keys or CDN URLs consistently — prefer storing S3 key and presigning on read
- `recalculate_photographer_storage` after photo add/delete

## Acceptance

- [ ] PUT updates studio_name
- [ ] Watermark PNG stored and returned
- [ ] Storage numbers update after photo ingest (BE-009)
