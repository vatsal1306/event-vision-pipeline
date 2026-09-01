# FE-019 — Guest link: OTP, selfie, processing, matched gallery

**Type:** Feature  
**Depends on:** FE-016  
**Area:** `frontend/src/app/event/[slug]/guest/`, `frontend/src/components/guest/`

## Goal

End-to-end guest PWA flow: branded landing → name + phone + OTP (lead capture) → guided selfie (quality, not security theatre) → processing copy → personalized grid of matched photos → original download. Return visit: OTP, skip selfie if already matched.

## References

- `docs/component_frontend.md` §7 entire
- `docs/PRD.md` §5.3
- API: guest auth, `POST selfie` multipart, `GET guest/photos`
- Client face hint: MediaPipe or face-api.js optional; capture disabled until a face is framed
- `react-webcam`, dynamic `ssr: false`

## Create / edit

- `guest/page.tsx` (multi-step)
- `otp-form.tsx`, `selfie-capture.tsx`, `face-guide-overlay.tsx`, `processing-screen.tsx`, `personalized-gallery.tsx`
- Privacy line: selfie not stored permanently (copy from spec)
- Empty match: retake selfie CTA

## Requirements

- Camera denied: explain how to enable
- Processing screen copy must match PRD (can close and come back)
- Greeting: “Hi {name}! We found {n} photos…”
- No WhatsApp, no QR, no social share buttons

## Acceptance

- [ ] Full flow works on mock (selfie POST → delay → photos)
- [ ] Returning session skips selfie when mock says so
- [ ] Inactive guest link handled
- [ ] Mobile-first layout
