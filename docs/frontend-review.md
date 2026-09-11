# SpotMe frontend review

How to read each item:

- **Problem** — what is wrong today, and why it hurts the product.
- **Fix** — the change I would make.
- **Files** — where it lives (approximate if the issue is scattered).

Severity:

- **P0** — broken, misleading, or will fail against the real backend.
- **P1** — visible unprofessional / off-brand; should land in the next polish pass.
- **P2** — interaction, aesthetics, and “feels expensive” work.

---

## 1. Executive summary

The app has a real skeleton: auth, events, folders, upload UI, share links, analytics, guest OTP + selfie, couple gallery + favorites. The **SpotMe** cream / ink / signal-orange language on marketing and auth is already more distinctive than a generic Shadcn dashboard.

It does not yet feel like a premium photo product.

Three gaps dominate:

1. **Two visual systems fighting each other.** Marketing/auth is warm editorial (cream, 20px pills, Sofia Sans, orange accent). Dashboard is default Shadcn on the same tokens (ink-black borders, leftover spinner pages). Galleries mix `bg-black` + `zinc-*` hex with a cream `EmptyState` card. Docs asked for Inter + Plus Jakarta, light dashboard, `#0a0a0a` galleries. None of that is applied consistently.
2. **The product is photos, but photos are not the UI.** The landing has no photography. Event cards use one stock Unsplash wedding for every cover. Gallery demo wraps a dark grid in a cream marketing chrome with “Create Account”. Analytics “top photos” hardcode Picsum. Against a live backend, photo objects are never mapped from snake_case, so grids can render empty even when the API succeeded.
3. **Guest/couple — the screens that make or break Indian weddings — still look like a prototype.** Technical 404 copy (`Event with slug '…' not found`), “Try 123456”, no resend OTP, no pinch-zoom, no swipe-down close, and a processing animation that bounces. After `a1e60e4`, SpotMe’s logo is now **more** present on guest/couple chrome, which fights photographer-brand-first.

Fix order at the end of this doc. Do design-system + mapping first; otherwise later visual work will keep breaking on real data.

---

## 0. Pull `a1e60e4` vs this review

Only **two items are fully closed**. Several integration bugs are **half-fixed** (list wrappers unwrapped, field names still snake_case). One change is a **branding regression**.

### Fully eliminated

| Review item | Why it is closed |
|---|---|
| §7 **[P1] Filters button does nothing** | Events list now has a working **Filter & Sort** dropdown (status + sort). Still client-side only, not URL/backend — that leftover is a new smaller P2 under the same heading. |
| §15 **[P1] Logout is absolutely positioned and fights the header** | Logout is a `GalleryHeader` `rightActions` slot. Share on the **couple** page copies the URL and toasts. |

### Partially addressed (do not close)

| Review item | What landed | What is still wrong |
|---|---|---|
| §7 **[P1] Native `<select>` / `<input>`** | Native sort `<select>` is gone (moved into the dropdown). | Search is still a raw `<input>`, not `@/components/ui/input`. |
| §14 **[P0] Selfie match + guest photos unmapped** | Guest selfie now sends `sessionToken` (401 on selfie is fixed). | Response still typed as `matchCount` / `matchedPhotoIds`; API is `matched_photo_count`. Photos still unmapped snake_case. |
| §15 **[P0] Response shapes vs UI** | `useMasterPhotos` → `res.items`; `useMasterFolders` → `res.folders`; `useFavorites` → `res.items`. Empty-gallery crash from wrapping is fixed. | Photos/folders not run through `mapPhotoFromApi` / `mapFolderNodeFromApi`. Favorite toggle still `{ photoId }` vs `{ photo_id }`. |
| §18 **[P0] CamelCase vs snake_case table** | Rows “Master photos `Photo[]`” and “Master folders `FolderNode[]`” are fixed. | All other rows in that table still apply (`proxyUrl`, move, favorite, selfie count, top photos, analytics sort, guest phone). |
| §18 **[P1] Guest/couple public info not mapped** | `useEventInfo` now `mapEventFromApi`s the event, so `guestLinkActive` is real instead of `undefined` → false. | Still reuses the full dashboard `Event` type; no dedicated public mapper; photographer blob unmapped. |
| §14 **[P1] Personalized gallery header is thin** | Guest gallery now shows logos next to “Hi {name}”. | Still a one-off header (not `GalleryHeader`). Downloads still hover-only on mobile. SpotMe mark is now first, studio second. |

### Not eliminated (touched files, different bug)

- Sidebar hover state moved into Zustand and layout padding follows expand-on-hover. **Does not** fix §6 mobile overlay sidebar.
- Upload dropzone accepts `initialFolderId` from the photos tab. **Does not** fix mock tus uploads.
- Folder tree selects the new folder after create. Not in the original list.
- Select content width matches the trigger. Not in the original list.

### Regression to watch

Putting **SpotMe** (`Logo` + dark `spotme-logo-dark.png`) in `GalleryHeader` and `PersonalizedGallery` is the opposite of §14 “platform recedes / photographer brand first” and of the done-bar line “no SpotMe header” on guest phones. `gallery-demo` still has no `onShare`, so Share stays hidden there (better than a dead icon).

---

## 2. Design system, brand, and primitives

### [P0] Three product names in production UI

**Problem:** The live product is **SpotMe** (`layout.tsx` title, logo). The PWA manifest is **PhotoShare**. Docs still say “AI Photo Sharing Platform”. Installed PWA, App Store-adjacent share sheets, and browser tabs will not match the logo guests just saw.

**Fix:** One name everywhere: SpotMe. `manifest.json` `name` / `short_name`, footer legal line (keep HPK as copyright owner: “© 2026 HPK AI Labs”), metadata, and any leftover PhotoShare copy.

**Files:** `frontend/public/manifest.json`, `frontend/src/app/layout.tsx`, `frontend/src/app/(marketing)/layout.tsx`, `frontend/src/app/(auth)/layout.tsx`, `frontend/src/components/shared/logo.tsx`

### [P0] Fonts and type scale do not match the photo-product spec

**Problem:** Docs and FE-002 specify Inter (body) + Plus Jakarta Sans (display), with `display-xl` / `heading` sizes. The app loads **Sofia Sans** only. `font-display` is referenced on profile and header but is **not defined** in Tailwind, so those classes are no-ops. Headings therefore have no display face; the product looks like a default sans SaaS, not a gallery brand.

**Fix:** `next/font` for Inter + Plus Jakarta Sans. Wire `font-sans` and `font-display` in `tailwind.config.ts`. Restore the display size tokens from `docs/component_frontend.md` §4.2. Use Plus Jakarta for landing H1, dashboard page titles, guest “Hi {name}”. Keep Inter for forms, tables, metadata.

**Files:** `frontend/src/app/layout.tsx`, `frontend/tailwind.config.ts`, `frontend/src/app/globals.css`, `frontend/src/app/dashboard/profile/page.tsx`, `frontend/src/components/dashboard/header.tsx`

### [P1] Token system is cream-editorial, then ignored, then violated

