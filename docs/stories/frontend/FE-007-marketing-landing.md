# FE-007 — Marketing landing page and 404

**Type:** Feature  
**Depends on:** FE-002  
**Area:** `frontend/src/app/(marketing)/`, `frontend/src/app/not-found.tsx`

## Goal

Static marketing home and a branded 404. Placeholder product name: “AI Photo Sharing Platform”. CTAs to login/register only. No billing, no GTM copy dump required — keep it premium and short.

## References

- `docs/component_frontend.md` §2.2, §2.3 (SSG for `/`)
- `docs/PRD.md` §11 Brand (professional, invisible, photographer-first)

## Create / edit

- `frontend/src/app/(marketing)/layout.tsx`, `page.tsx`
- `frontend/src/app/not-found.tsx`
- `frontend/src/components/shared/logo.tsx`

## Requirements

- SSG-friendly (no client data fetching)
- Links: Log in, Create account
- Visual quality: generous whitespace, confident typography — not a generic SaaS template cluttered with fake logos

## Acceptance

- [ ] `/` renders a clear value proposition for photographers
- [ ] 404 is on-brand
- [ ] Works without auth
