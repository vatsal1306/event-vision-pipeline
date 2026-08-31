# Component Document: Frontend

> **Version:** 1.0  
> **Last Updated:** September 2026  
> **Scope:** Photographer Studio Dashboard, Guest PWA, Couple Interface  
> **Development Order:** This is Component 1 — built first with mock data, before backend and AI/ML.

---

## Table of Contents

1. [Overview & Technology Choices](#1-overview--technology-choices)
2. [Architecture](#2-architecture)
3. [Project Structure](#3-project-structure)
4. [Design System & UI Foundation](#4-design-system--ui-foundation)
5. [Photographer Studio Dashboard](#5-photographer-studio-dashboard)
6. [Couple Interface (Master Link)](#6-couple-interface-master-link)
7. [Guest Interface (Guest Link / PWA)](#7-guest-interface-guest-link--pwa)
8. [PWA Configuration](#8-pwa-configuration)
9. [State Management](#9-state-management)
10. [API Integration Layer](#10-api-integration-layer)
11. [Mock Data Strategy](#11-mock-data-strategy)
12. [Performance Optimization](#12-performance-optimization)
13. [Testing Strategy](#13-testing-strategy)
14. [Accessibility & Internationalization](#14-accessibility--internationalization)
15. [Build & Deployment](#15-build--deployment)

---

## 1. Overview & Technology Choices

### 1.1 Framework: Next.js 14+ (App Router)

**Why Next.js:**

- **PWA support:** Next.js PWA plugins (`next-pwa` or `@serwist/next`) provide service worker generation, offline caching, and manifest configuration out of the box — critical for the guest experience.
- **Server-Side Rendering (SSR) and Static Generation (SSG):** Event landing pages and gallery pages benefit from SSR for fast initial load, while the photographer dashboard can use client-side rendering for interactivity.
- **Image optimization:** `next/image` provides automatic WebP conversion, lazy loading, responsive srcsets, and blur placeholders — essential for a photo-heavy platform.
- **App Router:** React Server Components reduce client-side JavaScript bundle for gallery pages, improving mobile performance.
- **API Routes:** Next.js API routes serve as a lightweight Backend-for-Frontend (BFF) layer during development and can proxy to the Python backend in production.
- **TypeScript:** First-class TypeScript support for type safety across the entire frontend codebase.

### 1.2 UI Framework: Tailwind CSS + Shadcn/UI

**Why Tailwind CSS:**
- Utility-first approach enables rapid UI development with consistent spacing, colors, and typography.
- Purged CSS output is tiny (~10KB gzipped typically), critical for mobile performance.
- Dark mode support via `dark:` prefix — needed for the gallery viewer (dark background) vs. dashboard (light theme).

**Why Shadcn/UI:**
- Not a component library (no npm dependency) — components are copied into the project and fully customizable.
- Built on Radix UI primitives (accessible, composable).
- Includes all foundational components: Dialog, Dropdown, Tabs, Toast, Progress, Table, Form, etc.
- Theming via CSS variables — single source of truth for the design system.

### 1.3 Additional Libraries

| Library | Purpose | Justification |
|---|---|---|
| `react-dropzone` | File drag-and-drop | Battle-tested, handles folder uploads with `webkitdirectory`, exposes file tree structure |
| `tus-js-client` | Chunked resumable uploads | Implements the tus protocol; handles resume, retry, and parallel chunk uploads |
| `zustand` | Client-side state management | Lightweight (1KB), no boilerplate, works naturally with React hooks |
| `@tanstack/react-query` | Server state management & caching | Handles API calls, caching, background refetching, optimistic updates, pagination |
| `framer-motion` | Animations | Smooth gallery transitions, image viewer animations, page transitions |
| `react-virtual` or `@tanstack/react-virtual` | Virtualized lists/grids | Renders only visible photos in grids of 1,000+ items; prevents DOM bloat |
| `react-webcam` | Selfie capture | Cross-browser camera access with configurable constraints (front-facing, resolution) |
| `zod` | Schema validation | Validates forms (registration, event creation) and API responses with TypeScript inference |
| `next-pwa` or `@serwist/next` | PWA service worker | Automatic service worker generation, precaching, runtime caching strategies |
| `lucide-react` | Icons | Clean, consistent icon set; tree-shakeable |
| `date-fns` | Date formatting | Lightweight date utility (no Moment.js bloat) |
| `sonner` | Toast notifications | Minimal, accessible toast component |

### 1.4 Language & Tooling

- **Language:** TypeScript (strict mode enabled)
- **Package Manager:** pnpm (faster installs, disk-efficient via hard linking)
- **Linting:** ESLint with `@typescript-eslint`, `eslint-plugin-react`, `eslint-plugin-jsx-a11y`
- **Formatting:** Prettier (single quotes, 2-space indent, trailing commas)
- **Pre-commit:** Husky + lint-staged (runs ESLint + Prettier on staged files)

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Application                    │
│                                                           │
│  ┌──────────────────┐  ┌──────────────────┐              │
│  │  Photographer     │  │  Guest / Couple   │              │
│  │  Dashboard        │  │  PWA Interface    │              │
│  │  (CSR-heavy)      │  │  (SSR + CSR)      │              │
│  │                   │  │                   │              │
│  │  /dashboard/*     │  │  /event/{slug}/*  │              │
│  └────────┬──────────┘  └────────┬──────────┘              │
│           │                      │                         │
│  ┌────────┴──────────────────────┴──────────┐              │
│  │          Shared Layer                     │              │
│  │                                           │              │
│  │  • API Client (axios/fetch wrapper)       │              │
│  │  • Zustand Stores (auth, upload, UI)      │              │
│  │  • React Query (server state)             │              │
│  │  • Design System (Shadcn + Tailwind)      │              │
│  │  • Type Definitions (shared types)        │              │
│  └────────────────────┬──────────────────────┘              │
│                       │                                     │
│  ┌────────────────────┴──────────────────────┐              │
│  │        Next.js API Routes (BFF Layer)      │              │
│  │        /api/* → Proxy to Python Backend    │              │
│  └────────────────────┬──────────────────────┘              │
│                       │                                     │
└───────────────────────┼─────────────────────────────────────┘
                        │
                        ▼
              ┌───────────────────┐
              │  Python Backend    │
              │  (FastAPI)         │
              │  REST API          │
              └───────────────────┘
```

### 2.2 Route Architecture

The application serves three distinct user interfaces through a single Next.js app, differentiated by route prefix:

```
/                           → Marketing landing page (static)
/login                      → Photographer login
/register                   → Photographer registration
/dashboard/                 → Photographer Studio Dashboard (protected)
/dashboard/events           → Event list
/dashboard/events/[id]      → Event detail
/dashboard/events/[id]/upload → Upload interface
/dashboard/events/[id]/analytics → Analytics
/dashboard/profile          → Profile & settings

/event/[slug]/master        → Couple's gallery (OTP-protected)
/event/[slug]/guest         → Guest auth + selfie + gallery (OTP-protected)
```

### 2.3 Rendering Strategy

| Route Group | Strategy | Reason |
|---|---|---|
| `/` (landing) | Static (SSG) | Marketing page; no dynamic data; maximum performance |
| `/dashboard/*` | Client-Side Rendering (CSR) | Highly interactive; requires auth; frequent state changes |
| `/event/[slug]/master` | SSR → Client hydration | Initial load shows event metadata (SSR for speed); gallery interaction is client-side |
| `/event/[slug]/guest` | SSR → Client hydration | Landing page is SSR for fast first paint; selfie/gallery is client-side |

---

## 3. Project Structure

```
frontend/
├── src/
│   ├── app/                              # Next.js App Router
│   ├── (marketing)/                  # Route group: public marketing pages
│   │   ├── page.tsx                  # Landing page
│   │   └── layout.tsx
│   │
│   ├── (auth)/                       # Route group: authentication
│   │   ├── login/page.tsx
│   │   ├── register/page.tsx
│   │   └── layout.tsx
│   │
│   ├── dashboard/                    # Photographer dashboard (protected)
│   │   ├── layout.tsx                # Dashboard shell (sidebar, header)
│   │   ├── page.tsx                  # Dashboard home (redirect to /events)
│   │   ├── events/
│   │   │   ├── page.tsx              # Event list
│   │   │   └── [id]/
│   │   │       ├── page.tsx          # Event detail
│   │   │       ├── upload/page.tsx   # Upload interface
│   │   │       └── analytics/page.tsx
│   │   └── profile/page.tsx          # Profile & settings
│   │
│   ├── event/                        # Guest/Couple-facing pages
│   │   └── [slug]/
│   │       ├── master/page.tsx       # Couple gallery
│   │       └── guest/page.tsx        # Guest auth + gallery
│   │
│   ├── api/                          # BFF API routes
│   │   ├── auth/[...nextauth]/       # Auth routes (if using NextAuth)
│   │   └── proxy/[...path]/          # Proxy to Python backend
│   │
│   ├── layout.tsx                    # Root layout
│   ├── not-found.tsx                 # 404 page
│   └── globals.css                   # Tailwind base + CSS variables
│
├── components/
│   ├── ui/                           # Shadcn/UI base components
│   │   ├── button.tsx
│   │   ├── dialog.tsx
│   │   ├── input.tsx
│   │   ├── progress.tsx
│   │   ├── toast.tsx
│   │   └── ...
│   │
│   ├── dashboard/                    # Photographer dashboard components
│   │   ├── sidebar.tsx
│   │   ├── header.tsx
│   │   ├── event-card.tsx
│   │   ├── event-form.tsx
│   │   ├── folder-tree.tsx
│   │   ├── upload-dropzone.tsx
│   │   ├── upload-progress.tsx
│   │   ├── photo-grid.tsx
│   │   ├── analytics-overview.tsx
│   │   ├── lead-table.tsx
│   │   ├── watermark-preview.tsx
│   │   └── link-generator.tsx
│   │
│   ├── gallery/                      # Shared gallery components (couple + guest)
│   │   ├── gallery-grid.tsx          # Masonry grid with virtualization
│   │   ├── photo-viewer.tsx          # Full-screen viewer with swipe/zoom
│   │   ├── folder-nav.tsx            # Folder-based navigation
│   │   ├── gallery-header.tsx        # Event branding header
│   │   └── download-button.tsx
│   │
│   ├── guest/                        # Guest-specific components
│   │   ├── otp-form.tsx
│   │   ├── selfie-capture.tsx
│   │   ├── face-guide-overlay.tsx
│   │   ├── processing-screen.tsx
│   │   └── personalized-gallery.tsx
│   │
│   ├── couple/                       # Couple-specific components
│   │   ├── favorites-button.tsx
│   │   └── favorites-gallery.tsx
│   │
│   └── shared/                       # Cross-cutting components
│       ├── logo.tsx
│       ├── loading-spinner.tsx
│       ├── error-boundary.tsx
│       ├── empty-state.tsx
│       └── responsive-image.tsx
│
├── lib/                              # Utilities and shared logic
│   ├── api-client.ts                 # Axios/fetch wrapper with interceptors
│   ├── auth.ts                       # Auth helpers (token management, session)
│   ├── constants.ts                  # App-wide constants
│   ├── utils.ts                      # Generic utilities
│   └── upload/
│       ├── tus-client.ts             # Tus upload client configuration
│       ├── upload-manager.ts         # Manages file queue, parallel uploads
│       └── file-utils.ts             # File type detection, size formatting
│
├── stores/                           # Zustand stores
│   ├── auth-store.ts                 # Photographer auth state
│   ├── upload-store.ts               # Upload queue, progress, status
│   ├── gallery-store.ts              # Gallery view state (filters, sort)
│   └── ui-store.ts                   # UI state (sidebar, modals, theme)
│
├── hooks/                            # Custom React hooks
│   ├── use-auth.ts                   # Auth hook (wraps auth store)
│   ├── use-upload.ts                 # Upload hook (wraps upload store + tus)
│   ├── use-camera.ts                 # Camera access hook
│   ├── use-intersection.ts           # Intersection observer for lazy loading
│   └── use-debounce.ts
│
├── types/                            # TypeScript type definitions
│   ├── api.ts                        # API request/response types
│   ├── event.ts                      # Event, Folder, Photo types
│   ├── user.ts                       # User, Guest, Couple types
│   └── upload.ts                     # Upload-related types
│
├── mocks/                            # Mock data for frontend-first development
│   ├── events.ts                     # Mock event data
│   ├── photos.ts                     # Mock photo URLs and metadata
│   ├── users.ts                      # Mock photographer/guest data
│   ├── analytics.ts                  # Mock analytics data
│   └── handlers.ts                   # MSW (Mock Service Worker) request handlers
│
└── public/
    ├── manifest.json                 # PWA manifest
    ├── sw.js                         # Service worker (auto-generated)
    ├── icons/                        # PWA icons (192x192, 512x512)
    ├── images/
    │   └── placeholder-photos/       # Placeholder images for mock galleries
    └── fonts/                        # Self-hosted fonts (Inter, etc.)
```

---

## 4. Design System & UI Foundation

### 4.0 Design Philosophy & Quality Bar

Visual quality is **non-negotiable** on a photo platform. Every pixel of the UI exists to make photographs look stunning and the experience feel premium.

**Gallery UI (Guest & Couple Pages):**
- **Dark backgrounds** (`#0a0a0a` / near-black) so photos pop with maximum vibrancy. Never use white or light gray backgrounds in gallery views.
- **Masonry grid** with consistent, generous gutter spacing. The gallery must feel like a curated photo exhibition, not a file browser or thumbnail dump.
- **Smooth, tasteful animations:** `framer-motion` for page transitions, subtle fade+scale on image reveal during scroll, spring-physics swipe in the photo viewer, backdrop blur on viewer open. Animations are fast (200–300ms) and elegant — never bouncy, playful, or attention-grabbing.
- **Photo viewer:** Full-screen dark overlay with smooth pinch-to-zoom, swipe-to-navigate with inertia, and swipe-down-to-close gesture. Must feel as polished as iOS Photos or Google Photos.
- **Zero layout shifts:** Every image slot must define its aspect ratio (CSS `aspect-ratio` or padding-bottom technique) and show a blurhash/shimmer placeholder before the real image loads. No content jumping, ever.
- **Loading states:** Skeleton screens with a subtle shimmer animation that mirrors the layout structure. No generic spinners except for discrete actions (download, OTP verification).

**Dashboard UI (Photographer):**
- **Clean, spacious, light-themed** by default. Generous whitespace. Card-based layouts with soft shadows and clear visual hierarchy.
- **Upload experience:** Must feel responsive and trustworthy. Real-time per-file progress bars, overall progress with speed indicator, clear error states (red badge + retry button) without being alarming. The photographer should feel confident leaving a 15,000-photo upload running.
- **Data tables** (guest list, analytics): clean hairline borders, row hover highlights, sortable columns with visible sort direction indicators, pagination with page size selector.

**Cross-Cutting:**
- **Typography:** Inter (body) and Plus Jakarta Sans (display headings). Large, confident headings with generous `line-height`. Text should breathe.
- **Color:** Neutral base (dark grays for gallery, light grays for dashboard) with a single accent color for CTAs and interactive highlights. Avoid competing colors.
- **Micro-interactions:** Button press feedback (subtle scale-down), toggle animations, toast notifications that slide in/out smoothly. Every interaction should have visual acknowledgment.
- **Responsive excellence:** Guest pages must be flawless from iPhone SE (375px) to iPad (768px) — these are the primary devices. Dashboard must be clean on 1280px+ with functional fallback at 768px (collapsed sidebar).

### 4.1 Theme Configuration

The design system uses CSS custom properties (variables) managed through Tailwind, enabling a single theme definition that powers both light (dashboard) and dark (gallery) modes.

```css
/* globals.css */
@layer base {
  :root {
    /* Dashboard (Light Mode) */
    --background: 0 0% 100%;
    --foreground: 240 10% 3.9%;
    --card: 0 0% 100%;
    --card-foreground: 240 10% 3.9%;
    --primary: 240 5.9% 10%;
    --primary-foreground: 0 0% 98%;
    --secondary: 240 4.8% 95.9%;
    --secondary-foreground: 240 5.9% 10%;
    --muted: 240 4.8% 95.9%;
    --muted-foreground: 240 3.8% 46.1%;
    --accent: 240 4.8% 95.9%;
    --accent-foreground: 240 5.9% 10%;
    --destructive: 0 84.2% 60.2%;
    --border: 240 5.9% 90%;
    --ring: 240 5.9% 10%;
    --radius: 0.5rem;
  }

  .dark {
    /* Gallery (Dark Mode) */
    --background: 240 10% 3.9%;
    --foreground: 0 0% 98%;
    --card: 240 10% 3.9%;
    --card-foreground: 0 0% 98%;
    --primary: 0 0% 98%;
    --primary-foreground: 240 5.9% 10%;
    --secondary: 240 3.7% 15.9%;
    --secondary-foreground: 0 0% 98%;
    --muted: 240 3.7% 15.9%;
    --muted-foreground: 240 5% 64.9%;
    --accent: 240 3.7% 15.9%;
    --accent-foreground: 0 0% 98%;
    --destructive: 0 62.8% 30.6%;
    --border: 240 3.7% 15.9%;
    --ring: 240 4.9% 83.9%;
  }
}
```

### 4.2 Typography

```typescript
// tailwind.config.ts
const config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Plus Jakarta Sans', 'Inter', 'sans-serif'],
      },
      fontSize: {
        'display-xl': ['3rem', { lineHeight: '1.1', fontWeight: '700' }],
        'display-lg': ['2.25rem', { lineHeight: '1.2', fontWeight: '700' }],
        'display-md': ['1.875rem', { lineHeight: '1.3', fontWeight: '600' }],
        'heading': ['1.5rem', { lineHeight: '1.4', fontWeight: '600' }],
        'subheading': ['1.125rem', { lineHeight: '1.5', fontWeight: '500' }],
      },
    },
  },
};
```

### 4.3 Responsive Breakpoints

| Breakpoint | Width | Target |
|---|---|---|
| `sm` | 640px | Large phones (landscape) |
| `md` | 768px | Tablets |
| `lg` | 1024px | Small laptops |
| `xl` | 1280px | Desktops |
| `2xl` | 1536px | Large desktops |

The gallery (guest/couple) is designed **mobile-first** (base styles target 320px+). The dashboard is designed **desktop-first** but must remain functional on tablets.

### 4.4 Photo Grid Columns

| Viewport | Guest Gallery | Couple Gallery | Dashboard Grid |
|---|---|---|---|
| < 640px (mobile) | 2 columns | 2 columns | 2 columns |
| 640–768px | 3 columns | 3 columns | 3 columns |
| 768–1024px | 3 columns | 4 columns | 4 columns |
| 1024–1280px | 4 columns | 5 columns | 5 columns |
| > 1280px | 4 columns | 6 columns | 6 columns |

### 4.5 Animation Tokens

```typescript
// framer-motion variants used across the app
export const fadeIn = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.2, ease: 'easeOut' },
};

export const slideUp = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 20 },
  transition: { duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] },
};

export const scaleIn = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
  transition: { duration: 0.2 },
};
```

---

## 5. Photographer Studio Dashboard

### 5.1 Authentication Screens

#### 5.1.1 Registration Flow

```
┌─────────────────────────────────────────────┐
│              Create Your Account             │
│                                              │
│  ┌─────────────────────────────────────────┐ │
│  │  Studio Name            [____________]  │ │
│  │  Email                  [____________]  │ │
│  │  Password               [____________]  │ │
│  │  Confirm Password       [____________]  │ │
│  │  Mobile Number   [+91 ▼][____________]  │ │
│  │                                         │ │
│  │  [      Send OTP to Mobile       ]      │ │
│  │                                         │ │
│  │  OTP   [_ _ _ _ _ _]                   │ │
│  │                                         │ │
│  │  [      Create Account            ]     │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  Already have an account? [Log in]           │
└─────────────────────────────────────────────┘
```

**Validation Rules:**
- Studio name: 2–100 characters
- Email: Valid email format, unique in system
- Password: Minimum 8 characters, at least one uppercase, one lowercase, one digit
- Mobile: Valid Indian mobile number (10 digits), verified via OTP
- OTP: 6-digit numeric, 5-minute expiry, max 3 attempts

#### 5.1.2 Login Flow

```
┌─────────────────────────────────────────────┐
│              Welcome Back                    │
│                                              │
│  ┌─────────────────────────────────────────┐ │
│  │  Email                  [____________]  │ │
│  │  Password               [____________]  │ │
│  │                                         │ │
│  │  □ Remember me      [Forgot password?]  │ │
│  │                                         │ │
│  │  [           Log In              ]      │ │
│  └─────────────────────────────────────────┘ │
│                                              │
│  Don't have an account? [Sign up]            │
└─────────────────────────────────────────────┘
```

### 5.2 Dashboard Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  ┌──────┐  AI Photo Sharing Platform          [🔔] [Avatar ▼]  │
│  │ Logo │                                                        │
│  └──────┘                                                        │
├──────────────┬───────────────────────────────────────────────────┤
│              │                                                   │
│  NAVIGATION  │              MAIN CONTENT AREA                    │
│              │                                                   │
│  📷 Events   │  ┌─────────────────────────────────────────────┐  │
│  👤 Profile  │  │                                             │  │
│  ⚙️ Settings │  │   (Content changes based on route)          │  │
│              │  │                                             │  │
│              │  │                                             │  │
│              │  │                                             │  │
│              │  │                                             │  │
│              │  │                                             │  │
│              │  └─────────────────────────────────────────────┘  │
│              │                                                   │
└──────────────┴───────────────────────────────────────────────────┘
```

- **Sidebar:** Fixed left sidebar (collapsible on tablet). Contains navigation links, studio name/logo, and storage usage indicator.
- **Header:** Top bar with platform branding, notification bell (processing complete alerts), and user avatar dropdown (profile, settings, logout).
- **Content Area:** Dynamic based on the current route.

### 5.3 Event List View (`/dashboard/events`)

```
┌──────────────────────────────────────────────────────────────┐
│  Your Events                              [+ Create Event]   │
│                                                              │
│  [Search events...]          Sort: [Most Recent ▼]           │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 📸 Rahul & Priya Wedding        │ 12 Jun 2026          │ │
│  │    3,450 photos · 12 folders     │ [● Ready]            │ │
│  │    186 guests viewed             │                      │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 📸 Amit Corporate Summit        │ 28 May 2026          │ │
│  │    890 photos · 3 folders        │ [● Processing 67%]   │ │
│  │    0 guests viewed               │                      │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ 📸 Sneha Birthday Party          │ 15 May 2026          │ │
│  │    240 photos · 1 folder         │ [● Archived]         │ │
│  │    34 guests viewed              │                      │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Event Card Details:**
- Cover image thumbnail (first photo or photographer-selected)
- Event name and date
- Photo count and folder count
- Guest count (who have viewed)
- Status badge: Draft (gray), Uploading (blue), Processing (yellow with %), Ready (green), Archived (muted)
- Click → navigates to Event Detail View

**Actions:**
- Search by event name
- Sort by date (newest/oldest), status, name
- Create new event (opens creation dialog/page)

### 5.4 Event Creation Dialog

```
┌──────────────────────────────────────────┐
│          Create New Event                │
│                                          │
│  Event Name    [________________________]│
│  Event Date    [📅 Select date(s)      ] │
│  Event Type    [Wedding            ▼   ] │
│  Description   [________________________]│
│                [________________________]│
│                                          │
│         [Cancel]    [Create Event]        │
└──────────────────────────────────────────┘
```

**Fields:**
- Event Name: Required, 3–200 characters
- Event Date: Required, date picker with range support for multi-day events
- Event Type: Dropdown — Wedding, Corporate, Birthday, Other (for analytics only)
- Description: Optional, max 500 characters

After creation, the user is navigated to the Event Detail View with the folder management interface.

### 5.5 Event Detail View (`/dashboard/events/[id]`)

This is the main management hub for an event. It uses a tabbed layout:

```
┌──────────────────────────────────────────────────────────────┐
│  ← Back to Events                                            │
│                                                              │
│  Rahul & Priya Wedding                    [⚙️ Event Settings]│
│  June 12-14, 2026 · Wedding · 3,450 photos                  │
│                                                              │
│  ┌────────┬──────────┬───────────┬──────────┐                │
│  │ Photos │  Upload  │ Analytics │  Share   │                │
│  └────────┴──────────┴───────────┴──────────┘                │
│                                                              │
│  (Tab content renders below)                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### 5.5.1 Photos Tab (Folder Management + Photo Grid)

**Left Panel — Folder Tree:**
```
┌──────────────┬───────────────────────────────────────────────┐
│              │                                               │
│  FOLDERS     │          PHOTO GRID                           │
│  [+ Folder]  │                                               │
│              │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
│  📁 All Photos│  │     │ │     │ │     │ │     │ │     │   │
│  📁 Mehndi   │  │ img │ │ img │ │ img │ │ img │ │ img │   │
│    📁 Bride  │  │     │ │     │ │     │ │     │ │     │   │
│    📁 Guests │  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘   │
│  📁 Sangeet  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐   │
│  📁 Wedding  │  │     │ │     │ │     │ │     │ │     │   │
│    📁 Ceremony│ │ img │ │ img │ │ img │ │ img │ │ img │   │
│    📁 Couple │  │     │ │     │ │     │ │     │ │     │   │
│  📁 Reception│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘   │
│              │                                               │
│              │  Showing 450 of 3,450 photos                  │
│              │  [Load More] or scroll to load                │
│              │                                               │
└──────────────┴───────────────────────────────────────────────┘
```

**Folder Tree Functionality:**
- Click folder → filters photo grid to show only that folder's contents
- "All Photos" shows everything across all folders
- Right-click context menu: Rename, Delete, Create subfolder
- Drag-and-drop reordering of folders
- Drag photos from grid onto folder tree items to move them
- New folder button with inline name editing

**Photo Grid Functionality:**
- Virtualized masonry grid (only renders visible photos + small buffer)
- Each photo thumbnail shows:
  - Web-proxy image
  - Face count badge (e.g., "3 faces" overlay)
  - Checkbox for multi-select (appears on hover)
- Multi-select actions toolbar (appears when photos are selected):
  - Move to folder → folder picker dropdown
  - Delete selected
  - Count indicator: "23 photos selected"
- Click photo → opens detail viewer (not full gallery viewer; shows metadata: filename, dimensions, file size, faces detected, folder path)

#### 5.5.2 Upload Tab

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Upload Photos                                               │
│                                                              │
│  Target Folder: [Mehndi / Bride Getting Ready  ▼]           │
│                                                              │
│  ┌──────────────────────────────────────────────────────────┐│
│  │                                                          ││
│  │     ┌──────────────────────────┐                         ││
│  │     │    📁                     │                         ││
│  │     │                          │                         ││
│  │     │  Drag & drop files or    │                         ││
│  │     │  folders here            │                         ││
│  │     │                          │                         ││
│  │     │  or [Browse Files]       │                         ││
│  │     │     [Browse Folder]      │                         ││
│  │     │                          │                         ││
│  │     │  Supports: JPG, PNG,     │                         ││
│  │     │  HEIC, TIFF, WebP        │                         ││
│  │     └──────────────────────────┘                         ││
│  │                                                          ││
│  └──────────────────────────────────────────────────────────┘│
│                                                              │
│  ── Upload Progress ──────────────────────────────────────── │
│                                                              │
│  Overall: ████████████░░░░░░░░  2,340 / 3,450  (67.8%)     │
│  Speed: 45.2 MB/s · ETA: ~12 min                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  IMG_4521.jpg  (24.3 MB)   ████████████████  Done ✓   │  │
│  │  IMG_4522.jpg  (18.7 MB)   ████████████░░░░  78%      │  │
│  │  IMG_4523.jpg  (22.1 MB)   ████░░░░░░░░░░░░  23%      │  │
│  │  IMG_4524.jpg  (19.8 MB)   Queued...                   │  │
│  │  IMG_4525.heic (31.2 MB)   Queued...                   │  │
│  │  ...                                                   │  │
│  │  ⚠️ IMG_4519.jpg  (25.1 MB) Failed - [Retry]          │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [Pause All]  [Cancel All]                                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Upload Interface Design:**

1. **Target Folder Selector:** Dropdown showing the event's folder tree. New uploads go into the selected folder. If "Browse Folder" is used and the dropped folder contains subfolders, the system creates matching folders automatically.

2. **Dropzone:** Large, clearly defined drop area. Accepts:
   - Individual files (drag or file picker)
   - Folders (drag or folder picker via `webkitdirectory`)
   - Deeply nested folder structures (preserved on upload)

3. **Upload Progress Section:**
   - **Overall progress bar:** Total files completed / total, percentage, upload speed, estimated time remaining.
   - **Per-file list:** Scrollable list showing each file's progress. States: Queued, Uploading (with progress %), Done (checkmark), Failed (with retry button).
   - **Active uploads:** Up to 6 concurrent file uploads (browser limit). The upload manager queues the rest.

4. **Controls:**
   - Pause All: Pauses all active uploads (tus protocol supports this natively)
   - Cancel All: Cancels remaining uploads (with confirmation dialog)
   - Per-file retry for failed uploads

5. **State Persistence:**
   - Upload state (which files are complete, which are pending) is stored in `localStorage` keyed by event ID.
   - If the browser tab is closed and reopened, the Upload tab shows the last known state with an option to resume pending files.

#### 5.5.3 Analytics Tab

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Event Analytics                                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │    186       │  │   1,247      │  │    892       │       │
│  │  Total       │  │  Total       │  │  Total       │       │
│  │  Guests      │  │  Views       │  │  Downloads   │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                              │
│  ── Most Viewed Photos ─────────────────────────────────────│
│                                                              │
│  ┌─────┐ IMG_4521.jpg     342 views  · 128 downloads        │
│  │ img │ Mehndi / Bride Getting Ready                        │
│  └─────┘                                                     │
│  ┌─────┐ IMG_4890.jpg     289 views  · 97 downloads         │
│  │ img │ Wedding / Ceremony                                  │
│  └─────┘                                                     │
│  ┌─────┐ IMG_5102.jpg     234 views  · 85 downloads         │
│  │ img │ Reception                                           │
│  └─────┘                                                     │
│                                                              │
│  ── Guest List (Lead Capture) ──────────────────────────────│
│                                                              │
│  [Export CSV ↓]                                              │
│                                                              │
│  Name             Phone          Visited    Photos  Downloads│
│  ─────────────────────────────────────────────────────────── │
│  Ankit Sharma     +91-98765xxxx  Jun 14     23      8       │
│  Priya Mehta      +91-87654xxxx  Jun 14     45      12      │
│  Suresh Kumar     +91-76543xxxx  Jun 15     18      5       │
│  Meera Patel      +91-65432xxxx  Jun 15     31      9       │
│  ...                                                         │
│                                                              │
│  Showing 1-20 of 186 guests    [← Prev]  [Next →]           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Analytics Components:**
- **Summary Cards:** Three stat cards showing total guests, total views, total downloads.
- **Most Viewed Photos:** Top 10 photos ranked by view count with thumbnails, filenames, folder paths, and download counts.
- **Guest List Table:** Paginated table with columns: Name, Phone, First Visit Timestamp, Photos Matched, Photos Downloaded. Sortable by any column. CSV export button.

#### 5.5.4 Share Tab

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Share Your Event                                            │
│                                                              │
│  ── Master Link (For the Couple) ───────────────────────────│
│                                                              │
│  The couple gets full access to all photos in every folder.  │
│                                                              │
│  https://platform.com/event/rahul-priya-2026/master          │
│  [Copy Link 📋]                                              │
│                                                              │
│  Status: ● Active                        [Deactivate Link]  │
│                                                              │
│  ── Guest Link (For Wedding Guests) ────────────────────────│
│                                                              │
│  Guests authenticate with phone, take a selfie, and see     │
│  only photos they appear in.                                 │
│                                                              │
│  https://platform.com/event/rahul-priya-2026/guest           │
│  [Copy Link 📋]                                              │
│                                                              │
│  Status: ● Active                        [Deactivate Link]  │
│                                                              │
│  ── Download Settings ──────────────────────────────────────│
│                                                              │
│  Allow guests to download original high-res photos:          │
│  [●─────] ON                                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.6 Profile & Settings Page (`/dashboard/profile`)

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  Studio Profile                                              │
│                                                              │
│  ── Studio Information ─────────────────────────────────────│
│                                                              │
│  Studio Name     [Prism Photography Studio    ]              │
│  Contact Email   [prism@studio.com            ]              │
│  Phone           [+91-9876543210              ]              │
│                                                              │
│  ── Studio Logo ────────────────────────────────────────────│
│                                                              │
│  ┌────────────────┐                                          │
│  │                │  [Upload New Logo]                        │
│  │   [Logo Img]   │  Recommended: 200x200px, PNG             │
│  │                │                                          │
│  └────────────────┘                                          │
│                                                              │
│  ── Watermark ──────────────────────────────────────────────│
│                                                              │
│  ┌────────────────┐                                          │
│  │                │  [Upload Watermark]                       │
│  │ [Watermark Img]│  Recommended: PNG with transparency      │
│  │                │                                          │
│  └────────────────┘                                          │
│                                                              │
│  Preview:                                                    │
│  ┌──────────────────────────────────────┐                    │
│  │                                      │                    │
│  │        [Sample Photo]                │                    │
│  │                                      │                    │
│  │                     [watermark]      │                    │
│  └──────────────────────────────────────┘                    │
│                                                              │
│  ── Storage ────────────────────────────────────────────────│
│                                                              │
│  Used: 145.3 GB / 1,000 GB                                  │
│  ████████████████░░░░░░░░░░░░░░  14.5%                      │
│                                                              │
│  Active: 120.1 GB · Archived: 25.2 GB                       │
│                                                              │
│  [Save Changes]                                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Couple Interface (Master Link)

### 6.1 Authentication Screen

```
┌─────────────────────────────────────────┐
│                                         │
│  ┌─────┐                                │
│  │Logo │  Prism Photography Studio      │
│  └─────┘                                │
│                                         │
│  Rahul & Priya Wedding                  │
│  June 12-14, 2026                       │
│                                         │
│  ─────────────────────────────────────  │
│                                         │
│  Enter your details to view your        │
│  wedding gallery                        │
│                                         │
│  Name        [________________________] │
│  Mobile      [+91 ▼] [______________]  │
│                                         │
│  [     Send OTP      ]                  │
│                                         │
│  OTP   [_ _ _ _ _ _]                   │
│                                         │
│  [    View Gallery    ]                 │
│                                         │
└─────────────────────────────────────────┘
```

- Dark-themed page (consistent with gallery aesthetic)
- Photographer's logo and studio name prominently displayed
- Event name and date as heading
- Minimal form: just name, phone, and OTP

### 6.2 Gallery View

```
┌──────────────────────────────────────────┐
│  ┌─────┐  Rahul & Priya Wedding         │
│  │Logo │  Prism Photography Studio       │
│  └─────┘                                 │
│                                          │
│  ┌────────┬─────────┬─────────┬────────┐ │
│  │Mehndi  │ Sangeet │ Wedding │Recep.  │ │
│  │ (450)  │  (680)  │ (1200)  │ (900)  │ │
│  └────────┴─────────┴─────────┴────────┘ │
│                                          │
│  [★ Favorites (23)]                      │
│                                          │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │
│  │      │ │      │ │      │ │      │   │
│  │ img  │ │ img  │ │ img  │ │ img  │   │
│  │    ♡ │ │    ♡ │ │    ❤ │ │    ♡ │   │
│  └──────┘ └──────┘ └──────┘ └──────┘   │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │
│  │      │ │      │ │      │ │      │   │
│  │ img  │ │ img  │ │ img  │ │ img  │   │
│  │    ♡ │ │    ❤ │ │    ♡ │ │    ♡ │   │
│  └──────┘ └──────┘ └──────┘ └──────┘   │
│                                          │
│  (scroll for more...)                    │
│                                          │
└──────────────────────────────────────────┘
```

**Key UI Elements:**
- **Header:** Photographer's logo + studio name + event name. Sticky on scroll.
- **Folder Tabs:** Horizontal scrollable tabs for each folder. Shows photo count per folder. "All" tab to view everything.
- **Favorites Button:** Floating or tab-positioned button showing favorite count. Tap to view only favorites.
- **Photo Grid:** Masonry layout with lazy-loaded web-proxy images. Each photo has a heart icon overlay in the bottom-right for favoriting.
- **Photo Viewer:** Tap any photo to open the full-screen lightbox viewer:
  - Swipe left/right to navigate
  - Pinch-to-zoom
  - Heart button (favorite/unfavorite)
  - Download button (fetches original high-res)
  - Close (X) button

### 6.3 Favorites View

- Shows only photos the couple has marked as favorite
- Same grid layout and viewer as the main gallery
- Photos grouped by their original folder (optional)
- Empty state: "No favorites yet. Tap the ♡ on any photo to save it here."

---

## 7. Guest Interface (Guest Link / PWA)

### 7.1 Landing Page

```
┌─────────────────────────────────────────┐
│                                         │
│  ┌─────┐                                │
│  │Logo │  Prism Photography Studio      │
│  └─────┘                                │
│                                         │
│  Rahul & Priya Wedding                  │
│  June 12-14, 2026                       │
│                                         │
│  ─────────────────────────────────────  │
│                                         │
│  Find your photos from the wedding!     │
│                                         │
│  Enter your details below to see the    │
│  photos you appear in.                  │
│                                         │
│  Name        [________________________] │
│  Mobile      [+91 ▼] [______________]  │
│                                         │
│  [     Send OTP      ]                  │
│                                         │
│  OTP   [_ _ _ _ _ _]                   │
│                                         │
│  [    Find My Photos   ]               │
│                                         │
└─────────────────────────────────────────┘
```

- Same dark-themed aesthetic as couple interface
- Clear, concise copy explaining what will happen
- Name + Phone + OTP (same as couple, but leads to selfie step next)

### 7.2 Selfie Capture Screen

```
┌─────────────────────────────────────────┐
│                                         │
│  Almost there!                          │
│  Take a quick selfie so we can find     │
│  your photos.                           │
│                                         │
│  ┌─────────────────────────────────────┐│
│  │                                     ││
│  │                                     ││
│  │         ┌───────────────┐           ││
│  │         │               │           ││
│  │         │   (Camera     │           ││
│  │         │    Feed)      │           ││
│  │         │               │           ││
│  │         │   ○ Face      │           ││
│  │         │   Guide       │           ││
│  │         │   Overlay     │           ││
│  │         │               │           ││
│  │         └───────────────┘           ││
│  │                                     ││
│  │  Position your face within the      ││
│  │  circle. Look straight at the       ││
│  │  camera.                            ││
│  │                                     ││
│  └─────────────────────────────────────┘│
│                                         │
│         [  📷 Capture Selfie  ]         │
│                                         │
│  Your selfie is used only to find your  │
│  photos and is not stored permanently.  │
│                                         │
└─────────────────────────────────────────┘
```

**Selfie Capture Implementation:**

1. **Camera Access:** Request front-facing camera via `getUserMedia` API. If denied, show a clear message explaining why camera access is needed and how to enable it.

2. **Face Guide Overlay:** A circular or oval SVG overlay positioned in the center of the camera feed. The guide helps the guest position their face correctly for better face detection accuracy.

3. **Real-Time Face Detection (Client-Side):**
   - Use a lightweight client-side face detection model (e.g., TensorFlow.js `@mediapipe/face_detection` or `face-api.js` browser build) to:
     - Confirm a face is detected in the frame before enabling the capture button
     - Show visual feedback (guide turns green when face is properly positioned)
     - Check for basic quality: face size relative to frame (not too far), sharpness
   - The capture button is disabled until a valid face is detected

4. **Capture:** On tap:
   - Freeze the current frame
   - Show a brief preview with "Retake" / "Use This Photo" options
   - On confirmation, encode the image as JPEG (quality 0.85) and send to backend

5. **Privacy Notice:** Small text beneath the capture button: "Your selfie is used only to find your photos and is not stored permanently." (builds trust, especially for privacy-conscious users)

### 7.3 Processing Screen

```
┌─────────────────────────────────────────┐
│                                         │
│                                         │
│                                         │
│          ┌─────────────────┐            │
│          │                 │            │
│          │   ✨ (animated   │            │
│          │     sparkle     │            │
│          │     loader)     │            │
│          │                 │            │
│          └─────────────────┘            │
│                                         │
│    We're gathering your memories...     │
│                                         │
│    This might take a moment.            │
│    You can close this page and come     │
│    back later — just log in with your   │
│    mobile number.                       │
│                                         │
│                                         │
│                                         │
│  ┌─────┐  Prism Photography Studio      │
│  │Logo │                                │
│  └─────┘                                │
│                                         │
└─────────────────────────────────────────┘
```

- Full-screen branded loading state
- Animated loader (subtle, elegant — CSS-only or Lottie)
- Reassuring copy that they can close and return
- Photographer's branding at the bottom
- Typically shown for < 2 seconds (face matching is near-instant for pre-indexed events)

### 7.4 Personalized Gallery

```
┌─────────────────────────────────────────┐
│  ┌─────┐  Rahul & Priya Wedding         │
│  │Logo │  Prism Photography Studio       │
│  └─────┘                                 │
│                                          │
│  Hi Ankit! We found 23 photos of you.   │
│                                          │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │
│  │      │ │      │ │      │ │      │   │
│  │ img  │ │ img  │ │ img  │ │ img  │   │
│  │   ↓  │ │   ↓  │ │   ↓  │ │   ↓  │   │
│  └──────┘ └──────┘ └──────┘ └──────┘   │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │
│  │      │ │      │ │      │ │      │   │
│  │ img  │ │ img  │ │ img  │ │ img  │   │
│  │   ↓  │ │   ↓  │ │   ↓  │ │   ↓  │   │
│  └──────┘ └──────┘ └──────┘ └──────┘   │
│                                          │
│  (scroll for more...)                    │
│                                          │
└──────────────────────────────────────────┘
```

**Key UI Elements:**
- **Personalized greeting:** "Hi {name}! We found {count} photos of you."
- **Photo Grid:** Same masonry layout as couple gallery, but showing only matched photos.
- **Download Icon:** Small download arrow overlay on each photo thumbnail.
- **Photo Viewer:** Tap to open full-screen viewer with:
  - Swipe left/right navigation
  - Pinch-to-zoom
  - Prominent "Download" button
  - Close (X) button
- **Empty State:** If no matches are found: "We couldn't find photos matching your face. This can happen if the lighting was different or if you appear in group photos from a distance. Please try again with a clearer selfie." [Retake Selfie] button.

### 7.5 Download Flow

When a guest taps "Download" on a photo:

1. **UI:** Download button shows a loading spinner.
2. **Request:** Frontend calls the backend download endpoint, which retrieves the original from cold storage.
3. **Delivery:** The original file is streamed to the guest's device as a standard file download. On mobile, this typically saves to the Photos app (iOS) or Downloads folder (Android).
4. **Completion:** Download button shows a checkmark briefly, then returns to the download icon.
5. **If downloads are disabled:** The download button is hidden. Photos are view-only with the watermarked web-proxy.

---

## 8. PWA Configuration

### 8.1 Web App Manifest

```json
{
  "name": "AI Photo Sharing Platform",
  "short_name": "PhotoShare",
  "description": "Find and download your event photos instantly",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0a0a0a",
  "theme_color": "#0a0a0a",
  "orientation": "portrait-primary",
  "icons": [
    {
      "src": "/icons/icon-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512x512-maskable.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ]
}
```

### 8.2 Service Worker Strategy

```typescript
// next.config.js (using @serwist/next or next-pwa)
const withPWA = require('next-pwa')({
  dest: 'public',
  disable: process.env.NODE_ENV === 'development',
  runtimeCaching: [
    {
      urlPattern: /^https:\/\/cdn\..*\.(webp|jpg|jpeg|png)$/,
      handler: 'CacheFirst',
      options: {
        cacheName: 'photo-cache',
        expiration: {
          maxEntries: 200,
          maxAgeSeconds: 7 * 24 * 60 * 60, // 7 days
        },
      },
    },
    {
      urlPattern: /^https:\/\/api\..*$/,
      handler: 'NetworkFirst',
      options: {
        cacheName: 'api-cache',
        expiration: {
          maxEntries: 50,
          maxAgeSeconds: 5 * 60, // 5 minutes
        },
      },
    },
    {
      urlPattern: /\.(js|css|woff2?)$/,
      handler: 'StaleWhileRevalidate',
      options: {
        cacheName: 'static-resources',
      },
    },
  ],
});
```

**Caching Strategy:**
- **Photo thumbnails (web-proxies):** CacheFirst — once loaded, served from cache. Cache limited to 200 entries to prevent storage bloat on guest devices.
- **API responses:** NetworkFirst — always try fresh data, fall back to cache if offline.
- **Static assets (JS, CSS, fonts):** StaleWhileRevalidate — serve cached version immediately, update cache in background.

### 8.3 Add to Home Screen

The PWA prompts "Add to Home Screen" on supported browsers (Android Chrome, iOS Safari) after the guest has interacted with the gallery. This provides:
- App-like icon on the home screen
- Standalone window (no browser chrome)
- Faster subsequent loads

---

## 9. State Management

### 9.1 State Architecture

State is split across three layers:

| Layer | Tool | What It Manages |
|---|---|---|
| **Server State** | `@tanstack/react-query` | API data (events, photos, analytics, guest sessions). Handles caching, background refetching, optimistic updates, pagination. |
| **Client State** | `zustand` | UI-specific state that doesn't come from the server: auth tokens, upload queue/progress, gallery view preferences, modal states. |
| **URL State** | Next.js router + `searchParams` | Active filters, current folder, pagination, sort order. Keeps state shareable via URL. |

### 9.2 Zustand Store Definitions

#### Auth Store

```typescript
interface AuthState {
  // Photographer auth
  photographer: Photographer | null;
  accessToken: string | null;
  isAuthenticated: boolean;

  // Actions
  setPhotographer: (photographer: Photographer, token: string) => void;
  logout: () => void;
  refreshToken: () => Promise<void>;
}

interface GuestAuthState {
  // Guest/Couple auth
  guestSession: GuestSession | null;
  isVerified: boolean;

  // Actions
  setGuestSession: (session: GuestSession) => void;
  clearGuestSession: () => void;
}
```

#### Upload Store

```typescript
interface UploadState {
  // Upload queue
  files: UploadFile[];
  activeUploads: number;
  maxConcurrent: number; // default 6

  // Progress
  totalFiles: number;
  completedFiles: number;
  failedFiles: number;
  totalBytes: number;
  uploadedBytes: number;
  uploadSpeed: number; // bytes per second

  // Status
  status: 'idle' | 'uploading' | 'paused' | 'complete' | 'error';

  // Actions
  addFiles: (files: File[], targetFolderId: string) => void;
  removeFile: (fileId: string) => void;
  retryFile: (fileId: string) => void;
  pauseAll: () => void;
  resumeAll: () => void;
  cancelAll: () => void;
  updateFileProgress: (fileId: string, progress: FileProgress) => void;
}

interface UploadFile {
  id: string;
  file: File;
  targetFolderId: string;
  status: 'queued' | 'uploading' | 'processing' | 'complete' | 'failed';
  progress: number; // 0-100
  uploadedBytes: number;
  totalBytes: number;
  tusUploadUrl?: string; // for resume
  error?: string;
  retryCount: number;
}
```

#### Gallery Store

```typescript
interface GalleryState {
  // View preferences
  currentFolderId: string | null; // null = "All Photos"
  sortBy: 'date' | 'name';
  sortOrder: 'asc' | 'desc';

  // Selection (dashboard only)
  selectedPhotoIds: Set<string>;
  isSelecting: boolean;

  // Viewer
  viewerOpen: boolean;
  viewerPhotoId: string | null;

  // Actions
  setFolder: (folderId: string | null) => void;
  toggleSelect: (photoId: string) => void;
  selectAll: () => void;
  clearSelection: () => void;
  openViewer: (photoId: string) => void;
  closeViewer: () => void;
}
```

### 9.3 React Query Configuration

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,        // 5 minutes
      gcTime: 30 * 60 * 1000,           // 30 minutes (garbage collection)
      retry: 2,
      refetchOnWindowFocus: false,       // disable aggressive refetching
    },
  },
});
```

**Key Query Patterns:**

```typescript
// Paginated photo list with infinite scroll
function useEventPhotos(eventId: string, folderId?: string) {
  return useInfiniteQuery({
    queryKey: ['events', eventId, 'photos', { folderId }],
    queryFn: ({ pageParam = 0 }) =>
      apiClient.getPhotos(eventId, { folderId, offset: pageParam, limit: 50 }),
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? lastPage.offset + lastPage.limit : undefined,
  });
}

// Guest matched photos
function useGuestPhotos(eventSlug: string, sessionId: string) {
  return useQuery({
    queryKey: ['guest', eventSlug, 'photos', sessionId],
    queryFn: () => apiClient.getGuestPhotos(eventSlug, sessionId),
    enabled: !!sessionId,
  });
}

// Optimistic favorite toggle
function useToggleFavorite(eventSlug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (photoId: string) =>
      apiClient.toggleFavorite(eventSlug, photoId),
    onMutate: async (photoId) => {
      // Optimistically update the UI
      await queryClient.cancelQueries(['couple', eventSlug, 'photos']);
      const previous = queryClient.getQueryData(['couple', eventSlug, 'photos']);
      queryClient.setQueryData(['couple', eventSlug, 'photos'], (old) =>
        toggleFavoriteInData(old, photoId)
      );
      return { previous };
    },
    onError: (err, photoId, context) => {
      queryClient.setQueryData(['couple', eventSlug, 'photos'], context.previous);
    },
  });
}
```

---

## 10. API Integration Layer

### 10.1 API Client

A centralized API client wraps `fetch` (or `axios`) with:
- Base URL configuration (environment-specific)
- Automatic auth token injection via interceptors
- Request/response type safety via generics
- Error normalization (API errors → consistent `ApiError` type)
- Automatic token refresh on 401 responses
- Request cancellation via `AbortController`

```typescript
// lib/api-client.ts
class ApiClient {
  private baseUrl: string;
  private getToken: () => string | null;

