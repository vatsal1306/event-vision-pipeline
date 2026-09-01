# FE-017 — Couple master link: OTP and full gallery

**Type:** Feature  
**Depends on:** FE-016  
**Area:** `frontend/src/app/event/[slug]/master/`

## Goal

Couple opens master link, enters name + phone + OTP, then browses **all** photos by folder with studio branding. Session persists on device.

## References

- `docs/component_frontend.md` §6.1, §6.2
- `docs/PRD.md` §5.2
- API: `GET /api/event/{slug}/info`, auth + verify `link_type=master`, `master/photos`, `master/folders`
- Public event info for landing (studio name, logo, dates)

## Create / edit

- `master/page.tsx` — auth step then gallery (or two-step client state)
- Reuse OTP patterns from photographer where possible; dark theme
- `gallery-header` with logo + event name
- Folder tabs with counts

## Requirements

- If `master_link_active` is false, show inactive message
- No selfie for couple
- SSR landing metadata if straightforward; gallery is client

## Acceptance

- [ ] OTP mock logs couple in
- [ ] All folders browsable
- [ ] Viewer + download honor event download flag
