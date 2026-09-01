# BE-006 — Nested event folders

**Type:** Feature  
**Depends on:** BE-005  
**Area:** `backend/app/api/v1/folders.py`, `backend/app/services/folder_service.py`

## Goal

Hierarchical folders per event: create, rename, reorder, reparent, delete. GET returns nested `FolderTree` with `photo_count`.

## References

- `docs/component_backend.md` §6.2 Folders
- `docs/PRD.md` §5.1.3

## Create / edit

- Prevent cycles when `parent_id` changes (walk ancestors)
- Delete: `?delete_photos=true` deletes photos; otherwise photos `folder_id` SET NULL (root)
- `sort_order` integer
- Unique name among siblings (same parent)

## Requirements

- All operations scoped to event + photographer ownership
- `photo_count` via grouped query, not loading all photos
- Max depth: document a sane limit (e.g. 10) to avoid abuse

## Acceptance

- [ ] Tree JSON matches nested schema
- [ ] Move folder under descendant is rejected
- [ ] Delete without delete_photos keeps photos at root