  constructor(config: ApiClientConfig) {
    this.baseUrl = config.baseUrl;
    this.getToken = config.getToken;
  }

  async request<T>(
    method: string,
    path: string,
    options?: RequestOptions
  ): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options?.headers,
    };

    const response = await fetch(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: options?.body ? JSON.stringify(options.body) : undefined,
      signal: options?.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ApiError(response.status, error.message, error.code);
    }

    return response.json();
  }

  // Typed convenience methods
  get<T>(path: string, signal?: AbortSignal) { ... }
  post<T>(path: string, body: unknown) { ... }
  put<T>(path: string, body: unknown) { ... }
  delete<T>(path: string) { ... }
}
```

### 10.2 API Endpoints (Frontend Expects)

These are the endpoints the frontend will call. During the mock data phase, these are intercepted by MSW (Mock Service Worker) or Next.js API routes returning mock data.

#### Authentication

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Photographer registration |
| POST | `/api/auth/login` | Photographer login |
| POST | `/api/auth/logout` | Photographer logout |
| POST | `/api/auth/refresh` | Refresh access token |
| POST | `/api/auth/forgot-password` | Send password reset email |
| POST | `/api/auth/reset-password` | Reset password with token |
| POST | `/api/auth/send-otp` | Send OTP to mobile number |
| POST | `/api/auth/verify-otp` | Verify OTP |

#### Events

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/events` | List photographer's events |
| POST | `/api/events` | Create new event |
| GET | `/api/events/{id}` | Get event details |
| PUT | `/api/events/{id}` | Update event |
| DELETE | `/api/events/{id}` | Delete event |

