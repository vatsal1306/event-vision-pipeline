# Backend, ML, and Infrastructure stories

Frontend stories: `docs/stories/frontend/00-index.md`.

Work **backend** before **ML**. **Infra v2:** S3 + IAM in the cheap account; one EC2 Compose stack in the compute account. ML does **not** deploy on that EC2.

**Always read:**

- Root `AGENTS.md`
- `backend/AGENTS.md` for Python/FastAPI/ML
- `docs/component_backend.md`, `docs/component_ai_ml.md`, `docs/component_infrastructure.md`
- `docs/PRD.md` Phase 1 only

**Hard constraints**

- Python **3.10 only** (`from __future__ import annotations` allowed). No 3.11+ syntax.
- Thin route handlers and thin Celery tasks. Business logic in services.
- No secrets in git. Config via `.env` on laptop and on the app EC2 (not SSM).
- Phase 1: no billing, WhatsApp, custom domains, multi-photographer roles, video, real-time camera-to-cloud, **no GPU on the app server**.
- Storage AWS account ≈ $60/year (S3). Compute = one **m6i.xlarge** in **ap-south-1**.

## Backend (`docs/stories/backend/`)

| ID     | Story                                         | Depends on                 | Status |
|--------|-----------------------------------------------|----------------------------|--------|
| BE-001 | FastAPI scaffold, uv, Compose, health         | —                          | Done   |
| BE-002 | Config, exceptions, logging, CORS             | BE-001                     | Done   |
| BE-003 | SQLAlchemy models and Alembic                 | BE-002                     | Done   |
| BE-004 | Security, JWT, photographer auth + OTP        | BE-003                     | Done   |
| BE-005 | Event CRUD and slugs                          | BE-004                     |
| BE-006 | Nested folders                                | BE-005                     |
| BE-007 | Photos list, move, delete, download URL       | BE-006, BE-008             |
| BE-008 | S3 storage service                            | BE-002                     |
| BE-009 | tusd webhook and photo ingest                 | BE-007                     |
| BE-010 | Web-proxy, HEIC, watermark Celery             | BE-009                     |
| BE-011 | Share links and download toggle               | BE-005                     |
| BE-012 | Guest and couple OTP sessions                 | BE-005                     |
| BE-013 | Guest selfie + matched photos API             | BE-012; stub until ML host |
| BE-014 | Couple gallery and favorites                  | BE-012                     |
| BE-015 | Analytics and CSV export                      | BE-012                     |
| BE-016 | Profile, logo, watermark, storage quota       | BE-008                     |
| BE-017 | Notifications (log OTP; email optional no-op) | BE-010                     |
| BE-018 | Archival scheduler                            | BE-008, BE-017             |
| BE-019 | Rate limits and HTTP security                 | BE-004                     |
| BE-020 | Backend automated tests                       | BE-004 onward              |

## ML (`docs/stories/ml/`)

| ID     | Story                                 | Depends on                          | Status |
|--------|---------------------------------------|-------------------------------------|--------|
| ML-001 | ML package, MLConfig, ModelRegistry   | BE-001                              |
| ML-002 | SCRFD detection and ArcFace crop      | ML-001                              |
| ML-003 | Blur and YPR quality filters          | ML-001                              |
| ML-004 | InsightFace R100 + MobileFaceNet      | ML-002                              |
| ML-005 | Incremental DBSCAN + agglomerative    | ML-001                              |
| ML-006 | ClusterManager pgvector persistence   | BE-003, ML-005                      |
| ML-007 | Selfie match and basic liveness       | ML-002, ML-004, ML-006              |
| ML-008 | FaceService and Celery face tasks     | BE-010, ML-007 — **not on app EC2** |
| ML-009 | Batch embedding path (future ML host) | ML-008                              |
| ML-010 | ML tests and fixtures                 | ML-008                              |

## Infra (`docs/stories/infra/`)

| ID      | Story                                   | Depends on       | Status |
|---------|-----------------------------------------|------------------|--------|
| INF-001 | Terraform state (storage account)       | —                | Done   |
| INF-002 | S3 media buckets                        | INF-001          | Done   |
| INF-003 | IAM user for app EC2                    | INF-002          | Done   |
| INF-004 | EC2 m6i.xlarge Ubuntu ap-south-1        | —                | Done   |
| INF-005 | Compose + Caddy + tusd upload hardening | INF-004          | Done   |
| INF-006 | GH tests + SSH deploy                   | INF-005          | Done   |
| INF-007 | Postgres dump to S3                     | INF-002, INF-005 |
| INF-008 | Disk/SSH/S3 spend checks                | INF-005          |

## Suggested batches

1. Local: BE-001 → BE-012, BE-014–BE-016; stub BE-013
2. Uploads: BE-008 → BE-010 (CPU Celery only)
3. Infra: INF-002–INF-005 on the two AWS accounts
4. ML: code later; **separate host** — do not install CUDA on m6i.xlarge