**Problem:** `:root` is Canvas Cream / Ink / Signal Orange with `--radius: 1.25rem` (20px). Feature screens then hardcode `bg-black`, `bg-zinc-900`, `text-zinc-400`, `border-zinc-700` instead of `.dark` tokens. `EmptyState` always paints `bg-lifted` cream + `border-ink/10`, so on a black gallery it becomes a white card with unreadable grey text (reproduced on couple 404).

**Fix:** Split tokens on purpose, matching the agreed mix:

- **Dashboard / marketing / auth (light):** keep cream canvas if you want SpotMe warmth, but change `--border` / `--input` from ink-black to a hairline warm gray (`~24 10% 82%`). Modern SaaS is quiet borders, not every field outlined in black. Keep `--radius` at `0.5rem`–`0.75rem` for inputs; reserve `rounded-button` / `rounded-pill` for CTAs only.
- **Gallery (`.dark`):** near-black `#0a0a0a`, no zinc hex in components. `EmptyState` must have a `variant="dark"` (transparent / zinc-950 card, light text) or inherit `bg-card text-card-foreground`.

Ban new `zinc-*` and raw `bg-black` in feature components.

**Files:** `frontend/src/app/globals.css`, `frontend/tailwind.config.ts`, `frontend/src/components/shared/empty-state.tsx`, all `frontend/src/app/event/**`, `frontend/src/components/guest/**`, `frontend/src/components/gallery/**`

### [P1] Inputs, buttons, and radius fight each other

**Problem:** `Input` uses `rounded-[var(--radius)]` → 20px, so fields look like pills. `Button` default is `rounded-[20px]`, but `size="sm"` and `size="lg"` reset to `rounded-md`. Login “Continue” is a stadium; dashboard “Create Event” is a stadium; folder filters are pills; event cards are `rounded-lg`. The UI has no one corner language.

**Fix:** Inputs and selects: `rounded-md` (8px). Primary CTAs: `rounded-full` or `rounded-button` only. Icon buttons: circle. Cards: 12px. Apply `active:scale-[0.98]` on buttons (spec micro-interaction). Destructive stays Signal Orange, not a second red.

**Files:** `frontend/src/components/ui/button.tsx`, `frontend/src/components/ui/input.tsx`, `frontend/src/components/ui/select.tsx`, `frontend/src/components/ui/textarea.tsx`

### [P1] Accent color is unused on the surfaces that need a CTA

**Problem:** Signal orange (`#CF4500`) appears on the landing word “Instantly.” and as destructive. Primary buttons are ink-black. On a cream marketing page that is fine; on guest dark OTP, the primary button becomes cream-on-black with no brand pulse. Docs asked for **one accent** for CTAs.

**Fix:** Dashboard primary = ink (serious B2B). Guest/couple primary CTA = cream or a single warm accent (signal, used sparingly: OTP submit, Capture Selfie, Download). Do not use signal for both “Instantly” and delete.

**Files:** `frontend/src/app/globals.css`, `frontend/src/components/guest/otp-form.tsx`, `frontend/src/components/guest/selfie-capture.tsx`, `frontend/src/app/(marketing)/page.tsx`

### [P2] Motion tokens exist but almost nothing uses them

**Problem:** `lib/motion.ts` is correct (200–300ms, not bouncy). Only the marketing `AnimatedSection` uses it (and at 0.5s, slower than the token). Guest processing uses a looping scale+rotate sparkle — explicitly against “never bouncy”. Photo grid hover is CSS `scale-105` over 500ms (too slow, too playful).

**Fix:** Use `fadeIn` / `slideUp` / `scaleIn` for dialogs, toasts, gallery reveal. Processing: quiet pulse on a studio logo, 1.5s opacity, no rotate. Image hover: 200ms opacity overlay, not zoom (editorial galleries rarely zoom the thumbnail; the viewer does the zoom).

**Files:** `frontend/src/lib/motion.ts`, `frontend/src/components/shared/animated-section.tsx`, `frontend/src/components/guest/processing-screen.tsx`, `frontend/src/components/gallery/gallery-grid.tsx`

### [P2] `/showcase` is an internal design kitchen in production

**Problem:** `/showcase` is a leftover FE-002 page (“SpotMe Design System”). No nav link, but it is crawlable. Empty-state “Create Event” on that page does nothing.

**Fix:** Gate with `process.env.NODE_ENV === 'development'` or delete. Do not ship it.

**Files:** `frontend/src/app/showcase/page.tsx`

### [P1] Toaster depends on `next-themes` with no ThemeProvider

**Problem:** `sonner.tsx` calls `useTheme()` but root layout never wraps `ThemeProvider`. Theme falls back to `"system"`. Guest dark pages can get light toasts (cream cards on a black gallery).

**Fix:** Add `ThemeProvider` with `attribute="class"` `defaultTheme="light"`. On gallery routes, set `class="dark"` on a wrapper (already done on couple gallery) and force toasts `theme="dark"` there.

**Files:** `frontend/src/app/layout.tsx`, `frontend/src/components/ui/sonner.tsx`, `frontend/src/app/event/[slug]/guest/page.tsx`, `frontend/src/app/event/[slug]/master/page.tsx`

---

## 3. Marketing landing — `/`

### [P1] A photo product with no photographs

**Problem:** Hero is type + two buttons on empty cream. Competitors (Pixieset, KwikPic) lead with a wedding grid or a phone mock of a guest gallery. Photographers will not feel “this is for my studio.”

**Fix:** Full-bleed editorial hero: 1–2 real Indian wedding stills (licensed or studio-owned), dark overlay, headline over the image, then the three steps. Optional looping 6-image masonry under the fold. Secondary CTA should be “See a sample gallery” → `/gallery-demo` (once that page is fixed).

**Files:** `frontend/src/app/(marketing)/page.tsx`, `frontend/src/app/(marketing)/layout.tsx`

### [P1] Header CTA order and redundancy

**Problem:** Header is **Create Account** (black pill) then **Log In** (ghost). Hero repeats both. Photographers who already have an account hunt for Log In. Standard SaaS: ghost Log In, solid Get started on the right.

**Fix:** Swap header order. Hero: one primary “Get started — it’s free”, one text “Log in”. Keep footer links.

**Files:** `frontend/src/app/(marketing)/layout.tsx`, `frontend/src/app/(marketing)/page.tsx`

### [P1] Mobile hero clipping / wrapping

**Problem:** H1 is `text-5xl` with a hard `<br />`. On ~390px the second line “Instantly.” and body copy can overflow or feel cramped. Header “Create Account” fights the logo for width; Log In disappears from the header on small screens (only Create Account remains).

**Fix:** Drop the forced `<br />`; let the headline wrap. `text-4xl sm:text-5xl md:text-7xl`. Header: icon-only logo + “Log in” text + compact “Get started”. Sticky blur header on scroll.

**Files:** `frontend/src/app/(marketing)/page.tsx`, `frontend/src/app/(marketing)/layout.tsx`

### [P2] How-it-works and feature cards are generic SaaS

**Problem:** Three icon-in-a-rounded-square columns. No screenshots of upload, selfie, or guest grid. Copy is good (“Upload once. AI does the rest.”) but the layout is interchangeable with any AI startup.

**Fix:** Replace icons with cropped product frames (upload progress, selfie oval, dark masonry). Number the steps in a horizontal timeline on desktop. Keep generous whitespace.