#### Folders

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/events/{id}/folders` | List folders in event |
| POST | `/api/events/{id}/folders` | Create folder |
| PUT | `/api/events/{id}/folders/{folderId}` | Update folder (rename, reorder) |
| DELETE | `/api/events/{id}/folders/{folderId}` | Delete folder |

#### Photos

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/events/{id}/photos` | List photos (paginated, filterable by folder) |
| DELETE | `/api/events/{id}/photos/{photoId}` | Delete photo |
| POST | `/api/events/{id}/photos/move` | Move photos to folder |
| GET | `/api/events/{id}/photos/{photoId}/download` | Download original high-res |

#### Upload

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/upload/create` | Initialize tus upload (returns upload URL) |
| PATCH | `/api/upload/{uploadId}` | Upload chunk (tus protocol) |
| HEAD | `/api/upload/{uploadId}` | Get upload offset for resume (tus protocol) |

#### Sharing

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/events/{id}/links` | Get master + guest links |
| PUT | `/api/events/{id}/links/{type}/toggle` | Activate/deactivate a link |
| PUT | `/api/events/{id}/settings` | Update event settings (download toggle) |

#### Guest / Couple

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/event/{slug}/info` | Get event info for landing page (public) |
| POST | `/api/event/{slug}/auth` | Guest/couple OTP auth |
| POST | `/api/event/{slug}/selfie` | Submit selfie for face matching |
| GET | `/api/event/{slug}/guest/photos` | Get guest's matched photos |
| GET | `/api/event/{slug}/master/photos` | Get all photos (couple) |
| GET | `/api/event/{slug}/master/folders` | Get folder structure (couple) |
| POST | `/api/event/{slug}/master/favorite` | Toggle favorite (couple) |
| GET | `/api/event/{slug}/master/favorites` | Get favorites list (couple) |
| GET | `/api/event/{slug}/photos/{photoId}/download` | Download original |

#### Analytics

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/events/{id}/analytics/summary` | Summary stats (views, downloads, guests) |
| GET | `/api/events/{id}/analytics/top-photos` | Most viewed/downloaded photos |
| GET | `/api/events/{id}/analytics/guests` | Guest list with metrics (paginated) |
| GET | `/api/events/{id}/analytics/guests/export` | CSV export of guest list |

