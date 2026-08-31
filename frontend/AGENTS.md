# AGENTS.md — Frontend (Next.js / TypeScript / React)

> Scoped rules for AI agents working on `frontend/` code.  
> For project-wide context and universal standards, see the root `AGENTS.md`.  
> For detailed architecture and screen specs, see `docs/component_frontend.md`.

---

## Technology Constraints

- **Framework:** Next.js 14+ with App Router. Do not use Pages Router.
- **Language:** TypeScript in strict mode. No `any` type — use `unknown` and narrow with type guards.
- **Styling:** Tailwind CSS + Shadcn/UI. No CSS modules, no styled-components, no inline `style={}` except for truly dynamic values (e.g., width from API data).
- **Package manager:** pnpm.
- **Node version:** 20 LTS.

---

## Next.js Patterns

- All routes live under `src/app/` using the App Router file convention.
- **Server Components by default.** Only add `"use client"` when the component needs React hooks, DOM event handlers, or browser-only APIs (camera, localStorage, IntersectionObserver).
- Use `next/image` for every `<img>`. Always provide `width`, `height`, `alt`, and `sizes` for responsive images.
- **Dynamic imports** (`next/dynamic` with `ssr: false`) for heavy client-only components: upload dropzone, camera/selfie capture, framer-motion animations, virtualized grids.
- Route groups: `(marketing)/` for public pages, `(auth)/` for login/register, `dashboard/` for photographer, `event/[slug]/` for guest/couple.

---

## Component Conventions

```tsx
// One component per file. Named export matching filename.
// Path: frontend/src/components/dashboard/event-card.tsx

interface EventCardProps {
  event: EventSummary;
  onSelect: (id: string) => void;
}

export function EventCard({ event, onSelect }: EventCardProps) {
  // Component body
}
```

- **One component per file.** Named export, not default export.
- **Props interface** defined in the same file, directly above the component.
- **Composition over prop-drilling.** If a component has 10+ props, it needs decomposition or composition via `children` / render props.
- **Extract custom hooks** when component logic exceeds ~20 lines of non-JSX code. Place hooks in `src/hooks/`.
- **Shadcn/UI as base layer.** Import from `@/components/ui/`. Customize appearance via Tailwind classes and CSS variables, not by forking the component internals.

---

## State Management

| State Type | Tool | Rule |
|-----------|------|------|
| Server/API data | `@tanstack/react-query` | **Never** store API data in Zustand. React Query handles caching, refetching, and stale-while-revalidate. |
| Client UI state | `zustand` | Upload progress, modal open/close, sidebar collapsed, theme toggle. |
| URL state | `useSearchParams` / router | Filters, pagination, sort order, active folder. Keep state shareable via URL. |
| Form state | React Hook Form + Zod | All forms validated with Zod schemas. Use `z.infer<typeof schema>` for types. |

---

## Styling & Design Quality

This is a **photo platform** — visual quality is paramount.

### Gallery UI (Guest & Couple Pages)

- **Masonry grid** with consistent gutter spacing. Photos should feel like a curated exhibition, not a file browser.
- **Smooth animations:** Use `framer-motion` for page transitions, image reveal on scroll (subtle fade + scale), and photo viewer open/close. Animations must be tasteful — subtle and fast (200–300ms), not playful or bouncy.
- **Photo viewer:** Full-screen overlay, smooth pinch-to-zoom, swipe navigation with spring physics. Backdrop blur on open. Close on swipe-down gesture.
- **No layout shifts.** Every image slot must have a defined aspect ratio (via `aspect-ratio` CSS or padding-bottom hack) and a blurhash/shimmer placeholder before the image loads.
- **Typography:** Clean sans-serif (Inter or Plus Jakarta Sans). Large, confident headings. Generous line-height for readability.
- **Loading states:** Skeleton screens with subtle shimmer animation, not spinners. Show structure before content.

### Dashboard UI (Photographer)

- **Light theme** by default, clean and spacious. Generous whitespace.
- **Card-based layouts** for event lists. Clear visual hierarchy.
- **Upload interface:** Must feel responsive and reliable. Real-time progress bars per file, overall progress, speed indicator. Error states must be clear (red badge, retry button) without being alarming.
- **Data tables** (guest list, analytics): clean borders, hover highlights, sortable columns with visible sort indicators.

### Responsive Design

- **Guest/couple pages:** Mobile-first (`min-width` breakpoints). Must be flawless on iPhone SE (375px) through iPad (768px). Desktop is secondary.
- **Dashboard:** Desktop-first. Must be functional on tablets (768px+). Collapsible sidebar at tablet widths.
- **Photo grid columns:** 2 (mobile) → 3 (tablet) → 4-6 (desktop). Adapt based on viewport width and context.

### Performance Targets

- LCP < 2.5s on 4G.
- CLS < 0.1 (no layout jumps as images load).
- 60fps scrolling in photo grids (virtualize lists with 100+ items using `@tanstack/react-virtual`).
- Guest route JS bundle < 150KB gzipped. Dashboard < 300KB.

---

## API Integration

- Central API client in `src/lib/api-client.ts` wrapping `fetch`. Auto-injects auth tokens, handles 401 refresh, normalizes errors.
- All API response types defined in `src/types/api.ts`.
- **Mock data phase:** Use MSW (Mock Service Worker) in `src/mocks/`. Toggle via `NEXT_PUBLIC_MOCK_API=true`. When backend is ready, flip to `false` — zero code changes in components.

---

## File Naming

- Components: `kebab-case.tsx` (e.g., `event-card.tsx`, `upload-dropzone.tsx`)
- Hooks: `use-kebab-case.ts` (e.g., `use-upload.ts`, `use-camera.ts`)
- Stores: `kebab-case-store.ts` (e.g., `auth-store.ts`, `upload-store.ts`)
- Types: `kebab-case.ts` (e.g., `event.ts`, `api.ts`)
- Utils: `kebab-case.ts` (e.g., `slug.ts`, `image-utils.ts`)

---

## Things to Avoid

- No `any`. Use `unknown` and narrow with type guards.
- No `console.log` in committed code. Use a logger or remove.
- No hardcoded colors. Use Tailwind theme tokens and CSS variables.
- No pixel values for spacing. Use Tailwind spacing scale (`p-4`, `gap-6`, not `padding: 16px`).
- No `useEffect` for data fetching. Use React Query.
- No prop-drilling beyond 2 levels. Introduce context or composition.