**Files:** `frontend/src/app/(marketing)/page.tsx`

### [P2] Final CTA band is strong; rest of page has no social proof

**Problem:** Black band “Ready to elevate your studio?” works. No studio logos, no “used at 12 weddings this season”, no sample QR. Fine for beta, but the page currently ends abruptly after three feature cards.

**Fix:** After features, one testimonial or one “sample event” strip, then the black CTA. Not a logo wall of fake companies.

**Files:** `frontend/src/app/(marketing)/page.tsx`

---

## 4. Auth — `/login`, `/register`, `/forgot-password`, `/reset-password`

### [P1] Auth card is competent, not premium

**Problem:** Centered cream card, black Continue, Sofia Sans. Inputs are 20px-radius with a hard ink border — looks like a wireframe with a nice logo. No photo, no studio-side visual, no step indicator for OTP. Footer copyright uses `©️` in source (emoji-style).

**Fix:** Split layout on `md+`: left 45% editorial image (wedding, muted), right form on cream. Mobile: form only, logo centered. Stepper: “1 Account → 2 Verify phone”. Replace `©️` with `©`. Card shadow should be barely there (`shadow-sm` is ok); reduce border contrast.

**Files:** `frontend/src/app/(auth)/layout.tsx`, `frontend/src/app/(auth)/login/page.tsx`, `frontend/src/app/(auth)/register/page.tsx`

### [P1] Login CTA says “Continue”, spec says “Log In”; Remember me is missing

**Problem:** `docs/component_frontend.md` §5.1.2: Log In + Remember me. Live button is Continue. No remember-me (refresh token persistence is already in Zustand persist, so the checkbox can just mean “keep me signed in on this browser” vs session-only).

**Fix:** Label primary “Send OTP” on step 1, “Log in” on step 2. Add Remember me. After OTP, autofocus the OTP field, `inputMode="numeric"` `autoComplete="one-time-code"` `pattern="[0-9]*"`.

**Files:** `frontend/src/app/(auth)/login/page.tsx`, `frontend/src/stores/auth-store.ts`

### [P1] Register: password + confirm on one row

**Problem:** Two password fields in `grid-cols-2` on all breakpoints. On mobile (reproduced) they are squeezed; eye icons collide with text. Confirm errors wrap under a 160px field.

**Fix:** Stack passwords full-width always. Show a live checklist (8–16, upper, lower, digit, special) instead of dumping Zod on submit. Keep +91 prefix but match Input radius so the addon does not look like a bolted-on box (`rounded-l-md` vs 20px field).

**Files:** `frontend/src/app/(auth)/register/page.tsx`, `frontend/src/lib/auth-schemas.ts`

### [P1] No resend OTP, no countdown, test copy leaks

**Problem:** After login/register OTP there is only “Back to login”. No resend, no 5-minute expiry UI. Guest/couple toasts say **“Invalid OTP. Use 123456 for testing.”** That must never ship.

**Fix:** Resend with 30s cooldown calling `api.sendOtp`. Human errors only. Dev-only OTP hint behind `NODE_ENV === 'development'`.

**Files:** `frontend/src/app/(auth)/login/page.tsx`, `frontend/src/app/(auth)/register/page.tsx`, `frontend/src/app/event/[slug]/guest/page.tsx`, `frontend/src/app/event/[slug]/master/page.tsx`

### [P2] Password eye buttons have no accessible name

**Problem:** Toggle buttons have no `aria-label`. Focus ring is `focus:outline-none` without a replacement.

**Fix:** `aria-label="Show password"` / `Hide password`. `focus-visible:ring-2`.

**Files:** login, register, reset-password pages

### [P2] Forgot / reset are functional but disconnected

**Problem:** Forgot success goes to a separate `/reset-password` that asks for email/phone **again**. Easy to land on reset without context. OTP field placeholder is `123456`.

**Fix:** One flow: forgot → same page step 2 (OTP + new password) with email/phone carried in state or query. Mask the identifier. Placeholder “••••••”, not a real-looking OTP.

**Files:** `frontend/src/app/(auth)/forgot-password/page.tsx`, `frontend/src/app/(auth)/reset-password/page.tsx`

---

## 5. 404

### [P0] Root 404 is the Next.js default

**Problem:** Visiting an unknown path shows `404 | This page could not be found.` — no logo, no Return Home. The branded page lives only at `frontend/src/app/(marketing)/not-found.tsx`, which does **not** apply outside that route group.

**Fix:** Move it to `frontend/src/app/not-found.tsx`. Guest/couple 404s should use the **dark** branded empty state, not the cream marketing 404.

**Files:** add `frontend/src/app/not-found.tsx`; keep or delete the marketing-only file; `frontend/src/app/event/[slug]/guest/page.tsx`, `master/page.tsx`

---

## 6. Photographer dashboard shell

### [P0] Mobile dashboard: sidebar is a permanent overlay

**Problem:** `Sidebar` is `fixed left-0` at `w-16` or `w-64` on all breakpoints. Layout only adds `md:pl-64`. On a phone the sidebar covers the first 64–256px of content. The header hamburger toggles collapse; it does not open a Sheet. There is no studio name in the sidebar — only chevrons. Spec: collapsible on tablet, overlay drawer on mobile.

**Fix:** `< md`: hide sidebar; hamburger opens a `Sheet` from the left with Events, Profile, storage, log out. `md+`: current rail. Put **logo + studio name** in the expanded header of the sidebar (spec).

**Files:** `frontend/src/components/dashboard/sidebar.tsx`, `frontend/src/app/dashboard/layout.tsx`, `frontend/src/components/dashboard/header.tsx`, `frontend/src/components/ui/sheet.tsx`

### [P0] Notification bell is fake

**Problem:** Bell always shows a red `3`. It does not open a panel. Processing-complete alerts from the spec are missing. Photographers will click it on day one and lose trust.

**Fix:** Hide the badge until a real notification API exists, or wire BE-017. Empty dropdown: “No notifications yet.” Never hardcode a count.

**Files:** `frontend/src/components/dashboard/header.tsx`

### [P1] Avatar control is cramped and Settings is a dead import

**Problem:** User menu is `h-10 w-10` with a ChevronDown absolutely positioned on the same circle (`right-2`). Initials work; logo `fill` on a 40px circle will crop poorly. Header imports `Settings` and never uses it. Docs mention a Settings nav item; it does not exist (profile absorbs it). Duplicate Log out (sidebar + menu).

**Fix:** Avatar + name + chevron in a single `rounded-full` / `rounded-lg` trigger (`h-10 px-2 gap-2`), not icon-only. Remove unused Settings import. One logout path is enough in the menu; keep sidebar logout for desktop power users.

**Files:** `frontend/src/components/dashboard/header.tsx`, `frontend/src/components/dashboard/sidebar.tsx`

### [P1] Dashboard chrome is not “spacious SaaS”

**Problem:** `--border` is ink, so header hairline, sidebar, and cards all feel heavy. Content padding is fine (`p-4 md:p-6 lg:p-8`) but the event detail page adds a **second** header (back + title + tabs) under the global header — lots of stacked bars, little photo.

