# AI Photo Sharing Platform — Master Product Requirements Document

> **Version:** 1.0  
> **Last Updated:** September 2026  
> **Status:** Phase 1 — Active Development  
> **Confidentiality:** Internal

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Vision & Mission](#2-product-vision--mission)
3. [Market Analysis & Competitive Landscape](#3-market-analysis--competitive-landscape)
4. [Target Users & Personas](#4-target-users--personas)
5. [Phase 1 — Complete Feature Specification](#5-phase-1--complete-feature-specification)
6. [Phase 2 — Planned Enhancements](#6-phase-2--planned-enhancements)
7. [User Flows & Journeys](#7-user-flows--journeys)
8. [Information Architecture](#8-information-architecture)
9. [Business Model & Pricing Strategy](#9-business-model--pricing-strategy)
10. [Go-To-Market Strategy](#10-go-to-market-strategy)
11. [Brand Identity & Positioning](#11-brand-identity--positioning)
12. [Success Metrics & KPIs](#12-success-metrics--kpis)
13. [Product Roadmap](#13-product-roadmap)
14. [Risks & Mitigations](#14-risks--mitigations)
15. [Glossary](#15-glossary)

---

## 1. Executive Summary

### The Problem

Professional event and wedding photographers face a broken delivery workflow. After capturing 5,000–20,000 photos across multi-day events, they resort to Google Drive links, Dropbox folders, or physical USBs — methods that are slow, unorganized, and frustrating for everyone involved. Guests must scroll through thousands of photos to find themselves. Photographers lose hours to manual sorting. The immediacy of the wedding moment — when guests are most likely to share on social media — is lost entirely.

### The Solution

An AI-powered photo delivery platform that uses facial recognition to instantly deliver personalized photo galleries to every guest via a simple shareable link. Photographers upload once; the platform handles face detection, clustering, and per-guest gallery creation automatically. Guests authenticate with their phone number, take a selfie, and receive only the photos they appear in — loaded fast via compressed web-optimized previews, with original high-resolution files available on demand for download.

### Core Differentiators

| Differentiator | Our Approach | Industry Status Quo |
|---|---|---|
| **Zero app friction** | Browser-based PWA; no app store visit required | KwikPic pushes app downloads; Kamero requires native app for full features |
| **Predictable pricing** | Reusable storage; no per-photo credit drain | KwikPic charges 2.5x credits per high-res download; storage is non-reusable |
| **Instant delivery illusion** | Pre-indexed face embeddings during upload; millisecond vector search at guest scan time | Competitors process on-demand, causing visible wait times |
| **Full-resolution originals** | Guests download the actual original file (10–30MB) | KwikPic delivers ~1MB compressed by default, ~1.6MB on "high-res" |
| **Dual-resolution architecture** | Compressed web-proxies for browsing; originals for download — optimizes both UX and cloud cost | Most platforms serve a single resolution tier |
| **Built-in lead capture** | Every guest's name and verified phone number is captured automatically | Requires separate tools or manual collection |

### Key Metrics Targets (First 12 Months)

- 500+ events processed
- 50+ active photographer accounts
- < 3 second average gallery load time for guests
- > 95% face match accuracy in standard lighting conditions
- < 5% churn rate among paying photographers after first 3 events

---

## 2. Product Vision & Mission

### Vision

To become the default infrastructure layer between a photographer's camera and every guest's phone — invisible, instant, and effortless.

### Mission

Eliminate the manual, fragmented photo delivery workflow for event photographers by providing an AI-first platform that automates face-based photo organization and delivers personalized galleries with zero friction for end users.

### Design Philosophy

1. **Invisible Technology:** The best software gets out of the way. The platform should feel like the photographer's own premium service, not a third-party tool.
2. **Speed as a Feature:** Every interaction is optimized for perceived speed. Pre-indexing during upload, compressed previews for instant grid loading, progressive image rendering.
3. **Mobile-First, Desktop-Capable:** Guest experience is designed phone-first. Photographer experience is designed for large screens with a drag-and-drop workflow.
4. **Photographer's Brand First:** The platform's identity recedes behind the photographer's watermark, studio name, and professional presentation.
5. **Cost Transparency:** No credit systems, no hidden multipliers, no per-photo charges. Storage is reusable and pricing is predictable.

---

## 3. Market Analysis & Competitive Landscape

### Market Size

The global photo sharing market was valued at USD 5,059.4 million in 2025, projected to reach USD 9,032.0 million by 2036 at a 5.5% CAGR (Future Market Insights). Within this, event photo delivery platforms represent a fast-growing sub-segment driven by AI adoption and the decline of physical album culture.

The Indian wedding photography market is particularly large — India hosts approximately 10 million weddings annually, with the professional photography services market growing at 15–20% year-over-year as smartphone penetration drives demand for digital delivery.

### Competitive Landscape (Detailed)

#### Tier 1: Direct Competitors (AI Face Recognition + Event Delivery, India-focused)

| Platform | Strengths | Weaknesses | Pricing Model |
|---|---|---|---|
| **KwikPic** | 500K+ events; 99.9% claimed face accuracy; 50+ gallery themes; portfolio websites; strong brand in India | Credit-based pricing (2.5x for high-res); non-reusable storage; hidden reset fees (₹2,500 after first free reset); pushes app download for full experience; no team collaboration; outdated UI complaints; poor low-light face recognition | Annual subscription + credit-based (₹3,490–₹29,990/yr) |
| **Cam-Shot AI** | Full workflow (upload→AI→QR→gallery→sell); AI highlights/reels; photo selling built-in; white-label website ($600) and app ($600); clean UI | Face scan limits per tier (50–5,000 per event); relatively new (smaller user base); tiered storage caps | Monthly subscription ($15–$32/mo) |
| **FotoOwl** | Camera-to-cloud "Beam" hardware; AI-generated personalized guest reels ("ReelIt"); photo selling (10% commission); generous free "Creator Pass" tier; 55+ countries | Beam requires extra hardware; 10% commission on photo sales; less established in India specifically | Tiered subscriptions + commission |
| **Kamero** | White-label branded iOS/Android apps (₹49,999); Kam-Sync FTP (up to 10 cameras); guest uploads; photo shortlisting; 70+ branded apps live | Pay-per-event photo bucket model (100–10K photos); exceeding bucket forces upgrade; native app focus can be limiting | Photo bucket packs per event |
| **Samaro** | WhatsApp bot for delivery + guest media collection; Netflix-style video galleries; digital invitations with RSVP; engagement-focused | Some features in early access; event-based plan caps on guests/media; less focus on face recognition accuracy | Event-based bundles |
| **FTPix** | Real-time camera WiFi upload (phone + PC app); unlimited events on Studio plan; digital invitations + RSVP; portfolio builder | Newer entrant; smaller user base | Unlimited events subscription |
| **TurtlePic** | Reusable storage (delete event, space returns); transparent pricing; full-res delivery | Smaller feature set compared to KwikPic/Cam-Shot | Storage-based subscription |
| **AccioPix** | WhatsApp-first delivery; no guest app download; homomorphic encryption for face data | Limited gallery customization; early-stage | Per-event pricing |

#### Tier 2: Global Competitors (Gallery/Delivery Platforms, not AI-first)

| Platform | Focus | Relevance |
|---|---|---|
| **Pixieset** | Gallery delivery + print sales; 250K+ photographers globally | No AI face recognition; manual gallery creation |
| **ShootProof** | Gallery + studio management; 0% commission on sales | No face matching; focused on proofing/selling |
| **Pic-Time** | Automated marketing engine; AI print upsells; 55% YoY growth | Limited face recognition; strong in Western markets |
| **SnapSeek** | Corporate events; web-app only; one-way curated galleries | Pay-per-photo credits; not wedding-focused |
| **Framekit** | Branded event gallery delivery on custom domain | No AI face recognition; delivery-only |

### Competitive Gaps We Exploit

1. **App download friction**: KwikPic and Kamero require or heavily push native app downloads. Older wedding guests, guests with full phone storage, and international attendees drop off at this step. Our PWA approach eliminates this entirely.

2. **Predatory credit/storage models**: KwikPic's 2.5x credit multiplier for high-res, non-reusable storage, and hidden ₹2,500 reset fees create anxiety and distrust. Our reusable storage model with transparent pricing directly addresses the most vocal photographer complaint in the market.

3. **Compressed delivery masquerading as "high-res"**: KwikPic delivers ~1MB files by default. Our dual-resolution model shows compressed web-proxies for fast browsing but delivers the actual full-resolution original (10–30MB) on download — a genuinely superior end product.

4. **No team collaboration**: Multi-photographer events (standard for Indian weddings with 2–5 shooters) are poorly served. While Phase 1 supports single-photographer events, our architecture is designed for multi-photographer expansion in Phase 2.

5. **Missing studio workflow features**: Most competitors are either pure delivery tools (no business features) or full studio management platforms (bloated for photographers who just want fast delivery). We focus on doing delivery exceptionally well with built-in lead capture as the key business tool.

---

## 4. Target Users & Personas

### Primary User: The Photographer (Buyer)

#### Persona 1: The Solo Wedding Photographer

- **Profile:** 25–40 years old, shoots 30–60 weddings per year, works alone or with one assistant, earns ₹50K–₹2L per wedding.
- **Tech Comfort:** Uses Lightroom/Photoshop daily, comfortable with cloud tools, has a strong Instagram presence.
- **Current Workflow:** Shoots event → edits in Lightroom (2–5 days) → uploads to Google Drive → sends link via WhatsApp → guests struggle to find their photos → photographer gets few social media tags.
- **Pain Points:**
  - Spends 3–5 hours per event manually sorting photos for individual families.
  - Google Drive links look unprofessional and don't carry their branding.
  - Misses the social media momentum window — guests share phone selfies instead of professional photos because delivery is too slow.
  - No way to capture guest contact information for future marketing.
- **What They Want:** "Upload once, done. Let the AI sort it. My clients and their guests should see their photos within minutes, and my brand should be everywhere."

#### Persona 2: The Studio Owner

- **Profile:** 35–55 years old, runs a team of 3–10 photographers, handles 100–200+ events per year, premium pricing (₹2L–₹10L per wedding).
- **Tech Comfort:** Delegates tech tasks to assistants; needs an interface simple enough for junior team members.
- **Current Workflow:** Multiple photographers shoot → photos consolidated on NAS/external drives → studio team edits → uploads to KwikPic or similar → manages credits and storage quotas.
- **Pain Points:**
  - Credit-based pricing creates budget unpredictability at scale.
  - No team collaboration — one account per photographer, no shared event management.
  - Storage fills up; deleting old events is irreversible or incurs fees.
  - Wants to differentiate from competitors by offering "instant AI delivery" as a premium service to clients.
- **What They Want:** "Predictable monthly costs, my team can upload without confusion, and my clients think this is my own software."

### Secondary User: The Couple (VIP End User)

#### Persona 3: The Bride/Groom

- **Profile:** 25–35 years old, smartphone-native, active on Instagram/WhatsApp, emotionally invested in wedding photos.
- **Interaction Model:** Receives a "Master Link" from the photographer granting access to the complete event gallery, organized by event day/function.
- **Pain Points:**
  - Currently receives a Google Drive folder with 5,000 unsorted photos.
  - Wants to see Mehndi photos separately from Wedding photos.
  - Wants to mark their favorite shots easily.
  - Wants to share the gallery with guests but with some control over what guests see.
- **What They Want:** "A beautiful gallery organized by event, easy to browse on my phone, and a way to share it with all our guests effortlessly."

### Tertiary User: The Guest (End User at Scale)

#### Persona 4: The Wedding Guest

- **Profile:** Wide age range (18–70+), varying tech comfort, uses WhatsApp as primary communication tool, attends 1–10 weddings per year.
- **Interaction Model:** Receives a shareable link from the couple or photographer via WhatsApp. Opens in browser, enters name + phone number, verifies via OTP, takes a selfie, and receives their personalized gallery.
- **Pain Points:**
  - Doesn't want to download an app for a one-time use.
  - Doesn't want to scroll through 5,000 photos to find themselves.
  - Wants to download their photos in full quality without compression.
  - Older family members struggle with complex interfaces.
- **What They Want:** "Click the link, see my photos, download the good ones. That's it."

---

## 5. Phase 1 — Complete Feature Specification

### 5.1 Photographer Studio Dashboard

#### 5.1.1 Authentication & Account Management

- **Registration:** Email + password + mobile phone number. Email verification via link. Mobile verification via OTP.
- **Login:** Email + password. Optional "Remember Me" with persistent session.
- **Password Recovery:** Standard email-based reset flow.
- **Profile Management:** Studio name, logo upload, contact information, watermark image upload.
- **Session Management:** Secure token-based sessions with configurable expiry.

#### 5.1.2 Event Creation & Management

- **Create Event:**
  - Event name (e.g., "Rahul & Priya Wedding")
  - Event date(s) — support for date ranges (multi-day events)
  - Event type (Wedding, Corporate, Birthday, Other) — for internal analytics; does not change functionality
  - Event description (optional)
  - Cover image (optional, selectable from uploaded photos later)
- **Event States:**
  - `Draft` — Created, no photos uploaded yet
  - `Uploading` — Photos are being uploaded/processed
  - `Processing` — AI face detection and clustering in progress
  - `Ready` — All processing complete; gallery shareable
  - `Archived` — Past the 2-month window; data moved to archival storage
- **Event List View:** Sortable by date, status, name. Search by event name. Shows photo count, guest count, and status badge per event.
- **Event Detail View:** Full management interface for a single event (folders, photos, settings, analytics, share links).

#### 5.1.3 Folder & Gallery Management

- **Hierarchical Folder Structure:** Photographers can create nested folders within an event to organize photos by function/day.
  - Example: `Rahul & Priya Wedding / Mehndi / Bride Getting Ready`
  - Example: `Rahul & Priya Wedding / Wedding Day / Ceremony`
  - Example: `Rahul & Priya Wedding / Reception`
- **Folder Operations:** Create, rename, reorder (drag-and-drop), delete (with confirmation).
- **Move Photos:** Drag-and-drop photos between folders. Multi-select support.
- **Bulk Operations:** Select multiple photos → delete, move to folder.
- **Photo Metadata Display:** Filename, resolution, file size, upload timestamp, number of faces detected.

#### 5.1.4 Photo Upload System

- **Browser-Based Uploader:** Drag-and-drop zone + file picker. Supports deeply nested folder uploads that preserve the folder structure.
- **Supported Formats:** JPEG, PNG, HEIC/HEIF (auto-converted to JPEG on upload), TIFF, WebP.
- **Chunked Resumable Uploads:** Each file is split into chunks (5MB each) and uploaded independently. If the connection drops, upload resumes from the last successful chunk — no re-upload of the entire file.
- **Parallel Uploads:** Up to 6 files uploaded concurrently (browser connection limit). Upload queue manages the remaining files.
- **Upload Progress:** Per-file progress bars + overall progress indicator. Shows upload speed, estimated time remaining, and completed/total file count.
- **Upload Capacity:** Must handle 15,000–20,000 files per event (10–30MB each, totaling 150–600GB per event).
- **Background Processing Trigger:** As each file uploads, it enters the processing queue for:
  1. Dual-resolution web-proxy generation (compressed ~500KB WebP/JPEG)
  2. Face detection and embedding extraction
  3. Watermark application to the web-proxy version
- **Error Handling:** Failed uploads are retried automatically (up to 3 times). Persistently failed files are flagged in the UI with retry option.
- **Upload State Persistence:** If the browser tab is closed mid-upload, reopening the event shows the upload state with completed files checked off and pending files ready to resume.

#### 5.1.5 Dual-Resolution Processing Pipeline

- **Web-Proxy Generation:** Every uploaded photo is processed into a lightweight web-optimized version:
  - Format: WebP (JPEG fallback for older browsers)
  - Target size: ~300–500KB
  - Resolution: Longest edge capped at 2048px
  - Quality: Perceptually optimized (SSIM > 0.95 compared to original)
  - Watermark: Photographer's uploaded watermark applied at bottom-right, semi-transparent
- **Original Preservation:** The full-resolution original file is stored as-is in cost-optimized cold storage. No modifications, no compression. This is what guests receive on download.
- **Storage Tiering:**
  - Hot storage: Web-proxies (frequently accessed for gallery browsing)
  - Cold/warm storage: Originals (accessed only on explicit download request)

#### 5.1.6 Watermark Configuration

- **Upload:** Photographer uploads their watermark image (PNG with transparency recommended).
- **Placement:** Bottom-right corner, semi-transparent overlay.
- **Application:** Auto-applied to all web-proxy images. Original high-res files are delivered without watermark.
- **Preview:** Photographer can preview the watermark appearance on a sample photo before applying to all.

#### 5.1.7 Link Generation & Distribution

- **Master Link (For the Couple):**
  - Unrestricted access to the complete gallery across all folders.
  - Couple can browse all photos, mark favorites, and download originals.
  - The couple can share this link with anyone (it acts as a "view all" pass).
  - URL format: `platform.com/event/{event-slug}/master`
- **Guest Link (For Attendees):**
  - Restricted portal — guests must authenticate and take a selfie.
  - After face matching, guests see only photos they appear in.
  - Guests can browse their matched photos and download originals.
  - URL format: `platform.com/event/{event-slug}/guest`
- **Link Controls:**
  - Enable/disable download of original high-res files (toggle, defaults to enabled).
  - Deactivate a link (revokes access without deleting the event).

#### 5.1.8 Lead Capture & Guest Analytics

- **Automatic Lead Capture:** Every guest who authenticates via the Guest Link has their name and verified mobile number stored.
- **Lead Dashboard:** A dedicated section within the event showing:
  - Guest name
  - Mobile number (verified via OTP)
  - Timestamp of first visit
  - Number of photos matched
  - Number of photos downloaded
- **Export:** CSV download of the complete guest list with all captured data points.
- **Analytics Metrics (Simple):**
  - Total gallery views (unique visitors)
  - Downloads per photo (which photos are most downloaded)
  - Most viewed photos (ranked by view count)

#### 5.1.9 Notification System (Phase 1)

- **Processing Complete Notification:** When all photos in an event have finished AI processing (face detection, embedding extraction, clustering), the photographer receives:
  - Email notification with event name, photo count, and a direct link to the event dashboard.
  - SMS notification (optional, configurable in account settings) with a brief summary and link.

#### 5.1.10 Data Retention & Archival

- **Active Period:** Event data (photos, embeddings, guest data) remains in active/hot storage for **2 months** from the event date or last upload, whichever is later.
- **Archival Warning:** At 7 days and 1 day before archival, the photographer receives email/SMS reminders.
- **Manual Deletion:** Photographer can delete an event at any time during the active period. Storage is freed and returned to their quota.
- **Automatic Archival:** After 2 months, if the photographer takes no action:
  - All event data is moved to archival (deep cold) storage.
  - Archived events are no longer accessible to guests via the share link (link shows an "Event archived" page).
  - Archived data **counts toward the photographer's storage quota** (this incentivizes cleanup).
  - Photographer can restore an archived event (subject to a processing delay for data retrieval from cold storage).
- **Permanent Deletion:** Photographer can permanently delete archived events to free storage quota.

### 5.2 Couple's Experience (Master Link)

#### 5.2.1 Authentication

- **Entry Point:** Couple clicks the Master Link received from the photographer (typically via WhatsApp).
- **Authentication:** Name + mobile number + OTP verification.
- **Session Persistence:** Once verified, the couple remains logged in via local storage/cookies tied to their verified mobile number. Closing the browser and returning later does not require re-authentication.

#### 5.2.2 Full Gallery Access

- **Complete Gallery:** The couple sees every photo in the event, organized by the photographer's folder structure (Mehndi, Sangeet, Wedding, etc.).
- **Navigation:** Folder-based sidebar or tab navigation to switch between event sections.
- **Photo Grid:** Responsive masonry grid layout with smooth scrolling. Lazy-loaded images using the compressed web-proxy versions for speed.
- **Photo Viewer:** Tap/click to open full-screen viewer with swipe navigation, pinch-to-zoom, and download button.
- **Download:**
  - Individual photo download: Fetches the original high-resolution file from cold storage.
  - Download indicator: Shows a brief loading state while the original is retrieved.

#### 5.2.3 Favorites

- **Mark Favorite:** Tap a heart/star icon on any photo to mark it as a favorite.
- **Favorites Folder:** A separate "Favorites" section accessible from the navigation that shows all marked photos across all folders.
- **Persistence:** Favorites are stored server-side, tied to the couple's verified session, so they persist across devices and sessions.
- **No Sharing:** Favorites are a private feature for the couple's own reference; there is no separate sharing mechanism for the favorites folder in Phase 1.

### 5.3 Guest Experience (Guest Link / PWA)

#### 5.3.1 Entry & Authentication

1. Guest receives the Guest Link via WhatsApp (forwarded by the couple or shared by the photographer).
2. Guest taps the link — opens instantly in their mobile browser (no app download, no app store redirect).
3. **Landing Page:** Branded page showing the event name, photographer's studio name/logo, and a "View Your Photos" call-to-action.
4. **Authentication:** Guest enters their **Name** and **Mobile Number**. System sends an OTP to the mobile number. Guest enters the OTP to verify.
5. Lead capture happens at this step — the verified name and phone number are stored for the photographer's analytics.

#### 5.3.2 Selfie Capture & Face Matching

1. **Camera Access:** Post-OTP, the browser requests camera access (front-facing camera).
2. **Selfie UI:** A guided selfie capture screen with:
   - Face outline overlay to help the guest position their face correctly.
   - Guidance text: "Position your face within the circle. Look straight at the camera."
   - Basic quality checks: Ensure a face is detected in the frame before allowing capture. Prevent blurry captures.
   - The goal is to capture the guest's face properly for maximum face match accuracy, not to act as a security restriction.
3. **Capture:** Guest taps the capture button. The selfie is sent to the backend for embedding extraction and vector search against the pre-indexed event embeddings.
4. **Processing State:** While matching is in progress, the guest sees a branded loading screen:
   > *"We are gathering your memories. This might take a moment. You can close this page and come back later — just log in with your mobile number."*
   - **Technical reality:** Because event photos are pre-indexed during the photographer's upload phase, the vector search against the guest's selfie embedding takes milliseconds. The loading screen serves as a UX buffer for server load spikes during high-concurrency periods (e.g., 200 guests scanning within 30 minutes at a reception).

#### 5.3.3 Personalized Gallery

1. Guest is redirected to a personalized photo grid showing **only** the photos they appear in, across all event folders.
2. **Gallery Layout:** Responsive masonry grid, optimized for mobile viewports (primarily iOS Safari and Android Chrome).
3. **Image Quality:** Displayed images are the compressed, watermarked web-proxies (~300–500KB each) for lightning-fast scrolling and minimal data consumption.
4. **Photo Viewer:** Tap to open full-screen viewer with swipe navigation and pinch-to-zoom.
5. **Folder Grouping (Optional):** If the photographer organized photos into folders, matched photos can optionally be grouped by folder ("Your Mehndi Photos", "Your Wedding Photos").

#### 5.3.4 Download

- **Individual Download:** Tap "Download" on any photo. The system retrieves the **original full-resolution file** (10–30MB) from cold storage and delivers it to the guest's device.
- **Download Indicator:** A loading spinner/progress indicator while the original is fetched (cold storage retrieval may take 1–5 seconds).
- **Download Control:** The photographer can globally toggle "Allow Download" on/off for the event. If disabled, guests can view but not download.
- **No Bulk Download in Phase 1:** Guests download individual photos. Bulk/zip download is a Phase 2 consideration.

#### 5.3.5 Session & Return Visits

- **Session Persistence:** Guest session is stored locally (cookies/local storage). Returning to the same link on the same device does not require re-authentication or re-selfie.
- **Cross-Device:** If a guest accesses from a different device, they re-authenticate with phone number + OTP. The system recognizes their existing face match and serves the same gallery without requiring a new selfie.

### 5.4 Gallery Design & Presentation

- **Single Default Gallery Theme:** One beautiful, modern, minimalist gallery design optimized for photo viewing.
  - Dark background (black or near-black) to maximize photo vibrancy.
  - Ample whitespace between photos.
  - Responsive masonry grid that adapts to screen size.
  - Smooth animations and transitions.
  - Typography: Clean, modern sans-serif.
- **Photographer Branding Elements:**
  - Studio name displayed in the gallery header.
  - Studio logo (if uploaded) in the header/corner.
  - Watermark on all web-proxy images (bottom-right, semi-transparent).
- **Performance Targets:**
  - Initial gallery load: < 3 seconds on 4G connection.
  - Image grid scrolling: 60fps, no jank.
  - Photo viewer open: < 200ms.

---

## 6. Phase 2 — Planned Enhancements

Phase 2 features are documented here for completeness and future planning. Phase 1 scope is locked and will not be expanded.

### 6.1 Real-Time Event Delivery

- **Camera-to-Cloud Upload:** Enable photographers to upload photos during the event (via WiFi tethering or mobile app) so guests can see their photos while the event is still happening.
- **Live Gallery:** Guests scanning the QR code at the venue see photos appearing in real-time as the photographer shoots.

### 6.2 Multi-Photographer / Team Collaboration

- **Role-Based Access:** Owner, Editor (can upload/manage), Viewer (read-only) roles per event.
- **Multiple Uploaders:** Multiple photographers can upload to the same event simultaneously.
- **Team Management:** Studio owner can manage team members, assign events, and control permissions.

### 6.3 Couple's Expanded Controls

- **Photo Moderation:** Couple can hide/unhide specific photos before the gallery is opened to guests.
- **Gallery Approval Workflow:** Couple reviews and approves the gallery before it goes live.
- **"VIP Faces" Pinning:** AI groups photos by frequently appearing faces (parents, bridal party) for easy review.

### 6.4 WhatsApp Integration

- **WhatsApp Notifications:** Automated messages to guests when their photos are ready ("Your photos from Rahul & Priya's Wedding are ready! Tap here to view.").
- **WhatsApp Bot:** Guests can interact via WhatsApp to receive their gallery link without visiting the website.
- **Broadcast Lists:** Photographer can send the Guest Link to all captured phone numbers via WhatsApp Business API.

### 6.5 Video Support

- **Video Uploads:** Support for video files (MP4, MOV) alongside photos.
- **Highlight Reels:** AI-generated short highlight reels from event photos (slideshow with music).
- **Video Streaming:** Adaptive bitrate streaming for video playback within the gallery.

### 6.6 Advanced Gallery Features

- **Multiple Gallery Themes:** Selectable gallery designs (10–20 themes) with different layouts, color schemes, and typography.
- **Social Sharing:** One-click sharing to Instagram Stories, WhatsApp Status, with photographer's branding/watermark baked into the shared image.
- **Guest Uploads:** Allow guests to upload their own phone photos to a community gallery section (separate from the curated photographer gallery).
- **Bulk Download:** Zip download of all matched photos for guests; full event download for couples.

### 6.7 Business & Monetization Features

- **Photo Selling:** Photographers can set prices for photo downloads; guests pay to access full-resolution files.
- **Print Integration:** Partnership with print labs for direct photo-to-print ordering within the gallery.
- **Subscription Billing:** Built-in subscription management with payment gateway integration (Razorpay/Stripe).

### 6.8 Advanced AI Features

- **Improved Face Matching:** Multi-angle matching, better handling of heavy makeup/jewelry changes between events, child face matching across multi-day events.
- **Object/Scene Detection:** Auto-tag photos by content (group shot, couple portrait, food, décor) for smarter gallery organization.
- **Duplicate Detection:** Identify and flag near-duplicate photos to help photographers curate.

### 6.9 Infrastructure Scaling

- **Desktop Upload App:** Native desktop application (Tauri/Electron) for ultra-reliable bulk uploads with filesystem access and background processing.
- **Global CDN Expansion:** Multi-region CDN for international guest access.
- **Offline PWA Capabilities:** Cache thumbnails for offline browsing; queue downloads for when connectivity improves.

---

## 7. User Flows & Journeys

### 7.1 Photographer: End-to-End Event Delivery Flow

```
                     ┌─────────────────────┐
                     │  Photographer edits  │
                     │ photos in Lightroom  │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │   Logs into Studio   │
                     │     Dashboard        │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │   Creates new Event  │
                     │  (name, date, type)  │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Creates folder      │
                     │  structure           │
                     │  (Mehndi, Sangeet,   │
                     │   Wedding, etc.)     │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Bulk uploads photos │
                     │  to respective       │
                     │  folders (drag-drop) │
                     │  [Chunked/Resumable] │
                     └──────────┬──────────┘
                                │
                    ┌───────────┴───────────┐
                    │   BACKGROUND PROCESSING │
                    │                         │
                    │  • Web-proxy generation │
                    │  • Watermark application│
                    │  • Face detection       │
                    │  • Embedding extraction │
                    │  • Face clustering      │
                    └───────────┬─────────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Receives "Processing │
                     │  Complete" email/SMS │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │  Reviews gallery     │
                     │  in dashboard        │
                     └──────────┬──────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
          ┌──────────────┐       ┌──────────────┐
          │ Copies Master │       │ Copies Guest  │
          │ Link → sends  │       │ Link → sends  │
          │ to Couple     │       │ to Couple for │
          │ via WhatsApp  │       │ distribution  │
          └──────────────┘       └──────────────┘
                                        │
                                        ▼
                              ┌──────────────────┐
                              │ Monitors Lead     │
                              │ Capture Dashboard │
                              │ as guests log in  │
                              └──────────────────┘
```

### 7.2 Couple: Gallery Access Flow

```
  Receives Master Link from Photographer (WhatsApp)
                        │
                        ▼
              Opens link in browser
                        │
                        ▼
           Enters Name + Phone + OTP
                        │
                        ▼
         ┌──────────────────────────┐
         │    Full Gallery Access    │
         │                          │
         │  Browse by folder:       │
         │  • Mehndi (450 photos)   │
         │  • Sangeet (680 photos)  │
         │  • Wedding (1200 photos) │
         │  • Reception (900 photos)│
         └──────────┬───────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
   Browse &    Mark photos   Download
   view all    as Favorites  originals
        │           │
        │           ▼
        │    View Favorites
        │    folder later
        │
        ▼
   Share Guest Link
   with wedding guests
   via WhatsApp
```

### 7.3 Guest: Photo Discovery Flow

```
  Receives Guest Link from Couple/Photographer (WhatsApp)
                        │
                        ▼
        Opens link in mobile browser (instant, no app)
                        │
                        ▼
              ┌────────────────────┐
              │   Branded Landing  │
              │   Page with event  │
              │   name & studio    │
              │   branding         │
              └────────┬───────────┘
                       │
                       ▼
              Enters Name + Phone
                       │
                       ▼
              Receives OTP → Verifies
              [Lead captured at this step]
                       │
                       ▼
              ┌────────────────────┐
              │  Selfie Capture    │
              │  (face guide       │
              │   overlay, basic   │
              │   quality check)   │
              └────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │  "Gathering your   │
              │   memories..."     │
              │  Loading screen    │
              │  [AI matching in   │
              │   background,      │
              │   typically <2s]   │
              └────────┬───────────┘
                       │
                       ▼
              ┌────────────────────┐
              │  Personalized      │
              │  Gallery           │
              │  (only photos      │
              │   they appear in)  │
              │                    │
              │  Compressed        │
              │  watermarked       │
              │  previews for      │
              │  fast browsing     │
              └────────┬───────────┘
                       │
                       ▼
              Tap "Download" on any photo
                       │
                       ▼
              Original full-res file
              delivered (10-30MB)
```

---

## 8. Information Architecture

### 8.1 Data Model Overview

```
Photographer (Account)
 │
 ├── Profile (studio name, logo, watermark, contact info)
 │
 ├── Event 1
 │    ├── Metadata (name, date, type, status)
 │    ├── Settings (download toggle, link status)
 │    ├── Folders
 │    │    ├── Mehndi
 │    │    │    └── Photos (original + web-proxy + embeddings)
 │    │    ├── Sangeet
 │    │    │    └── Photos
 │    │    └── Wedding
 │    │         └── Photos
 │    ├── Face Clusters (grouped embeddings → person identities)
 │    ├── Master Link → Couple Access
 │    │    └── Couple Session (name, phone, favorites)
 │    ├── Guest Link → Guest Access
 │    │    └── Guest Sessions
 │    │         ├── Guest 1 (name, phone, selfie embedding, matched photos)
 │    │         ├── Guest 2
 │    │         └── Guest N
 │    └── Analytics (views, downloads, lead list)
 │
 ├── Event 2
 │    └── ...
 │
 └── Storage Quota (used / total, including archived events)
```

### 8.2 URL Structure

| URL | Purpose | Access |
|---|---|---|
| `/dashboard` | Photographer studio dashboard | Authenticated photographer |
| `/dashboard/events` | Event list | Authenticated photographer |
| `/dashboard/events/{id}` | Event detail/management | Authenticated photographer |
| `/dashboard/events/{id}/upload` | Upload interface | Authenticated photographer |
| `/dashboard/events/{id}/analytics` | Analytics & lead capture | Authenticated photographer |
| `/dashboard/profile` | Profile & watermark settings | Authenticated photographer |
| `/event/{slug}/master` | Couple's master gallery | Authenticated couple (OTP) |
| `/event/{slug}/guest` | Guest authentication & gallery | Authenticated guest (OTP + selfie) |

---

## 9. Business Model & Pricing Strategy

### 9.1 Pricing Philosophy

Pricing must be:
- **Predictable:** No per-photo credits. No surprise multipliers for high-res.
- **Transparent:** What you see is what you pay. No hidden fees for storage resets.
- **Reusable:** Deleting an event frees up storage that can be reused for new events.

### 9.2 Pricing Model Options (To Be Finalized)

Two models under consideration. Final selection depends on cloud cost analysis after initial development:

#### Option A: Storage-Based Subscription

| Tier | Storage | Price (Monthly) | Best For |
|---|---|---|---|
| Starter | 200GB | ₹999/mo | Solo photographers (3–5 events active) |
| Professional | 1TB | ₹2,499/mo | Active photographers (10–15 events active) |
| Studio | 5TB | ₹6,999/mo | Studios with high volume (30+ events active) |

- All tiers include: Unlimited events, unlimited AI processing, unlimited guests, full-res downloads.
- Storage is reusable: delete/archive old events to free space.

#### Option B: Event-Based Flat Rate

| Tier | Price Per Event | Includes |
|---|---|---|
| Standard | ₹999/event | Up to 5,000 photos, unlimited guests |
| Premium | ₹1,999/event | Up to 15,000 photos, unlimited guests |
| Mega | ₹3,499/event | Up to 25,000 photos, unlimited guests |

- No subscriptions; pay only when you have events.
- Includes 2-month active storage per event.

#### The Hook (Both Models)

**First 2 events are 100% free** (up to 3,000 photos each). This is critical because photographers will not switch their workflow until they experience the "Wow" factor from their own clients and guests.

### 9.3 Cost Optimization Strategy

The dual-resolution architecture is the key cost lever:
- **Web-proxies (~500KB each):** Served from hot storage via CDN. This is 95%+ of all data requests (gallery browsing, scrolling). Cheap per-GB egress.
- **Originals (10–30MB each):** Stored in cold/infrequent-access storage. Only accessed on explicit download. Much lower storage cost per GB, and downloads are infrequent relative to views.
- **Face embeddings:** Tiny (512-dimensional float vector, ~2KB per face). Negligible storage cost even at millions of faces.

This architecture means a 10,000-photo event consumes approximately:
- Hot storage: ~5GB (web-proxies)
- Cold storage: ~100–300GB (originals)
- Vector storage: ~20MB (embeddings, assuming 1.5 faces per photo on average)

---

## 10. Go-To-Market Strategy

### 10.1 Launch Strategy

#### Pre-Launch (Month 1–2)

1. **Beta with 5–10 photographers:** Hand-pick photographers from personal network and Instagram outreach in one city (e.g., Ahmedabad, Delhi, or Mumbai). Offer completely free usage for 3 months in exchange for feedback and case studies.
2. **Dogfood the product:** Use the platform for personal events (birthdays, family gatherings) to stress-test the flow end-to-end.
3. **Collect testimonials:** After each beta event, collect feedback from both the photographer and at least 5 guests. Focus on the "wow moment" when guests see only their photos.

#### Soft Launch (Month 3–4)

1. **Free tier announcement:** Open the platform with the "First 2 events free" offer. Target Instagram hashtags: `#WeddingPhotographer`, `#IndianWeddingPhotography`, `#{City}WeddingPhotographer`.
2. **Demo events:** At photography meetups or workshops, take attendee photos, create an event, and let them experience the AI face matching live. This is the ultimate "show, don't tell."
3. **Content marketing:** Publish comparison articles ("Google Drive vs. AI Photo Delivery: Why Your Clients Deserve Better") targeting photographers who currently use DIY solutions.

#### Scale (Month 5–12)

1. **Referral program:** Existing photographers get 1 free event for every referral that completes their first paid event.
2. **Partnership with album printers/gear rentals:** These businesses already have the photographer's trust. Small affiliate commission per referral.
3. **Instagram engagement:** Systematic engagement with photographer communities. Comment on work, share tips, then pitch the free trial via DM.

### 10.2 Acquisition Channels (Ranked by Priority)

1. **Direct Instagram outreach** — Highest conversion potential. Photographers live on Instagram and respond to genuine engagement.
2. **Photography community WhatsApp groups** — Many cities have active photographer WhatsApp groups. A well-placed demo video goes viral quickly.
3. **Wedding expos & photography workshops** — In-person demos are unbeatable for this product. Let people experience it.
4. **SEO content marketing** — Long-term play. Target "how to deliver wedding photos faster", "best photo delivery platform for photographers India".
5. **YouTube tutorials** — Short tutorials on "How to deliver 10,000 photos in 5 minutes" attract organic photographer traffic.

### 10.3 Retention Strategy

- **Onboarding support:** For any photographer's first event, offer to walk them through the upload process via a video call or screen-share.
- **Post-event report:** After each event, auto-generate a summary email showing stats (X guests viewed, Y photos downloaded, Z leads captured) to reinforce value.
- **Printable QR templates (Phase 2):** When real-time delivery launches, provide free printable QR code templates for wedding table placement.

---

## 11. Brand Identity & Positioning

### 11.1 Positioning Statement

**For** professional event photographers **who** need to deliver thousands of photos to hundreds of guests quickly, **our platform** is an AI-powered photo delivery engine **that** uses facial recognition to instantly create personalized guest galleries, **unlike** Google Drive folders, credit-based competitors, or app-download-required platforms, **because** it delivers zero-friction, full-resolution, branded photo galleries through a simple browser link.

### 11.2 Positioning Axis

We are **not** a cloud storage product. We are not a studio management platform. We are not a photo editing tool.

We are a **"Client Experience Engine"** — the technology that makes a photographer look like a premium, tech-forward studio. The platform saves them hours of manual work while making their clients and guests feel delighted.

### 11.3 Brand Personality

| Attribute | Expression |
|---|---|
| **Professional** | B2B language; "Elevate your studio", "Delight your clients" |
| **Invisible** | The platform recedes behind the photographer's brand |
| **Fast** | Speed is a feature; "Guests get their photos before the party ends" (Phase 2) |
| **Reliable** | "Every photo, every guest, every time" |
| **Simple** | "Upload once. AI does the rest." |

### 11.4 Visual Design Language

- **Gallery UI:** Dark background (photo-forward), minimalist, ample whitespace, smooth animations.
- **Dashboard UI:** Clean, modern, light theme with dark mode option. Focus on clarity over decoration.
- **Typography:** Modern sans-serif (Inter, Plus Jakarta Sans, or similar).
- **Color Palette:** Neutral base (dark grays, whites) with a single accent color for CTAs and highlights.

---

## 12. Success Metrics & KPIs

### 12.1 North Star Metric

**Number of guest gallery views per month** — This metric captures both photographer adoption (more events = more guests) and guest satisfaction (return visits, shares to other guests).

### 12.2 Phase 1 KPIs

#### Acquisition & Growth

| Metric | Target (Month 6) | Target (Month 12) |
|---|---|---|
| Registered photographers | 100 | 500 |
| Active photographers (≥1 event/month) | 30 | 150 |
| Total events created | 200 | 1,500 |
| Total photos processed | 1M | 10M |
| Guest gallery views (monthly) | 5,000 | 50,000 |

#### Product Quality

| Metric | Target |
|---|---|
| Gallery load time (P95) | < 3 seconds on 4G |
| Face match accuracy | > 95% (standard lighting) |
| Upload success rate | > 99% (with resume) |
| Processing time (per 1,000 photos) | < 15 minutes |
| System uptime | > 99.5% |

#### Engagement

| Metric | Target |
|---|---|
| Guest-to-download conversion | > 40% of guests download ≥1 photo |
| Average photos matched per guest | > 15 |
| Photographer repeat rate | > 70% use platform for 2nd event |
| Photographer churn (monthly) | < 5% |

#### Business

| Metric | Target |
|---|---|
| Free-to-paid conversion | > 25% of free trial photographers convert |
| Average revenue per photographer (monthly) | ₹1,500+ |
| Customer acquisition cost (CAC) | < ₹2,000 |
| Lifetime value (LTV) / CAC ratio | > 3:1 |

---

## 13. Product Roadmap

### Phase 1 — Foundation (Months 1–4)

| Month | Focus | Deliverables |
|---|---|---|
| Month 1 | Frontend foundation | Photographer dashboard (auth, event CRUD, folder management, upload UI with mock data), Guest PWA (auth, selfie, gallery with mock data) |
| Month 2 | Backend core | API server, database, auth system, event/folder CRUD, chunked upload pipeline, dual-resolution processing, watermark engine |
| Month 3 | AI/ML pipeline | Face detection integration (PicSee SCRFD), embedding extraction, clustering, selfie-to-gallery matching, liveness detection |
| Month 4 | Integration & polish | Frontend ↔ Backend integration, end-to-end testing, analytics dashboard, notification system, infrastructure hardening, beta launch preparation |

### Phase 2 — Expansion (Months 5–10)

| Quarter | Focus | Key Features |
|---|---|---|
| Q1 (M5–M7) | Engagement & distribution | WhatsApp integration, real-time camera-to-cloud delivery, social sharing, multiple gallery themes |
| Q2 (M8–M10) | Scale & monetization | Multi-photographer collaboration, video support, photo selling, subscription billing, advanced AI features |

---

## 14. Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **Face recognition accuracy < 90% in Indian wedding conditions** (heavy makeup, lighting changes, veils) | Medium | High | PicSee pipeline already handles this; incremental clustering + quality filtering reduces false matches; err on the side of more matches (accept some false positives) |
| **Upload failures at scale** (15K+ files, unstable connections) | Medium | High | Chunked resumable uploads with automatic retry; upload state persistence across browser sessions |
| **High cloud storage costs eat into margins** | Medium | High | Dual-resolution architecture; aggressive cold storage tiering; auto-archival after 2 months; cost analysis before pricing finalization |
| **Photographers don't switch from Google Drive** ("it's free and works") | High | Medium | Free trial eliminates cost objection; focus on guest experience as the selling point — "your guests see their photos in seconds, not hours"; post-event analytics showing engagement prove value |
| **Guest drop-off at OTP step** (too much friction) | Low | Medium | OTP is fast (10-second delivery); clearly communicate value ("Enter your number to see your photos"); minimal fields (name + phone only) |
| **Privacy/legal concerns with facial recognition** | Medium | Medium | Clear consent at selfie step; data retention policy with auto-archival; no biometric data sold or shared; embed privacy policy in guest flow; comply with India's Digital Personal Data Protection Act |
| **Single developer bottleneck** | High | Medium | Phased development reduces risk; frontend-first approach allows early user feedback; use managed cloud services to reduce ops burden |
| **Competitor response** (KwikPic cuts prices or copies features) | Medium | Low | Speed to market matters; our PWA approach and full-res delivery are structural advantages, not easy feature copies; focus on execution quality over feature count |

---

## 15. Glossary

| Term | Definition |
|---|---|
| **Web-Proxy** | A compressed, web-optimized version of a photo (~300–500KB) used for gallery browsing. Watermarked with the photographer's branding. |
| **Original / Full-Res** | The unmodified, full-resolution photo file (10–30MB) as uploaded by the photographer. Delivered to users on download. |
| **Dual-Resolution Architecture** | The system's approach of maintaining two copies of every photo — a web-proxy for fast viewing and the original for download — to optimize both performance and cost. |
| **Face Embedding** | A 512-dimensional numerical vector representing the unique features of a face, extracted by the AI model. Used for face matching via cosine similarity. |
| **Face Cluster** | A group of face embeddings that the AI determines belong to the same person across multiple photos. |
| **Pre-Indexing** | The process of extracting face embeddings from all event photos during the photographer's upload phase, before any guest visits. This enables near-instant face matching when a guest takes their selfie. |
| **Master Link** | The URL shared with the couple, granting unrestricted access to the complete event gallery. |
| **Guest Link** | The URL shared with wedding guests, requiring OTP authentication and selfie capture before showing a personalized gallery of photos the guest appears in. |
| **Lead Capture** | The automatic collection of guest names and verified phone numbers when they authenticate to view their photos. This data is valuable for photographers as a marketing tool. |
| **PWA (Progressive Web App)** | A web application that provides a native-app-like experience (offline caching, home screen install, smooth animations) without requiring an app store download. |
| **Cold Storage** | Low-cost cloud storage tier optimized for infrequently accessed data. Used for original full-resolution files. |
| **Hot Storage** | High-performance cloud storage tier optimized for frequently accessed data. Used for web-proxies served to gallery viewers. |
| **Chunked Upload** | An upload method where large files are split into smaller pieces (chunks) and uploaded independently, enabling resumability if the connection drops. |
| **OTP (One-Time Password)** | A temporary numeric code sent via SMS to verify a user's mobile phone number. |
| **Liveness Detection** | A check during selfie capture to ensure the image is of a live person (not a photograph of a photograph). Basic implementation in Phase 1. |
| **Archival** | The process of moving event data from active (hot/warm) storage to deep cold storage after the 2-month active period. Archived data remains but is not accessible to guests. |

---

*End of Master PRD — AI Photo Sharing Platform v1.0*