#### Profile

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/profile` | Get photographer profile |
| PUT | `/api/profile` | Update profile |
| POST | `/api/profile/logo` | Upload studio logo |
| POST | `/api/profile/watermark` | Upload watermark image |
| GET | `/api/profile/storage` | Get storage usage |

---

## 11. Mock Data Strategy

Since the frontend is developed before the backend, all API interactions are mocked. Two approaches are used together:

### 11.1 Mock Service Worker (MSW)

MSW intercepts network requests at the service worker level, making it transparent to the application code. The frontend codebase doesn't need any conditional logic for mocks vs. real APIs.

```typescript
// mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  // Event list
  http.get('/api/events', () => {
    return HttpResponse.json({
      events: mockEvents,
      total: mockEvents.length,
    });
  }),

  // Photo list with pagination
  http.get('/api/events/:id/photos', ({ request, params }) => {
    const url = new URL(request.url);
    const offset = parseInt(url.searchParams.get('offset') || '0');
    const limit = parseInt(url.searchParams.get('limit') || '50');
    const folderId = url.searchParams.get('folderId');

    let photos = mockPhotos[params.id] || [];
    if (folderId) {
      photos = photos.filter(p => p.folderId === folderId);
    }

    return HttpResponse.json({
      photos: photos.slice(offset, offset + limit),
      total: photos.length,
      hasMore: offset + limit < photos.length,
      offset,
      limit,
    });
  }),

  // Guest selfie → simulated match
  http.post('/api/event/:slug/selfie', async () => {
    // Simulate processing delay
    await new Promise(resolve => setTimeout(resolve, 1500));
    return HttpResponse.json({
      matchedPhotoIds: mockMatchedPhotos,
      matchCount: mockMatchedPhotos.length,
    });
  }),

  // ... handlers for all other endpoints
];
```

```typescript
// mocks/browser.ts (client-side initialization)
import { setupWorker } from 'msw/browser';
import { handlers } from './handlers';

