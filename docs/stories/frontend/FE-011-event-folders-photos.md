# FE-011 — Event detail: folders and photo grid

**Type:** Feature  
**Depends on:** FE-010  
**Area:** `frontend/src/app/dashboard/events/[id]/`

## Goal

Event hub with tabs. Photos tab: nested folder tree (Mehndi/Haldi/etc.), create/rename/delete/reorder folders, virtualized photo grid, multi-select move/delete, photo metadata viewer (not the public lightbox).

## References

- `docs/component_frontend.md` §5.5, §5.5.1
- `docs/PRD.md` §5.1.3
- API: folders CRUD, `GET photos`, `POST photos/move`, `DELETE photo`

## Create / edit

- `frontend/src/app/dashboard/events/[id]/page.tsx` — tabs: Photos | Upload | Analytics | Share (Upload/Analytics/Share can be placeholders linking to subroutes)
- `frontend/src/components/dashboard/folder-tree.tsx`, `photo-grid.tsx`
- URL: `?folderId=` for active folder
- `@tanstack/react-virtual` for grid
- `next/image` + blurhash placeholder

## Requirements

- Nested folders; “All Photos” root
- Drag-and-drop between folders if reasonable; otherwise move via toolbar is enough for Phase 1 if DnD is risky — prefer both if time allows; **must** have multi-select move
- Face count badge on thumbs
- Infinite scroll / load more using offset pagination

## Acceptance

- [ ] Folder tree matches mock hierarchy
- [ ] Filtering by folder works
- [ ] Move and delete work against MSW
- [ ] Grid stays smooth with 200+ mocks