**Fix:** Lighter borders. Event detail: merge title into the dashboard header (breadcrumbs: Events / {name}) and use Shadcn `Tabs` underline in the content, not a custom tab row plus page header plus app header.

**Files:** `frontend/src/app/dashboard/layout.tsx`, `frontend/src/app/dashboard/events/[id]/page.tsx`, `frontend/src/app/globals.css`

### [P2] Auth gate is a spinner

**Problem:** Unauthenticated `/dashboard/*` shows a centered `Loader2` then redirects to login. Spec: skeletons, not spinners, for pages.

**Fix:** If no token after hydrate, `router.replace('/login')` with no spinner flash (or a cream branded splash <150ms). Never a generic spinner on cream.

**Files:** `frontend/src/app/dashboard/layout.tsx`

---

## 7. Events list — `/dashboard/events`

### [P1] List is a file manager, not a studio home

**Problem:** Horizontal rows, 80px thumb, metadata in one truncated line. Every event with `coverPhotoId` shows **the same** Unsplash wedding (`photo-1511285560929`). Backend already has `cover_image_url` on `EventSummary`; the mapper ignores it. `photographer` is read from the store and unused. No “welcome, {studio}”.

**Fix:** Card grid on `lg` (2–3 cols): large cover (`aspect-[3/2]`), name, date, status pill, photo count. List view optional. Use `cover_image_url` from API; fallback to a tasteful gradient + first letter, never a hardcoded stock photo. Greeting line using studio name.

**Files:** `frontend/src/components/dashboard/event-card.tsx`, `frontend/src/app/dashboard/events/page.tsx`, `frontend/src/lib/map-api.ts`, `backend/app/schemas/event.py` (already has `cover_image_url`)

### [P1] Filters button does nothing — RESOLVED in `a1e60e4`

**Was:** Outline “Filters” had no menu.

**Now:** “Filter & Sort” dropdown filters by status and sorts locally. The dead-button problem is gone.

**Leftover [P2]:** Filter/sort/search still live only in React state (not `?status=&q=&sort=`). Backend `GET /events` already supports `status`, `sort_by`, `sort_order` — unused. Empty copy can still say “adjust your search or filters” when a status filter is the reason the list is empty.

**Files:** `frontend/src/app/dashboard/events/page.tsx`, `frontend/src/hooks/use-events.ts`, `frontend/src/lib/api-client.ts`

### [P1] Native `<select>` and `<input>` bypass the design system — PARTIAL in `a1e60e4`

**Was:** Search is a raw `<input>`, sort is a raw `<select>`.

**Now:** Sort moved into the Filter & Sort dropdown (Shadcn). Search is still a raw `<input>` with custom classes, not `@/components/ui/input`.

**Fix:** Swap the search field to `Input`.

**Files:** `frontend/src/app/dashboard/events/page.tsx`

### [P2] Create dialog always says “Create Event”

**Problem:** `EventForm` submit label is hardcoded `Create Event` / `Creating...`. The same form is used for **Event Settings** edit. Dates are native `type="date"` with a Calendar icon that does not open a picker.

**Fix:** `submitLabel` prop. Consider a proper date range later; for now hide the decorative Calendar icon or make it click the input.

**Files:** `frontend/src/components/dashboard/event-form.tsx`, `frontend/src/app/dashboard/events/[id]/page.tsx`

### [P2] Create errors are a generic toast

**Problem:** `Failed to create event. Please try again.` swallows API `detail` (validation, duplicate slug, etc.).

**Fix:** Show `ApiError.message`. Map field errors onto the form.

**Files:** `frontend/src/app/dashboard/events/page.tsx`

---

## 8. Event detail — `/dashboard/events/[id]`

Tabs: Photos, Upload, Analytics, Share.

### [P0] Photo grid height / virtualizer likely clips or does not scroll

**Problem:** Page is `flex flex-col h-full overflow-hidden` inside a padded `<main>` that is **not** a full-height flex child. `h-full` often resolves to content height; the virtualized grid then cannot compute a viewport. Result: empty-looking photos tab or inner scroll fighting the page.

**Fix:** Dashboard layout: `min-h-screen flex flex-col`, main `flex-1 min-h-0`. Event detail `flex-1 min-h-0`. Photo grid `h-full min-h-0`.

**Files:** `frontend/src/app/dashboard/layout.tsx`, `frontend/src/app/dashboard/events/[id]/page.tsx`, `frontend/src/components/dashboard/photo-grid.tsx`

### [P0] Photos from the API are the wrong shape

**Problem:** Backend `PhotoResponse` is snake_case (`proxy_url`, `folder_id`, `event_id`, `file_size_bytes`, `face_count`, `uploaded_at`). Frontend `Photo` and the grid read `proxyUrl`, `folderId`, etc. Events are mapped in `map-api.ts`; **photos are not**. Grids, viewer, download, and favorites will look empty or break against localhost:8000.

**Fix:** `mapPhotoFromApi()` used in `useEventPhotos`, guest photos, master photos, favorites, top photos. Same for list wrappers (`items` vs raw array).

**Files:** `frontend/src/lib/map-api.ts`, `frontend/src/hooks/use-event-photos.ts`, `frontend/src/hooks/use-guest-gallery.ts`, `frontend/src/hooks/use-master-gallery.ts`, `frontend/src/hooks/use-couple-favorites.ts`, `frontend/src/types/event.ts`

### [P0] Move photos sends camelCase; backend expects snake_case

**Problem:** UI posts `{ photoIds, targetFolderId }`. Backend `MovePhotosRequest` is `{ photo_ids, folder_id }`. Move will 422. Delete-by-confirm uses `window.confirm`.

**Fix:** Map in the hook. Replace `confirm()` with an AlertDialog (same for archive/delete event, delete folder).

**Files:** `frontend/src/hooks/use-event-photos.ts`, `frontend/src/components/dashboard/photo-grid.tsx`, `frontend/src/app/dashboard/events/[id]/page.tsx`, `frontend/src/components/dashboard/folder-tree.tsx`

### [P1] Photos tab is a square thumbnail dump

**Problem:** Spec: dashboard can be denser than guest masonry, but still not a file browser. Grid is `aspect-square`, 2–6 cols, face badge is the **👤 emoji**. Hover zoom. Selection checkbox appears on hover only (invisible on touch).

**Fix:** Keep square for management, but add filename on hover, processing state, and a persistent checkbox on touch (`md:opacity-0 md:group-hover:opacity-100`). Replace emoji with `Users` icon. Empty state already has Upload Photos — good; match it to the cream/empty primitive consistently.

**Files:** `frontend/src/components/dashboard/photo-grid.tsx`

### [P1] Folder tree: hover-only actions, Tailwind `ml-${level}` is invalid

**Problem:** `level > 0 && \`ml-${level * 4}\`` does not generate Tailwind classes (dynamic string). Indent relies on inline `paddingLeft` only. Folder overflow (`…`) menu is `opacity-0 group-hover` — invisible on mobile. Delete uses `confirm()`.

**Fix:** Always show the overflow button on touch. Drop the dynamic class. Confirm via dialog. “All Photos” should show total count.

**Files:** `frontend/src/components/dashboard/folder-tree.tsx`

