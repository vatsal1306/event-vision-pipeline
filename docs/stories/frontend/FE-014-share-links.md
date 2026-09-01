# FE-014 — Share links and download settings

**Type:** Feature  
**Depends on:** FE-011  
**Area:** event detail Share tab

## Goal

Show Master and Guest links, copy to clipboard, activate/deactivate each, global “allow original download” toggle. No QR generation.

## References

- `docs/component_frontend.md` §5.5.4
- `docs/PRD.md` §5.1.7
- URL pattern: `{APP_URL}/event/{slug}/master` and `/guest`

## Create / edit

- Share panel on `[id]/page.tsx` or `share/page.tsx`
- `frontend/src/components/dashboard/link-generator.tsx`
- API: `GET links`, toggle, `PUT settings`

## Acceptance

- [ ] Copy shows toast
- [ ] Toggles persist via mock
- [ ] Links use `NEXT_PUBLIC_APP_URL` and event slug
