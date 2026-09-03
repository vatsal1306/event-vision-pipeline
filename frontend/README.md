# SpotMe Frontend

The frontend for the **SpotMe** event photo pipeline.

## Stack
- Next.js 14 (App Router)
- React 18
- TypeScript
- Tailwind CSS
- custom Shadcn UI (Radix UI)
- Framer Motion

## Design System

This project uses a bespoke, Mastercard-inspired design system documented in `DESIGN.md`. It aggressively overrides standard utility styles to create a warm, editorial, "magazine-like" feel.

**Key Design Tokens:**
- **Canvas Cream** (`#F3F0EE`): Primary background color. Never use pure white for the page background.
- **Ink Black** (`#141413`): Primary text and button fill color.
- **Signal Orange** (`#CF4500`): Used strictly for consent, compliance, and destructive actions.
- **Border Radii**: 
  - `stadium` (40px) for hero cards and large containers.
  - `pill` (999px) for full rounding (nav bars, chips).
  - `button` (20px) for primary actions.

**Typography:**
- Uses **Sofia Sans**.
- `font-[450]` is the standard body weight.
- `font-medium` (500) with `-tracking-[0.02em]` for headings and buttons.

## Setup & Running Locally

1. Install dependencies:
   ```bash
   pnpm install
   ```

2. Run the development server:
   ```bash
   pnpm dev
   ```

3. Open [http://localhost:3000](http://localhost:3000) in your browser.

## Component Library

We use Radix UI primitives installed via Shadcn UI, but they are heavily customized in `src/components/ui/` to enforce the 20px pill shapes and tight typography. Do not install raw Shadcn components without adapting their Tailwind classes to match `DESIGN.md`.

## Mock API

Since the frontend is developed before the backend is fully available, we use MSW (Mock Service Worker) to intercept API requests and return mock data.

To enable the mock API, set the following environment variable in `.env.local`:
```
NEXT_PUBLIC_MOCK_API=true
```

**Testing credentials:**
- When prompted for an OTP in the mocked guest authentication flow, use `123456`.

## Developed Features

### FE-011: Event Details & Photo Grid
- Integrated dynamic `FolderTree` and virtualized `PhotoGrid`.
- Responsive layout using `ResizeObserver`.
- MSW handlers for dynamic folder selection and photo retrieval.

### FE-012: Resumable Uploads
- Chunked, resumable file and folder uploads.
- Managed by `UploadManager` communicating with `tus-js-client`.
- Supports drag-and-drop file/folder uploads via `react-dropzone`.
- State managed by Zustand in `src/stores/upload-store.ts`.
- Integrated target folder creation logic (automatically creating subfolders matching dragged local directories).

### FE-013: Event Analytics
- Added AnalyticsOverview with summary metrics (Total Guests, Views, Downloads).
- Implemented LeadTable with sortable, paginated guest data.
- Built client-side CSV export functionality for guest lead capture data.
- Integrated into the existing unified Event Dashboard tabs.