### [P1] Photo inspector is “Metadata Inspector” with S3 keys

**Problem:** Sheet title is the filename; description is “Metadata Inspector”. Photographers do not need `originalS3Key` in the UI. Download is “Download Proxy”, not original. No next/prev between photos.

**Fix:** Rename to the photo name only. Hide storage key. Primary: “Download original” via presigned URL. Secondary: delete. Add prev/next. Don’t show internal IDs by default (copyable in an advanced disclosure).

**Files:** `frontend/src/components/dashboard/photo-detail-viewer.tsx`

### [P1] Tabs are a custom underline, not keyboardable Tabs

**Problem:** Plain `<button>`s, no `role="tablist"`, no arrow keys. Deep-link via `?tab=` is good.

**Fix:** Use `@/components/ui/tabs` (already installed) wired to search params.

**Files:** `frontend/src/app/dashboard/events/[id]/page.tsx`, `frontend/src/components/ui/tabs.tsx`

### [P2] `eventType as any`

**Problem:** Forbidden `any` when passing into `EventForm`.

**Fix:** Narrow with the `EventType` union.

**Files:** `frontend/src/app/dashboard/events/[id]/page.tsx`

---

## 9. Upload tab

### [P0] Uploads are simulated; they never hit tusd

**Problem:** `UploadManager.startMockUpload` fakes progress with timers. `tus-client.ts` exists but is unused. Backend upload API is tusd **hooks** (`POST /api/v1/upload/hook`), not `POST /api/v1/upload/create` that `api-client.ts` still declares. A photographer can “upload 200 files” and nothing lands in S3.

**Fix:** Point tus to the real tusd endpoint (`NEXT_PUBLIC_TUS_ENDPOINT`). Send `event_id` / `folder_id` in tus metadata as the backend hook expects. Keep the existing progress UI. Remove mock timers from production builds.

**Files:** `frontend/src/lib/upload/upload-manager.ts`, `frontend/src/lib/upload/tus-client.ts`, `frontend/src/lib/api-client.ts`, `frontend/.env.example`, `backend/app/api/v1/upload.py`

### [P1] Dropzone is clear but not “trustworthy at 15k files”

**Problem:** Spec: per-file progress, overall %, speed, retry. The progress panel is actually close — speed/ETA exist. Gaps: no file-type icons/thumbnails, no “leave this tab open” warning, `@ts-ignore` on `file.path`, browse buttons are `<label>` wrapping `<Button asChild>` (awkward hit target). Folder select is a long flattened list.

**Fix:** Thumbnail from `URL.createObjectURL` for images. Sticky overall bar. If the user navigates away mid-upload, a banner on other tabs. Replace ts-ignore with a typed `webkitRelativePath`.

**Files:** `frontend/src/components/dashboard/upload-dropzone.tsx`, `frontend/src/components/dashboard/upload-progress.tsx`

### [P2] Upload progress heading underline is off-brand

**Problem:** `border-b-2 border-primary pb-1 inline-block` on “Upload Progress” looks like a leftover sketch.

**Fix:** Same section title style as Share / Analytics cards.

**Files:** `frontend/src/components/dashboard/upload-progress.tsx`

---

## 10. Analytics tab

### [P0] Top photos ignore real proxy URLs; types don’t match the API

**Problem:** UI type is `{ photoId, views, downloads }`. Backend is `{ id, filename, proxy_url, views, downloads }`. Render uses `https://picsum.photos/seed/${photo.photoId}/400/400`. Stats hover is `opacity-0 group-hover` — invisible on mobile. Empty top-photos still shows a heading with a blank grid.

**Fix:** Map `id` → `photoId`, use `proxy_url`. Always show view/download counts (not hover-only). Empty: “No views yet — share the guest link.” Skeleton cards, not “Loading analytics…” text.

**Files:** `frontend/src/components/dashboard/analytics-overview.tsx`, `frontend/src/types/analytics.ts`, `frontend/src/hooks/use-analytics.ts`

### [P1] Guest leads: query param names and export

**Problem:** Frontend sends `sortBy` / `sortOrder`. Backend expects `sort_by` / `sort_order`. Sort may silently use defaults. Export rebuilds CSV on the client (limit 1000) instead of `GET .../guests/export` which already returns CSV. Phone numbers shown in full in the table (good for the photographer; still worth a copy button). Loading is a table cell string.

**Fix:** Snake_case query params. `window.open` the export endpoint with the bearer token or blob from `api.exportAnalyticsGuests`. Row hover already from Table — add visible sort direction (arrow up vs down, not the same `ArrowUpDown` on every column). Skeleton rows.

**Files:** `frontend/src/lib/api-client.ts`, `frontend/src/components/dashboard/lead-table.tsx`

### [P2] Summary cards omit engagement rate

**Problem:** API returns `engagement_rate`. UI shows three cards only.

**Fix:** Fourth card or a small label under Total Guests. Format as percent.

**Files:** `frontend/src/components/dashboard/analytics-overview.tsx`, `frontend/src/types/analytics.ts`

---

## 11. Share tab

### [P1] Checkboxes for “link on/off” are the wrong control

**Problem:** Guest/Master active state is a tiny `Checkbox` on the right. Photographers will miss it. Disabled links still show the URL but copy is disabled — easy to share a dead link from memory. No QR. Indian wedding desks live on QR codes taped to the welcome board.

**Fix:** Explicit Switch + status text (“Live” / “Off”). QR for each link (download PNG). “Preview” opens the guest/master URL. Copy stays enabled; if off, toast “Link is off — turn it on before sharing.”

**Files:** `frontend/src/components/dashboard/link-generator.tsx` (add a Switch UI primitive if missing)

### [P2] Download toggle copy is slightly wrong vs product

**Problem:** Helper says if disabled, guests “can only view or download web-optimized versions.” Product: browsing is always proxy; original download is the flag. Tighten copy. No success toast on toggle.

**Fix:** “Guests always browse fast previews. This allows full-resolution originals.” Toast on change.

**Files:** `frontend/src/components/dashboard/link-generator.tsx`

---

## 12. Profile — `/dashboard/profile`

### [P1] Loading is a text string; email is shown as editable but not sent

**Problem:** `Loading profile...` spinner-adjacent. Form includes Email; `useUpdateProfile` only PATCHes `studio_name` and `phone`. Saving looks like email changed. Hardcoded “Your current plan includes 100GB” ignores `storage_limit_bytes`. Remove logo sends `logo_url: null` via the same update endpoint — confirm backend accepts that (logo is a separate upload route).

**Fix:** Skeleton matching the two-column cards. Email `readOnly` with “Contact support to change”. Storage copy from `formatBytes(limit)`. Logo/watermark remove should call a dedicated delete or documented PATCH. Watermark sample is Picsum — use a local wedding still in `/public`.

**Files:** `frontend/src/app/dashboard/profile/page.tsx`, `frontend/src/hooks/use-profile.ts`, `frontend/src/components/dashboard/watermark-preview.tsx`

### [P2] Logo is a circle crop; studios have horizontal logos

**Problem:** 128px circle. Guest header uses a small square. A wide studio wordmark will be destroyed.

