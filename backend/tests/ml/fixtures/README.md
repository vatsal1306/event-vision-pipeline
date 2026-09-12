# ML test image fixtures

These images are used by ML unit and integration tests. They are **not** wedding
or client photos.

| File | Source | Notes |
|------|--------|-------|
| `no_face.jpg` | Generated solid-color image | No faces expected |
| `blank_image.jpg` | Generated solid-color image | Distinct from `no_face.jpg`; liveness + no-face |
| `single_face.jpg` | `backend/models/cvlface_DFA_mobilenet/input.png` | Exactly 1 face |
| `group_photo.jpg` | Openverse scrape | 4 faces detected by SCRFD |
| `blurry_face.jpg` | Gaussian blur of `single_face.jpg` | Blur-filter tests |
| `profile_face.jpg` | Affine-warped `single_face.jpg` | Synthetic high-yaw pose (not a photographic profile) |
| `synthetic_crops/face_a.jpg` | Center 112×112 of `single_face.jpg` | Pre-cropped ArcFace size |
| `synthetic_crops/face_b.jpg` | Hue-shifted / flipped `face_a` | Synthetic variation |
| `synthetic_crops/face_c.jpg` | Noisy `face_a` | Synthetic variation |

Do not replace these with private event photos.
