# FE-001 — Next.js scaffold and tooling

**Type:** Foundation  
**Depends on:** none  
**Area:** `frontend/`

## Goal

Create a runnable Next.js 14+ App Router app in the monorepo `frontend/` folder with TypeScript strict mode, pnpm, Tailwind, ESLint, Prettier, and env placeholders. No product screens yet except a temporary home page that can be replaced in FE-007.

## Context

This is Component 1 of a photo delivery PWA. Backend does not exist. The app must live under `frontend/` (not repo root). Python 3.10 applies only to backend later.

## References

- `docs/component_frontend.md` §1.1, §1.4, §3, §15
- `frontend/AGENTS.md` (package manager, Node 20, App Router)
- Root `AGENTS.md` (monorepo layout)

## Create / edit

- `frontend/package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `next.config.ts` (or `.mjs`)
- `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/globals.css`
- `frontend/.env.example` with `NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_MOCK_API=true`, `NEXT_PUBLIC_APP_URL`
- Root `.gitignore`: add Node/Next entries (`node_modules/`, `.next/`, `frontend/.env.local`) without breaking existing Python ignores
- Optional: `frontend/.nvmrc` with `20`

## Requirements

- `pnpm dev` starts the app on port 3000
- TypeScript `strict: true`
- Path alias `@/` → `frontend/src/`
- `src/` directory (not files at `frontend/app/`)
- Do **not** enable MSW, Shadcn, or PWA yet (later stories)
- Do **not** add a Python backend

## Acceptance

- [ ] `pnpm install` and `pnpm dev` work
- [ ] `pnpm type-check` (or `tsc --noEmit`) passes
- [ ] App Router + TypeScript strict
- [ ] Env example documents mock-first development