**Fix:** Landscape slot `h-16 w-40` object-contain on a cream tile, plus optional avatar crop. Match guest header.

**Files:** `frontend/src/app/dashboard/profile/page.tsx`, `frontend/src/components/gallery/gallery-header.tsx`

---

## 13. Gallery demo — `/gallery-demo`

### [P0] Marketing chrome on an editorial gallery

**Problem:** Page is under `(marketing)/`, so cream header (SpotMe + Create Account + Log In) and footer sit on a dark gallery. This is the opposite of “platform recedes.” Folder chips include awkward `Mehndi > Guests` paths. Photos are random Picsum, not a wedding. Share in the inner header does nothing.

**Fix:** Move to `frontend/src/app/gallery-demo/page.tsx` **outside** the marketing layout, or a nested layout with no marketing nav. Dark only. Optional tiny “Demo” badge. Use wedding-set images. Wire Share to `navigator.share` / copy link.

**Files:** `frontend/src/app/(marketing)/gallery-demo/page.tsx`, `frontend/src/app/(marketing)/layout.tsx`, `frontend/src/components/gallery/gallery-header.tsx`

---

## 14. Guest gallery — `/event/[slug]/guest`

This is the make-or-break surface (mobile-first).

### [P0] Errors dump backend internals

**Problem:** Live 404: **“Event with slug 'rahul-priya-2026' not found”** inside a card. Guests should never see “slug”. `EmptyState` on guest is patched with `bg-zinc-950`; couple 404 was a **white** card with grey text (contrast failure). “Try again” on a missing event is the wrong action.

**Fix:** Map 404 → “This gallery isn’t available. Check the link from your photographer.” Button: none, or “Contact the studio” if you have a phone. Dark empty variant. Don’t interpolate `error.message` for 4xx.

**Files:** `frontend/src/app/event/[slug]/guest/page.tsx`, `frontend/src/components/shared/empty-state.tsx`, `frontend/src/lib/api-client.ts`

### [P0] Phone validation will fail the real API

**Problem:** Guest OTP form accepts a loose US-style regex and placeholders. Couple placeholder is `+1 234 567 8900`. Backend `INDIAN_PHONE_PATTERN` is `^\+91\d{10}$`. Auth will 422 after a “successful” client validation.

**Fix:** Same +91 control as photographer register. Normalize to `+91XXXXXXXXXX` before POST. `inputMode="numeric"`.

**Files:** `frontend/src/components/guest/otp-form.tsx`, `frontend/src/app/event/[slug]/master/page.tsx`, `frontend/src/app/event/[slug]/guest/page.tsx`

### [P0] Selfie match + guest photos are unmapped — PARTIAL in `a1e60e4`

**Was:** Token not passed; match payload and photos unmapped.

**Now:** `useSubmitSelfie` takes `token` and the guest page passes `sessionToken`. Selfie 401 from a missing bearer should be gone.

**Still open:** `api.submitSelfie` is still typed `{ matchCount, matchedPhotoIds }`; backend is `{ matched_photo_count, matched_photo_ids, status }`. Guest photo rows are still snake_case. Handle `status` (no face) with a specific empty state.

**Files:** `frontend/src/hooks/use-guest-gallery.ts`, `frontend/src/lib/api-client.ts`, `frontend/src/lib/map-api.ts`, `frontend/src/app/event/[slug]/guest/page.tsx`

### [P1] Guest landing is not photographer-brand-first — WORSE on gallery chrome after `a1e60e4`

**Problem:** Hardcoded **“Find your photos from the wedding!”** — wrong for corporate/birthday. Card is `bg-zinc-900`. Logo fallback is a colored square with a letter using **light-theme primary** (black square). SpotMe itself should be absent or a 10px “Powered by SpotMe” in the footer.

**Pull change:** Auth/OTP landing is unchanged. Personalized gallery and couple header now lead with the **SpotMe** wordmark (including `spotme-logo-dark.png`). That is the opposite of photographer-brand-first.

**Fix:** `{event.eventType}` copy table. Full-bleed cover if `cover_image_url`. Studio logo large, event name, date, then OTP. Footer: studio name; SpotMe only as a quiet “Powered by” if legally required.

**Files:** `frontend/src/app/event/[slug]/guest/page.tsx`, `frontend/src/components/guest/personalized-gallery.tsx`, `frontend/src/components/gallery/gallery-header.tsx`, `frontend/src/components/shared/logo.tsx`

### [P1] OTP and selfie are close; processing is not

**Problem:** Selfie oval guide is good. Capture button is large. Processing uses bouncy Sparkles and “you can close this page” — good copy, wrong motion. No upload of a gallery photo as fallback if camera is denied (common on iOS in-app browsers).

**Fix:** Calm pulse. Secondary “Upload a photo instead” file input. Camera-denied state is already there — add the upload path.

**Files:** `frontend/src/components/guest/selfie-capture.tsx`, `frontend/src/components/guest/processing-screen.tsx`

### [P1] Personalized gallery header is thin — PARTIAL in `a1e60e4`

**Was:** No studio mark; guest invented a one-off header.

**Now:** SpotMe logo + optional studio logo + event name sit above “Hi {name}”.

**Still open:** Not the shared `GalleryHeader`. Downloads on the grid are still hover-only (invisible on phones). Prefer studio-first, SpotMe last.

**Files:** `frontend/src/components/guest/personalized-gallery.tsx`, `frontend/src/components/gallery/gallery-grid.tsx`, `frontend/src/components/gallery/photo-viewer.tsx`

### [P0] Guest download uses the photographer photo endpoint

**Problem:** `DownloadButton` always calls `api.downloadPhoto(eventId, photoId)` (`/api/v1/events/:id/photos/:id/download`) which requires photographer JWT. Guests need `/api/v1/event/:slug/photos/:id/download` (and couple has `/master/photos/:id/download`). Downloads from guest/couple galleries will 401.

**Fix:** `DownloadButton` takes `context: 'photographer' | 'guest' | 'couple'` + `slug`.

**Files:** `frontend/src/components/gallery/download-button.tsx`, `frontend/src/lib/api-client.ts`

---

## 15. Couple / master gallery — `/event/[slug]/master`

### [P0] Response shapes vs UI — PARTIAL in `a1e60e4`

**Was:** Couple gallery would look empty or crash because photos/folders/favorites were treated as arrays.

**Now:** Hooks unwrap `items` / `folders`. `api-client` types match `PaginatedResponse` / `{ folders }`. That crash is gone.

**Still open:**

- Photos still not `mapPhotoFromApi` (`proxy_url` vs `proxyUrl` → blank tiles).
- Folders unwrapped but not `mapFolderNodeFromApi` (chips that only read `id`/`name` may work; anything using `eventId` / `parentId` will not).
- Toggle body still `{ photoId }` vs `{ photo_id }`.

**Fix:** Map in hooks. `toggleFavorite({ photo_id })`. Folders via `mapFolderNodeFromApi`.

**Files:** `frontend/src/hooks/use-master-gallery.ts`, `frontend/src/hooks/use-couple-favorites.ts`, `frontend/src/lib/api-client.ts`, `frontend/src/lib/map-api.ts`

### [P1] Logout is absolutely positioned and fights the header — RESOLVED in `a1e60e4`

