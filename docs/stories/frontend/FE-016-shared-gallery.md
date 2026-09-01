# FE-016 — Shared gallery grid, lightbox, download

**Type:** Feature  
**Depends on:** FE-002, FE-005  
**Area:** `frontend/src/components/gallery/`

## Goal

Reusable dark-theme masonry (or justified) grid, full-screen viewer (swipe, pinch-zoom, spring), download button that requests original via API (loading then save). Used by couple and guest stories.

## References

- `docs/component_frontend.md` §4.0, §6.2, §7.4, §7.5, §12
- `frontend/AGENTS.md` gallery quality bar
- Libraries: framer-motion, react-virtual, next/image

## Create / edit

- `gallery-grid.tsx`, `photo-viewer.tsx`, `gallery-header.tsx`, `download-button.tsx`, `folder-nav.tsx`
- `frontend/src/components/shared/responsive-image.tsx`

## Requirements

- Dark background, blurhash/shimmer, no CLS
- Column counts per §4.4
- Download: spinner while fetching; hide download if `downloadEnabled` false
- Keyboard: arrows, Escape (a11y §14)
- Dynamic import viewer if heavy

## Acceptance

- [ ] Grid + viewer can be demoed on a throwaway page or couple page
- [ ] 60fps-ish scroll with virtualization
- [ ] Download triggers the download endpoint (mock blob or URL)