export const worker = setupWorker(...handlers);
```

```typescript
// app/layout.tsx (conditional initialization)
if (process.env.NEXT_PUBLIC_MOCK_API === 'true') {
  const { worker } = await import('@/mocks/browser');
  await worker.start({ onUnhandledRequest: 'warn' });
}
```

### 11.2 Mock Data Files

```typescript
// mocks/events.ts
export const mockEvents: Event[] = [
  {
    id: 'evt-001',
    name: 'Rahul & Priya Wedding',
    slug: 'rahul-priya-2026',
    date: { start: '2026-06-12', end: '2026-06-14' },
    type: 'wedding',
    status: 'ready',
    photoCount: 3450,
    folderCount: 12,
    guestCount: 186,
    coverImage: '/images/placeholder-photos/wedding-cover.jpg',
    createdAt: '2026-06-10T10:00:00Z',
  },
  // ... more events
];

// mocks/photos.ts
export const mockPhotos: Record<string, Photo[]> = {
  'evt-001': Array.from({ length: 200 }, (_, i) => ({
    id: `photo-${i}`,
    eventId: 'evt-001',
    folderId: ['folder-mehndi', 'folder-sangeet', 'folder-wedding'][i % 3],
    filename: `IMG_${4500 + i}.jpg`,
    webProxyUrl: `https://picsum.photos/seed/${i}/800/1200`, // placeholder
    originalUrl: null, // would be a presigned S3 URL in production
    width: 4000 + (i % 500),
    height: 6000 + (i % 500),
    fileSize: 15_000_000 + (i * 100_000),
    faceCount: Math.floor(Math.random() * 5),
    uploadedAt: '2026-06-15T10:00:00Z',
    views: Math.floor(Math.random() * 100),
    downloads: Math.floor(Math.random() * 30),
  })),
};
```

### 11.3 Placeholder Images

For realistic gallery rendering during frontend development:
- Use [Picsum Photos](https://picsum.photos/) URLs for random placeholder images in grids
- Store 10–20 actual wedding-style stock photos in `public/images/placeholder-photos/` for hero images and demos
- Mock upload progress with simulated timers (no actual file upload needed)

### 11.4 Mock-to-Real Transition

When the backend is ready, transitioning from mocks to real API:
1. Remove or set `NEXT_PUBLIC_MOCK_API=false` in environment
2. Set `NEXT_PUBLIC_API_BASE_URL` to the real backend URL
3. No code changes needed in components or hooks — they use the same API client and React Query hooks regardless of whether MSW is intercepting or the real backend is responding

---

## 12. Performance Optimization

### 12.1 Image Loading Strategy

Photo galleries are the heaviest part of the application. Performance is critical.

**Lazy Loading:**
- Photos below the fold are not loaded until they enter the viewport (Intersection Observer via `react-intersection-observer` or native `loading="lazy"`).
- The `next/image` component handles this automatically with its `loading="lazy"` default.

**Blur Placeholder:**
- While a photo loads, show a tiny blurred placeholder (blurhash or LQIP — Low Quality Image Placeholder).
- Backend generates a blurhash string (20-character string) per photo during the web-proxy generation step.
- Frontend renders the blurhash instantly, then fades in the actual image once loaded.

```typescript
// Usage with next/image
<Image
  src={photo.webProxyUrl}
  alt=""
  width={photo.width}
  height={photo.height}
  placeholder="blur"
  blurDataURL={photo.blurHash} // base64 tiny image or blurhash
  loading="lazy"
  sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