**Was:** Absolutely positioned Logout over Share; Share was a no-op.

**Now:** `GalleryHeader` accepts `rightActions` and `onShare`. Couple page copies `window.location.href` and toasts. Logout sits in the header flex row.

**Leftover [P2]:** Share is clipboard-only (no `navigator.share` on mobile). Gallery demo does not pass `onShare`, so the icon is hidden there (acceptable). Visual style is still a dashboard ghost button, not a studio control.

**Files:** `frontend/src/app/event/[slug]/master/page.tsx`, `frontend/src/components/gallery/gallery-header.tsx`

### [P1] Favorites FAB

**Problem:** Fixed bottom-right, `hover:scale-105`, heart `text-primary` (cream on dark when filled — ok; when inactive+count the fill uses primary on a glass button and can look like a default Shadcn chip). Label “Favorites (0)” on a wedding gallery is English-dashboard, not couple.

**Fix:** “Shortlist” / “Priya’s picks” copy optional later; for now “Saved”. No scale bounce. Badge count on the heart. Respect safe-area (`bottom-6` + `env(safe-area-inset-bottom)`).

**Files:** `frontend/src/components/couple/favorites-fab.tsx`

### [P1] Folder pills flatten the tree with `Parent > Child`

**Problem:** Long unreadable chips, horizontal scroll without a fade hint. Fine for 3 folders; bad for 12.

**Fix:** Single-level chips for roots; drill-in or a compact select on mobile. Fade edges on the scroller (`no-scrollbar` is already there — add mask-image).

**Files:** `frontend/src/components/gallery/folder-nav.tsx`

### [P2] Couple OTP “Try 123456” in the label

**Problem:** `OTP Code (Try 123456)` is in the form label. John Doe / +1 placeholders.

**Fix:** Remove. Indian name/phone examples. Back + Verify already exist — good.

**Files:** `frontend/src/app/event/[slug]/master/page.tsx`

---

## 16. Shared gallery: grid and viewer

### [P1] Grid is masonry-ish but not exhibition-grade

**Problem:** Column virtualizer + 16px gap is a solid start. Issues: `rounded-md` on every image (editorial often uses **no** radius or 2px). Hover zoom. Download/heart hover-only. `useEffect` for columns does not list `layoutMode` in deps (stale columns if mode changed). Empty is `<p>No photos found.</p>` not `EmptyState`. Picsum + `unoptimized` left in dashboard grid comments.

**Fix:** Guest/couple: `rounded-none` or `rounded-sm`, 8–12px gutters, no zoom. Heart visible on touch (always-on 24px). Include `layoutMode` in the effect deps. Blurhash is wired — good; ensure API actually sends hashes or the shimmer is the fallback (it is).

**Files:** `frontend/src/components/gallery/gallery-grid.tsx`, `frontend/src/components/shared/responsive-image.tsx`

### [P0] Viewer is not “iOS Photos”

**Problem:** Spec: pinch-zoom, swipe with spring, swipe-down-to-close, backdrop blur. Implemented: fade overlay, horizontal drag with a crude velocity check, keyboard arrows, **no pinch**, **no swipe down**, arrows `hidden sm:flex` so phones have no chrome (drag only, easy to miss). `next/image` `fill` + `object-contain` inside a dragged motion div is jank-prone. No preloading of neighbors. Close does not restore focus.

**Fix:** Use a dedicated viewer (e.g. yet-another-react-lightbox, or a small custom one with `use-gesture`). Pinch + swipe-down close. Bottom filmstrip optional. Preload ±1. Trap focus. `aria-modal`. Keep 200ms fade.

**Files:** `frontend/src/components/gallery/photo-viewer.tsx`

### [P1] `next/image` will reject S3 / CloudFront hosts

**Problem:** `remotePatterns` allow only `picsum.photos` and `images.unsplash.com`. Real `proxy_url` hosts will error in the Image component. Dashboard even comments `unoptimized // for picsum mocks`.

**Fix:** Add the storage CDN / S3 pattern via env (`NEXT_PUBLIC_MEDIA_HOST`). Prefer `unoptimized` for signed URLs that change query strings.

**Files:** `frontend/next.config.mjs`, `frontend/src/components/shared/responsive-image.tsx`

---

## 17. PWA, performance, a11y

### [P1] PWA identity and theme color

**Problem:** Manifest name PhotoShare, `theme_color` `#0a0a0a` even for the cream dashboard. PWA disabled in development (`next-pwa` `disable: development`) — fine. Guest JS budget <150KB is unlikely with webcam + framer + virtualizer all on the guest page (selfie is not dynamically imported).

**Fix:** Manifest SpotMe; `theme_color` cream for photographer, dark for `/event/*` via the existing viewport export split per layout. `next/dynamic` the webcam and photo viewer on guest (viewer already dynamic on couple).

**Files:** `frontend/public/manifest.json`, `frontend/src/app/layout.tsx`, `frontend/src/app/event/[slug]/guest/page.tsx`, `frontend/next.config.mjs`

### [P1] Accessibility gaps vs FE-021

**Problem:** No skip link (main has `tabIndex={-1}` unused). OTP fields not announced as 6-digit. Dialogs: Radix handles focus — good. Viewer: no focus trap. Status badge processing uses color + text — ok. Contrast: muted grey on cream is borderline; grey-on-white EmptyState on couple error **fails**. `prefers-reduced-motion` only on `AnimatedSection` and viewer scale, not processing sparkles or gallery hover.

**Fix:** Skip link to `#main-content`. Dark empty variant. Reduced motion on processing and hover zoom. OTP `aria-describedby`.

**Files:** `frontend/src/app/layout.tsx`, `frontend/src/app/dashboard/layout.tsx`, `frontend/src/components/guest/processing-screen.tsx`, `frontend/src/components/shared/empty-state.tsx`

### [P2] MSW boot flash

**Problem:** When `NEXT_PUBLIC_MOCK_API=true`, `MSWProvider` returns `null` until the worker starts → blank white/cream frame. Live review against port 8000 showed real 404s, so mocks are likely off — good — but MSW handlers still use `/api/events` not `/api/v1/events`, so turning mocks on would still miss.

**Fix:** Align MSW paths with `/api/v1`. Show the branded splash instead of `null`.

**Files:** `frontend/src/components/providers/msw-provider.tsx`, `frontend/src/mocks/handlers.ts`

---

## 18. Frontend ↔ backend integration (UX of the contract)

Focus: what the UI must do so screens feel finished on the real API. Not a full OpenAPI audit.

### [P0] CamelCase UI vs snake_case API (the main integration bug)

| UI field / call | Backend | What the user sees |
|---|---|---|
| `Photo.proxyUrl` | `proxy_url` | Blank tiles |
| `Photo.folderId` | `folder_id` | Folder filter empty |
| Move `{ photoIds, targetFolderId }` | `{ photo_ids, folder_id }` | Move fails, toast |
| Favorite `{ photoId }` | `{ photo_id }` | Heart doesn’t persist |
| Selfie `matchCount` | `matched_photo_count` | “Found undefined photos” / no toast |
| Master photos `Photo[]` | `{ items, … }` | **Fixed in `a1e60e4`** (unwrap `items`; tiles still blank until `proxyUrl` is mapped) |
| Master folders `FolderNode[]` | `{ folders }` | **Fixed in `a1e60e4`** (unwrap `folders`) |
| Top photo `photoId` | `id` + `proxy_url` | Picsum placeholders |
| Analytics `sortBy` | `sort_by` | Sort ignored |
| Guest phone free text | `+91` + 10 digits | 422 after OTP send |

