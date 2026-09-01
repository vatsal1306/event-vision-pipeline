# FE-018 — Couple favorites

**Type:** Feature  
**Depends on:** FE-017  
**Area:** `frontend/src/components/couple/`

## Goal

Heart/star on photos; optimistic toggle; Favorites view across folders. Server-persisted per couple session. No share-favorites feature.

## References

- `docs/component_frontend.md` §6.3, §9.3 optimistic favorite example
- `docs/PRD.md` §5.2.3
- API: `POST .../favorite`, `GET .../favorites`

## Create / edit

- `favorites-button.tsx`, `favorites-gallery.tsx`
- Empty state copy from spec

## Acceptance

- [ ] Toggle updates UI immediately and survives refresh (mock)
- [ ] Favorites section lists only marked photos
