# FE-002 — Design system and shared UI primitives

**Type:** Foundation  
**Depends on:** FE-001  
**Area:** `frontend/src/app/globals.css`, `frontend/src/components/ui/`, fonts

## Goal

Install the visual foundation: CSS variables for light (dashboard) and dark (gallery), Inter + Plus Jakarta Sans, Tailwind theme tokens, Shadcn/UI primitives, and shared motion tokens. Quality bar is high — this is a photo product.

## Context

Dashboard is light, spacious, card-based. Guest/couple galleries are dark (`#0a0a0a`), exhibition-like, no layout shift. Animations 200–300ms, not bouncy.

## References

- `docs/component_frontend.md` §4 (especially §4.0 Design Philosophy)
- `frontend/AGENTS.md` — Styling & Design Quality
- Shadcn components needed soon: Button, Input, Dialog, Dropdown, Tabs, Progress, Table, Form, Toast (or Sonner)

## Create / edit

- `frontend/src/app/globals.css` — `:root` and `.dark` tokens from the component doc
- `frontend/tailwind.config.ts` — fonts, display sizes, darkMode `class`
- Self-hosted or `next/font` for Inter and Plus Jakarta Sans
- `frontend/src/components/ui/*` via Shadcn
- `frontend/src/lib/motion.ts` — `fadeIn`, `slideUp`, `scaleIn` from §4.5
- `frontend/src/components/shared/loading-spinner.tsx`, `empty-state.tsx`, `error-boundary.tsx`

## Requirements

- No CSS modules / styled-components
- No hardcoded hex in feature components later — use tokens
- Toast via Sonner as specified in the component doc
- `lucide-react` for icons

## Acceptance

- [ ] Light and dark CSS variables match the spec
- [ ] Fonts load with `font-display: swap` (or next/font equivalent)
- [ ] Core Shadcn primitives exist and are importable from `@/components/ui/`
- [ ] Shared empty/loading/error primitives exist for later screens
