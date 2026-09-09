# ML test image fixtures

These images are used by SCRFD integration tests. They are **not** wedding or client photos.

| File              | Source                                           | Notes                     |
|-------------------|--------------------------------------------------|---------------------------|
| `no_face.jpg`     | Generated solid-color image                      | No faces expected         |
| `single_face.jpg` | `backend/models/cvlface_DFA_mobilenet/input.png` | Exactly 1 face            |
| `group_photo.jpg` | Openverse scrape                                 | 4 faces detected by SCRFD |

Do not replace these with private event photos.
