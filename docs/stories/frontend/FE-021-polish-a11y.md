# FE-021 — Empty, error, loading polish and accessibility

**Type:** Hardening  
**Depends on:** FE-010 through FE-019  
**Area:** all user-facing routes

## Goal

Production-feeling states: skeletons for grids and dashboards, empty events/folders/matches, API errors with retry, focus management in dialogs and photo viewer, WCAG AA contrast, keyboard gallery.

## References

- `docs/component_frontend.md` §12, §14
- `frontend/AGENTS.md` loading states (skeletons, not spinners for pages)

## Create / edit

- Reuse `empty-state`, `error-boundary`
- Audit forms for labels
- `prefers-reduced-motion`: shorten or disable non-essential animations

## Out of scope

- Full i18n (English only; keep strings in constants if easy)

## Acceptance

- [ ] No raw error dumps in UI
- [ ] Viewer keyboard + Escape
- [ ] Empty and loading states on main list/gallery screens