/>
```

**Virtualization:**
- For grids with 1,000+ photos, use `@tanstack/react-virtual` to render only the visible rows plus a small overscan buffer.
- This prevents DOM bloat (rendering 5,000 `<img>` tags kills performance).

**Progressive Loading:**
- Load thumbnail-quality images first (200px wide), then swap in full web-proxy images as the user scrolls slower or pauses.
- Implemented via `srcset` and `sizes` attributes.

### 12.2 Bundle Optimization

**Code Splitting:**
- Next.js App Router automatically code-splits per route.
- The dashboard bundle is separate from the guest/couple bundle — guests never download dashboard JavaScript.
- Heavy libraries (framer-motion, react-webcam, tus-js-client) are dynamically imported only on the pages that need them.

```typescript
// Dynamic import of heavy components
const SelfieCapture = dynamic(() => import('@/components/guest/selfie-capture'), {
  ssr: false, // camera access doesn't work on server
  loading: () => <LoadingSpinner />,
});

const UploadDropzone = dynamic(() => import('@/components/dashboard/upload-dropzone'), {
  ssr: false,
  loading: () => <LoadingSpinner />,
});
```

**Font Loading:**
- Self-host fonts (Inter, Plus Jakarta Sans) in `public/fonts/`.
- Use `font-display: swap` to avoid blocking render.
- Preload the primary font weight (400, 600) in the document head.

### 12.3 Performance Targets

| Metric | Target | Measurement |
|---|---|---|
| **Largest Contentful Paint (LCP)** | < 2.5s | First photo visible in gallery grid |
| **First Input Delay (FID)** | < 100ms | Time to respond to tap/click |
| **Cumulative Layout Shift (CLS)** | < 0.1 | No layout jumps as images load (achieved via aspect ratio placeholders) |
| **Time to Interactive (TTI)** | < 3.5s | Guest landing page fully interactive |
| **JS Bundle (guest route)** | < 150KB gzipped | Minimal JS for the guest flow |
| **JS Bundle (dashboard)** | < 300KB gzipped | More JS acceptable for the dashboard |

---

## 13. Testing Strategy

### 13.1 Testing Stack

| Type | Tool | Coverage Target |
|---|---|---|
| **Unit Tests** | Vitest | Utility functions, store logic, hooks |
| **Component Tests** | Vitest + React Testing Library | Individual components (forms, cards, grids) |
| **Integration Tests** | Vitest + MSW | Full page flows with mocked API |
| **E2E Tests** | Playwright | Critical user journeys (upload, guest flow) |
| **Visual Regression** | Playwright screenshots | Gallery grid, photo viewer, landing page |

### 13.2 Critical Test Paths

1. **Photographer registration + login flow** — End-to-end OTP verification
2. **Event creation + folder management** — Create, rename, delete, reorder folders
3. **Upload flow** — File selection, progress tracking, pause/resume, retry on failure
4. **Guest flow** — OTP auth → selfie capture → processing screen → personalized gallery → download
5. **Couple flow** — OTP auth → full gallery → folder navigation → favorite toggle → favorites view
6. **Responsive layouts** — Gallery grid at all breakpoints (mobile, tablet, desktop)

### 13.3 Testing with MSW

All integration and E2E tests use MSW handlers to mock the backend. This ensures:
- Tests are fast (no real network requests)
- Tests are deterministic (consistent mock data)
- Backend doesn't need to be running to test frontend
- Edge cases (empty states, errors, slow responses) can be easily simulated

```typescript
// Example: testing error state
http.get('/api/events', () => {
  return HttpResponse.json(
    { message: 'Internal Server Error' },
    { status: 500 }
  );
});
```

---

## 14. Accessibility & Internationalization

### 14.1 Accessibility (a11y) Standards

Target: **WCAG 2.1 Level AA**

**Key Requirements:**
- All interactive elements are keyboard navigable (Tab, Enter, Escape, Arrow keys)
- Photo viewer supports keyboard navigation (left/right arrows, Escape to close)
- All images have appropriate `alt` text (empty string for decorative photos in grids; meaningful alt for UI images)
- Color contrast ratios meet AA standards (4.5:1 for normal text, 3:1 for large text)
- Form fields have associated labels
- Error messages are linked to form fields via `aria-describedby`
- Focus is managed correctly in modals (trapped focus, return focus on close)
- Screen reader announcements for dynamic content (upload progress, processing status)

### 14.2 Internationalization (i18n)

Phase 1 is English-only. However, the codebase is structured for future i18n:
- All user-facing strings are centralized in constant files (not hardcoded in JSX)
- Date and number formatting uses `Intl` APIs
- RTL layout considerations are deferred to Phase 2 (if needed)

---

## 15. Build & Deployment

### 15.1 Environment Configuration

```env
# .env.local (development)
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_MOCK_API=true
NEXT_PUBLIC_APP_URL=http://localhost:3000