**Fix:** One mapping layer. Do not sprinkle `raw.proxy_url` in components.

**Files:** `frontend/src/lib/map-api.ts` (extend), all hooks under `frontend/src/hooks/`

### [P0] 401 refresh is a stub

**Problem:** `handle401` comments “placeholder” and throws. Access JWT is 15 minutes. Photographers mid-upload or mid-settings get kicked or stuck without a re-login UX. `refreshToken` exists on the auth store and is never called from the client.

**Fix:** On 401, try `api.refresh`, retry the request once, else `clearTokens` and send to `/login?next=`. Guest/couple tokens should not use photographer refresh.

**Files:** `frontend/src/lib/api-client.ts`, `frontend/src/stores/auth-store.ts`

### [P1] FastAPI `detail` can be a string or a list

**Problem:** Validation errors return `detail: [{ loc, msg }]`. `ApiError` uses `errorData.detail` as `message`. Toasts can show `[object Object]`.

**Fix:** Normalize to a string in `ApiClient`. Attach field errors for forms.

**Files:** `frontend/src/lib/api-client.ts`

### [P1] Guest/couple public info is not mapped — PARTIAL in `a1e60e4`

**Was:** `event.guestLinkActive` undefined → guests saw “Gallery Unavailable” on a live link.

**Now:** `useEventInfo` runs `mapEventFromApi` on `data.event`, so `guestLinkActive` / `downloadEnabled` / dates should populate.

**Still open:** Reuses the full dashboard `Event` type (fake zeros for `totalPhotos`, etc.). Photographer object is not mapped. Prefer a dedicated `PublicEventInfo` type. `mapEventFromApi` defaults missing flags with `?? true`, which can show a gallery as on if the field is absent.

**Files:** `frontend/src/hooks/use-master-gallery.ts`, `frontend/src/lib/map-api.ts`, `frontend/src/lib/api-client.ts`, `backend/app/schemas/event.py` (`EventPublicInfo`)

### [P1] Optimistic UI is rare except favorites

**Problem:** Favorites have a good optimistic toggle (then refetch). Link toggles wait on the server with a disabled checkbox and no optimistic flip. Profile logo does optimistic blob preview — good. Event create waits then navigates — good. Failed selfie returns to selfie — good.

**Fix:** Optimistic Switch for link toggles; rollback on error. That’s the highest-visibility remaining case.

**Files:** `frontend/src/components/dashboard/link-generator.tsx`, `frontend/src/hooks/use-events.ts`

### [P2] CORS / cookie / token storage

**Problem:** Tokens in `localStorage` + Zustand persist. Fine for Phase 1; XSS-sensitive. API base is absolute `localhost:8000` so CORS must allow the Next origin. No `credentials`. Don’t change this in a visual polish pass except to document it.

**Files:** `frontend/src/lib/api-client.ts`, backend CORS config

---

## 19. Copy and microcopy (cross-cutting)

| Location | Current | Suggested |
|---|---|---|
| Guest subtitle | “Find your photos from the wedding!” | Event-type aware |
| Guest/couple errors | slug in message | “This gallery isn’t available.” |
| OTP toasts | “Use 123456 for testing.” | Remove |
| Login button | Continue | Send OTP / Log in |
| Event form edit | Create Event | Save changes |
| Profile storage | “100GB” | Actual limit |
| Photo sheet | Metadata Inspector | (drop) |
| Share checkbox | (none) | Live / Off |
| Filters | **Working dropdown (`a1e60e4`)** | Keep; later sync to URL / API |
| 404 | Next default | SpotMe branded |
| PWA | PhotoShare | SpotMe |

Prefer a `frontend/src/lib/copy.ts` so wedding/corporate/birthday strings stay in one place.

---

## 20. What is already working (do not regress)

- SpotMe logo and cream/ink/signal direction on marketing/auth — distinctive; refine, don’t replace with generic blue SaaS.
- Login password visibility, OTP step, masked phone.
- Forgot-password anti-enumeration (always success).
- Event list skeleton, empty state with Create Event, search, Filter & Sort dropdown (`a1e60e4`).
- Couple header: logout in the header row; share copies the gallery URL (`a1e60e4`).
- Guest selfie request sends the session bearer (`a1e60e4`).
- Couple photos/folders/favorites unwrap paginated `{ items }` / `{ folders }` (`a1e60e4`).
- Share URLs derived from slug; tab state in the query string.
- Couple `LayoutGroup` + `layoutId` for viewer (keep when rewriting zoom).
- Blurhash + shimmer path in `ResponsiveImage`.
- Folder CRUD inline rename, upload dropzone copy (formats, 50MB).
- Upload progress ETA/speed UI (reuse when tus is real).
- Favorites optimistic update.
- `ErrorBoundary` on major pages.
- Indian `+91` on photographer register (extend to guest/couple).

---

## 21. Recommended implementation order

Do these as separate PRs; each should be visually complete.

1. **Contract layer (P0)** — `mapPhotoFromApi`, favorite `{ photo_id }`, selfie `matched_photo_count`, 401 refresh, FastAPI detail normalization. List wrappers are already unwrapped (`a1e60e4`); photos still need field mapping.
2. **Empty/error/dark variant (P0)** — `EmptyState` dark, branded root `not-found`, no slug in guest copy, couple/guest 404 contrast.
3. **Design tokens (P1)** — hairline borders on dashboard, input radius, fonts Inter + Plus Jakarta, ThemeProvider, kill zinc hex on galleries.
4. **Guest + couple chrome (P1)** — photographer-first landing, +91 OTP, resend, viewer gestures, visible mobile download, remove marketing layout from gallery demo.
5. **Dashboard shell (P0/P1)** — mobile Sheet, real/no fake notifications, event cards with real covers, event detail height. Filters exist; next step is URL/backend sync.
6. **Upload (P0)** — real tusd; then thumbnails and “don’t close this tab.”
7. **Landing (P1)** — photography in the hero, CTA order, sample gallery.
8. **Share QR + analytics real images (P1)**.
9. **Motion/a11y pass (P2)** — button press, reduced motion, skip link, PWA name.

---

## 22. Suggested “done” bar for “highly interactive, stylish, professional”

A photographer on a 13" laptop:

- Cream dashboard, quiet borders, Plus Jakarta titles, event **covers** not rows.
- Upload that survives refresh and shows MB/s.
- Share tab with a QR they can screenshot.

A guest on an iPhone SE:

- Studio logo, event name, +91 OTP, selfie oval, calm wait, dark masonry, swipeable viewer, download in the viewer, no SpotMe header.

A couple:

- Same darkness, folder chips, visible heart, shortlist FAB, no marketing “Create Account” anywhere near the photos.

Until those three sentences are true, extra animation will not make the product feel premium.
