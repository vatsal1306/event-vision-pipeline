# FE-015 — Photographer profile, branding, storage

**Type:** Feature  
**Depends on:** FE-009  
**Area:** `frontend/src/app/dashboard/profile/`

## Goal

Edit studio name, email, phone; upload logo; upload watermark PNG; preview watermark bottom-right ~40% opacity on a sample photo; show storage used vs limit (active vs archived).

## References

- `docs/component_frontend.md` §5.6
- `docs/PRD.md` §5.1.6, §5.1.10
- API: `GET/PUT /api/profile`, logo, watermark, storage

## Create / edit

- `profile/page.tsx`
- `frontend/src/components/dashboard/watermark-preview.tsx`

## Requirements

- Watermark position fixed bottom-right, semi-transparent (no position picker)
- No custom domain UI
- Settings nav can alias to profile or a small settings section on the same page

## Acceptance

- [ ] Save profile updates mock
- [ ] Logo and watermark upload show preview
- [ ] Storage bar reflects mock bytes