# .env.production
NEXT_PUBLIC_API_BASE_URL=https://api.platform.com
NEXT_PUBLIC_MOCK_API=false
NEXT_PUBLIC_APP_URL=https://platform.com
NEXT_PUBLIC_CDN_URL=https://cdn.platform.com
```

### 15.2 Build Pipeline

```bash
# Development
pnpm dev            # Next.js dev server with hot reload + MSW

# Production build
pnpm build          # Next.js production build (SSR + static)
pnpm start          # Start production server

# Quality checks
pnpm lint           # ESLint
pnpm type-check     # TypeScript type checking
pnpm test           # Vitest unit + integration tests
pnpm test:e2e       # Playwright E2E tests
```

### 15.3 Deployment Target

The Next.js application is deployed as a Docker container (or serverless via Vercel/AWS Amplify depending on infrastructure decisions).

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

### 15.4 Development Workflow

1. **Local Development:** `pnpm dev` starts the Next.js dev server. MSW intercepts all API calls with mock data. No backend needed.
2. **Backend Integration:** When the backend is ready, set `NEXT_PUBLIC_MOCK_API=false` and `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`. Frontend code is unchanged; only the environment variable switches the data source.
3. **Staging:** Deploy to a staging environment with the real backend. Run E2E tests against staging.
4. **Production:** Deploy to production with all environment variables pointed at production services.

---

*End of Frontend Component Document v1.0*
