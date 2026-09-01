# Backend, ML, and Infrastructure stories

Frontend stories: `docs/stories/frontend/00-index.md`.

Work **backend** before **ML** (ML is imported by Celery workers). **Infra** can start in parallel after local Docker Compose exists (BE-001), but production AWS should wait until the API image builds.

**Always read:**

- Root `AGENTS.md`
- `backend/AGENTS.md` for Python/FastAPI/ML
- `docs/component_backend.md`, `docs/component_ai_ml.md`, `docs/component_infrastructure.md`
- `docs/PRD.md` Phase 1 only

**Hard constraints**

- Python **3.10 only** (`from __future__ import annotations` allowed). No 3.11+ syntax.
- Thin route handlers and thin Celery tasks. Business logic in services.
- No secrets in git. Config via env / SSM.
- Phase 1: no billing, WhatsApp, custom domains, multi-photographer roles, video, real-time camera-to-cloud.

## Backend (`docs/stories/backend/`)

| ID | Story | Depends on | Status |
|----|--------|------------|-------|
| BE-001 | FastAPI scaffold, uv, Compose, health | — |
| BE-002 | Config, exceptions, logging, CORS | BE-001 |
| BE-003 | SQLAlchemy models and Alembic | BE-002 |
| BE-004 | Security, JWT, photographer auth + OTP | BE-003 |
| BE-005 | Event CRUD and slugs | BE-004 |
| BE-006 | Nested folders | BE-005 |
| BE-007 | Photos list, move, delete, download URL | BE-006, BE-008 |
| BE-008 | S3 storage service | BE-002 |
| BE-009 | tusd webhook and photo ingest | BE-007 |
| BE-010 | Web-proxy, HEIC, watermark Celery | BE-009 |
| BE-011 | Share links and download toggle | BE-005 |
| BE-012 | Guest and couple OTP sessions | BE-005 |
| BE-013 | Guest selfie + matched photos API | BE-012, ML-008 |
| BE-014 | Couple gallery and favorites | BE-012 |
| BE-015 | Analytics and CSV export | BE-012 |
| BE-016 | Profile, logo, watermark, storage quota | BE-008 |
| BE-017 | Email/SMS notifications | BE-010 |
| BE-018 | Archival scheduler | BE-008, BE-017 |
| BE-019 | Rate limits and HTTP security | BE-004 |
| BE-020 | Backend automated tests | BE-004 onward |

## ML (`docs/stories/ml/`)

| ID | Story | Depends on | Status |
|----|--------|------------|-------|
| ML-001 | ML package, MLConfig, ModelRegistry | BE-001 |
| ML-002 | SCRFD detection and ArcFace crop | ML-001 |
| ML-003 | Blur and YPR quality filters | ML-001 |
| ML-004 | InsightFace R100 + MobileFaceNet | ML-002 |
| ML-005 | Incremental DBSCAN + agglomerative | ML-001 |
| ML-006 | ClusterManager pgvector persistence | BE-003, ML-005 |
| ML-007 | Selfie match and basic liveness | ML-002, ML-004, ML-006 |
| ML-008 | FaceService and Celery face tasks | BE-010, ML-007 |
| ML-009 | Batch GPU embedding path | ML-008 |
| ML-010 | ML tests and fixtures | ML-008 |

## Infra (`docs/stories/infra/`)

| ID | Story | Depends on | Status |
|----|--------|------------|-------|
| INF-001 | Terraform state backend | — |
| INF-002 | VPC, subnets, NAT, security groups | INF-001 |
| INF-003 | S3 buckets, encryption, lifecycle | INF-002 |
| INF-004 | RDS PostgreSQL 16 + pgvector | INF-002 |
| INF-005 | ElastiCache Redis | INF-002 |
| INF-006 | Dockerfiles and ECR | BE-001 |
| INF-007 | ECS cluster, FastAPI + Next.js services | INF-006, INF-004, INF-005 |
| INF-008 | ALB, ACM, Route 53 | INF-007 |
| INF-009 | CloudFront CDN | INF-003, INF-008 |
| INF-010 | GPU Spot workers and queues | INF-007, ML-008 |
| INF-011 | GitHub Actions CI/CD + migrations | INF-006 |
| INF-012 | CloudWatch, Sentry, budgets | INF-007 |
| INF-013 | IAM, SSM secrets, least privilege | INF-007 |
| INF-014 | Staging environment | INF-007–INF-013 |
| INF-015 | Production-hardening checklist | INF-014 |

## Suggested batches

1. Local platform: BE-001 → BE-012, BE-014–BE-016 (stub face match until ML-008)
2. Media pipeline: BE-008 → BE-010, BE-017–BE-018
3. ML: ML-001 → ML-010 then BE-013
4. Cloud: INF-001 onward once images exist
