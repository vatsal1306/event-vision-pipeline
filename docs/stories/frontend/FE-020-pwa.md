# FE-020 — PWA manifest and caching

**Type:** Feature  
**Depends on:** FE-007, FE-019  
**Area:** `frontend/public/manifest.json`, `next.config` PWA plugin

## Goal

Installable PWA for guest experience: manifest, icons, service worker caching for photo proxies (CacheFirst, 200 entries, 7 days), API NetworkFirst, static StaleWhileRevalidate. Disable SW in development.

## References

- `docs/component_frontend.md` §8
- Prefer `@serwist/next` or `next-pwa` as documented

## Create / edit

- `public/manifest.json`, icons 192/512 + maskable
- PWA config in Next config
- Optional A2HS: do not nag aggressively; after gallery interaction is enough

## Requirements

- `display: standalone`, dark `theme_color` / `background_color`
- Do not implement full offline gallery editing

## Acceptance

- [ ] Production build generates a service worker
- [ ] Manifest is valid
- [ ] Dev mode does not register SW (or is disabled per spec)
