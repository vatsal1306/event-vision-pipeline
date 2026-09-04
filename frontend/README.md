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

### FE-014: Share Links & Settings
- Implemented `LinkGenerator` component in the Event Dashboard Share tab.
- Generates and allows copying of Master and Guest links using the event slug.
- Added toggle controls for Master link, Guest link, and "Allow original downloads" setting.
- Integrated with MSW to mock event link toggling and global settings updates.

### FE-015: Photographer Profile & Branding
- Built the Photographer Profile page (`/dashboard/profile`).
- Added editable form for Studio Name, Email, and Phone with Zod validation.
- Implemented Logo and Watermark upload features with immediate local preview generation (`URL.createObjectURL`).
- Added `WatermarkPreview` component to visualize how the watermark will appear overlaid on photos.
- Updated the global sidebar and profile page to display real mocked storage usage limits (progress bar and human-readable bytes).

### FE-016: Shared Gallery Grid & Viewer
- Fully integrated the guest/couple gallery UI primitives (`GalleryGrid`, `PhotoViewer`, `FolderNav`, `GalleryHeader`).
- `GalleryGrid` now supports responsive column layouts corresponding to 'guest', 'couple', and 'dashboard' contexts.
- Added a dedicated throwaway demo page at `/gallery-demo` to showcase the dark-theme gallery experience with masonry layouts, virtualization, and the full-screen photo lightbox viewer.

### FE-017: Couple Master Link & Auth
- Implemented the public-facing "Master Link" page at `/event/[slug]/master` for couples to view their complete gallery.
- Added an OTP-based authentication flow (Name + Phone -> OTP) before the gallery is accessible. You can use the mock OTP `123456` to test.
- The authentication session is persisted locally on the device using a lightweight `zustand` store with `persist` middleware.
- Refined the `GalleryGrid` layout for couples by enforcing a `'couple'` mode which sets a comfortable, expansive column structure up to 6 columns.
- The gallery integrates the `FolderNav` allowing the couple to browse their event's photos across all folders in a sleek dark theme.

### FE-018: Couple Favorites
- Added the ability for couples to "favorite" photos within the master gallery.
- Created `useFavorites` and `useToggleFavorite` React Query hooks to fetch favorites and optimistically update the UI, enabling instant feedback on toggling.
- Added a heart icon toggle to the `GalleryGrid` thumbnails (on hover) and the `PhotoViewer` header.
- Implemented a `FavoritesFab` floating action button that displays the favorite count and toggles the view to show only favorite photos across all folders.
- Mocked the favorites API state in MSW to test the flow end-to-end.

### FE-019: Guest Link & Personalized Gallery
- Implemented the end-to-end PWA flow for wedding guests via the `/event/[slug]/guest` link.
- Created a robust state machine utilizing `useGuestAuthStore` (zustand persist) to guide users through Auth -> OTP -> Selfie Capture -> Processing -> Personalized Gallery.
- Integrated `react-webcam` to capture the guest's selfie seamlessly on both mobile and desktop browsers with an intuitive face guide overlay.
- Displayed a branded processing state simulating backend face matching.
- Developed a personalized photo grid greeting the guest by name and displaying only the photos they appear in. Return visits bypass the selfie step entirely if they've already been matched.
