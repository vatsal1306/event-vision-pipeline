# Component Document: Backend & API

> **Version:** 1.0  
> **Last Updated:** September 2026  
> **Scope:** REST API, Business Logic, Database, Authentication, Upload Pipeline, Async Processing  
> **Development Order:** This is Component 2 — built after the frontend, before AI/ML pipeline.

---

## Table of Contents

1. [Overview & Technology Choices](#1-overview--technology-choices)
2. [Architecture](#2-architecture)
3. [Project Structure](#3-project-structure)
4. [Database Design](#4-database-design)
5. [Authentication & Authorization](#5-authentication--authorization)
6. [API Specification](#6-api-specification)
7. [Upload Pipeline](#7-upload-pipeline)
8. [Dual-Resolution Processing Engine](#8-dual-resolution-processing-engine)
9. [Watermark Engine](#9-watermark-engine)
10. [Notification Service](#10-notification-service)
11. [Analytics Service](#11-analytics-service)
12. [Data Retention & Archival](#12-data-retention--archival)
13. [Error Handling & Logging](#13-error-handling--logging)
14. [Configuration Management](#14-configuration-management)
15. [Testing Strategy](#15-testing-strategy)
16. [API Rate Limiting & Security](#16-api-rate-limiting--security)

---

## 1. Overview & Technology Choices

### 1.1 Framework: Python FastAPI

**Why FastAPI:**
- **Async-native:** Built on ASGI with full `async/await` support, critical for I/O-heavy operations (S3 uploads, database queries, external API calls).
- **Auto-generated OpenAPI docs:** Swagger UI and ReDoc available out of the box — accelerates frontend-backend integration.
- **Pydantic validation:** Request/response models are validated and serialized automatically. Tight integration with Python type hints.
- **High performance:** One of the fastest Python frameworks (comparable to Node.js/Go for I/O workloads).
- **AI/ML integration:** Python ecosystem enables seamless integration with the PicSee face recognition pipeline (InsightFace, PyTorch, NumPy).
- **Dependency injection:** FastAPI's `Depends()` system provides clean, testable dependency management for database sessions, auth, services.

### 1.2 Core Dependencies

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | latest | Web framework |
| `uvicorn[standard]` | latest | ASGI server (production: gunicorn + uvicorn workers) |
| `pydantic[email]` | v2 | Data validation, settings management |
| `sqlalchemy[asyncio]` | 2.x | Async ORM and database toolkit |
| `asyncpg` | latest | Async PostgreSQL driver |
| `alembic` | latest | Database migrations |
| `python-jose[cryptography]` | latest | JWT token creation and validation |
| `passlib[bcrypt]` | latest | Password hashing |
| `boto3` | latest | AWS S3 interactions |
| `aioboto3` | latest | Async AWS S3 interactions |
| `celery[redis]` | latest | Distributed task queue for background processing |
| `redis` | latest | Celery broker + result backend + caching |
| `pillow` | latest | Image manipulation (resize, watermark, format conversion) |
| `pillow-heif` | latest | HEIC/HEIF image support |
| `httpx` | latest | Async HTTP client (for OTP service, notifications) |
| `python-multipart` | latest | File upload parsing |
| `tusd` | (external) | Tus protocol upload server (Go binary, runs as sidecar) |
| `structlog` | latest | Structured JSON logging |
| `sentry-sdk[fastapi]` | latest | Error tracking |

### 1.3 Language & Tooling

- **Language:** Python 3.10 (use `from __future__ import annotations` for modern type hint syntax)
- **Package Manager:** `uv` (fast, reliable dependency management and virtual environments)
- **Linting:** `ruff` (replaces flake8, isort, pycodestyle — single tool, extremely fast)
- **Formatting:** `ruff format` (replaces black)
- **Type Checking:** `mypy` (strict mode)
- **Pre-commit:** `pre-commit` hooks running ruff + mypy

---

## 2. Architecture

### 2.1 High-Level Architecture

```
                    ┌─────────────────────────────────────────┐
                    │           Next.js Frontend               │
                    │     (Photographer / Guest / Couple)       │
                    └──────────────┬──────────────────────────┘
                                   │ HTTPS
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │     Caddy on EC2 (TLS, reverse proxy)     │
                    └───────┬──────────────────┬──────────────┘
                            │                  │
                    ┌───────▼──────┐   ┌───────▼──────┐
                    │   FastAPI     │   │   tusd        │
                    │   Application │   │   Upload      │
                    │   Server      │   │   Server      │
                    │   (REST API)  │   │   (tus proto)  │
                    └───────┬──────┘   └───────┬──────┘
                            │                  │
                    ┌───────┴──────────────────┴──────┐
                    │                                  │
              ┌─────▼─────┐  ┌─────────┐  ┌──────────▼─────┐
              │ PostgreSQL │  │  Redis   │  │  AWS S3         │
              │ (pgvector) │  │ (cache + │  │ (photos +       │
              │            │  │  broker) │  │  assets)        │
              └────────────┘  └────┬────┘  └────────────────┘
                                   │
                          ┌────────▼────────┐
                          │  Celery Workers  │
                          │  (background     │
                          │   processing)    │
                          │                  │
                          │  • Resize/proxy  │
                          │  • Watermark     │
                          │  • Notifications │
                          │  • Face tasks: stub until ML host │
                          └─────────────────┘
```

### 2.2 Component Responsibilities

| Component | Responsibility |
|---|---|
| **FastAPI Application** | REST API, authentication, business logic, database operations, S3 presigned URL generation |
| **tusd Upload Server** | Handles tus protocol chunked/resumable uploads directly to S3. Sends webhook to FastAPI on upload completion. |
| **PostgreSQL + pgvector** | Runs in Docker on the app EC2 (not RDS) |
| **Redis** | Docker on the app EC2 (not ElastiCache). OTP may be logged in dev instead of SMS |
| **Celery Workers** | CPU only: resize, watermark. Do not load InsightFace on this box |
| **AWS S3** | Separate storage account, same region `ap-south-1`. tusd uploads originals here |

### 2.3 Request Flow Patterns

**Synchronous (API Request → Response):**
- Authentication (login, OTP verify)
- Event CRUD operations
- Folder management
- Photo listing (paginated)
- Analytics queries
- Link generation

**Asynchronous (API Request → Queue → Worker → Callback):**
- Face embedding extraction and clustering (**later ML host**; stub on app server)
- Original file download (presigned S3)
- Notification delivery (log / optional email)
- Data archival

---

## 3. Project Structure

```
backend/
├── alembic/                          # Database migrations
│   ├── versions/                     # Migration files
│   ├── env.py
│   └── alembic.ini
│
├── app/
│   ├── __init__.py
│   ├── main.py                       # FastAPI app factory, middleware, startup/shutdown
│   ├── config.py                     # Pydantic settings (env vars)
│   │
│   ├── api/                          # API route handlers
│   │   ├── __init__.py
│   │   ├── deps.py                   # Shared dependencies (db session, current user)
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # Aggregated v1 router
│   │   │   ├── auth.py               # Auth endpoints
│   │   │   ├── events.py             # Event endpoints
│   │   │   ├── folders.py            # Folder endpoints
│   │   │   ├── photos.py             # Photo endpoints
│   │   │   ├── upload.py             # Upload webhook handler
│   │   │   ├── sharing.py            # Link & sharing endpoints
│   │   │   ├── guest.py              # Guest-facing endpoints
│   │   │   ├── couple.py             # Couple-facing endpoints
│   │   │   ├── analytics.py          # Analytics endpoints
│   │   │   └── profile.py            # Profile & settings endpoints
│   │   └── health.py                 # Health check endpoint
│   │
│   ├── models/                       # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── base.py                   # Base model class with common fields
│   │   ├── photographer.py
│   │   ├── event.py
│   │   ├── folder.py
│   │   ├── photo.py
│   │   ├── face_embedding.py
│   │   ├── face_cluster.py
│   │   ├── guest_session.py
│   │   ├── couple_session.py
│   │   ├── favorite.py
│   │   └── analytics_event.py
│   │
│   ├── schemas/                      # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── event.py
│   │   ├── folder.py
│   │   ├── photo.py
│   │   ├── guest.py
│   │   ├── couple.py
│   │   ├── analytics.py
│   │   ├── profile.py
│   │   └── common.py                 # Pagination, error responses
│   │
│   ├── services/                     # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth_service.py           # Registration, login, OTP, JWT
│   │   ├── event_service.py          # Event CRUD, status management
│   │   ├── folder_service.py         # Folder CRUD, reordering
│   │   ├── photo_service.py          # Photo CRUD, move, download URL
│   │   ├── upload_service.py         # Upload processing orchestration
│   │   ├── image_processing_service.py # Resize, proxy generation
│   │   ├── watermark_service.py      # Watermark application
│   │   ├── face_service.py           # Interface to AI/ML pipeline
│   │   ├── guest_service.py          # Guest auth, selfie match
│   │   ├── couple_service.py         # Couple auth, favorites
│   │   ├── sharing_service.py        # Link generation, toggle
│   │   ├── analytics_service.py      # Metrics, lead capture
│   │   ├── notification_service.py   # Email, SMS delivery
│   │   ├── storage_service.py        # S3 operations (upload, download, presign)
│   │   └── archival_service.py       # Data retention, archival, deletion
│   │
│   ├── tasks/                        # Celery task definitions
│   │   ├── __init__.py
│   │   ├── celery_app.py             # Celery application configuration
│   │   ├── photo_tasks.py            # Resize, watermark, proxy generation
│   │   ├── face_tasks.py             # Detection, embedding, clustering
│   │   ├── notification_tasks.py     # Email and SMS delivery
│   │   └── archival_tasks.py         # Scheduled archival and cleanup
│   │
│   ├── core/                         # Cross-cutting concerns
│   │   ├── __init__.py
│   │   ├── database.py               # Async SQLAlchemy engine, session factory
│   │   ├── security.py               # Password hashing, JWT utils
│   │   ├── exceptions.py             # Custom exception classes
│   │   ├── middleware.py              # Request logging, CORS, rate limiting
│   │   └── constants.py              # Application constants
│   │
│   └── utils/                        # Utilities
│       ├── __init__.py
│       ├── slug.py                   # Event slug generation
│       ├── otp.py                    # OTP generation, storage, verification
│       ├── pagination.py             # Pagination helpers
│       ├── csv_export.py             # CSV generation for analytics export
│       └── image_utils.py            # Image format detection, EXIF handling
│
├── tests/
│   ├── conftest.py                   # Shared fixtures (test db, test client)
│   ├── factories/                    # Test data factories (factory_boy)
│   ├── unit/                         # Unit tests (services, utils)
│   ├── integration/                  # Integration tests (API endpoints)
│   └── e2e/                          # End-to-end tests
│
├── pyproject.toml                    # Project metadata + dependencies (uv)
├── Dockerfile
├── docker-compose.yml                # Local dev (postgres, redis, celery)
└── Makefile                          # Common commands (dev, test, migrate)
```

---

## 4. Database Design

### 4.1 Entity Relationship Diagram

```
┌──────────────────┐       ┌──────────────────┐
│   Photographer    │       │      Event        │
├──────────────────┤       ├──────────────────┤
│ id (PK, UUID)    │──1:N──│ id (PK, UUID)    │
│ email            │       │ photographer_id   │
│ password_hash    │       │ name              │
│ studio_name      │       │ slug (unique)     │
│ phone            │       │ date_start        │
│ phone_verified   │       │ date_end          │
│ logo_url         │       │ event_type        │
│ watermark_url    │       │ status (enum)     │
│ storage_used     │       │ description       │
│ storage_limit    │       │ cover_photo_id    │
│ is_active        │       │ download_enabled  │
│ created_at       │       │ master_link_active│
│ updated_at       │       │ guest_link_active │
└──────────────────┘       │ archive_at        │
                           │ created_at        │
                           │ updated_at        │
                           └────────┬─────────┘
                                    │
              ┌─────────────────────┼───────────────────────┐
              │                     │                       │
    ┌─────────▼────────┐  ┌────────▼─────────┐   ┌────────▼─────────┐
    │     Folder        │  │ CoupleSession    │   │  GuestSession    │
    ├──────────────────┤  ├──────────────────┤   ├──────────────────┤
    │ id (PK, UUID)    │  │ id (PK, UUID)    │   │ id (PK, UUID)    │
    │ event_id (FK)    │  │ event_id (FK)    │   │ event_id (FK)    │
    │ parent_id (FK)   │  │ name             │   │ name             │
    │ name             │  │ phone            │   │ phone            │
    │ sort_order       │  │ phone_verified   │   │ phone_verified   │
    │ created_at       │  │ created_at       │   │ selfie_url       │
    │ updated_at       │  └──────┬───────────┘   │ selfie_embedding │
    └────────┬─────────┘         │               │ match_cluster_ids│
             │              ┌────▼───────────┐   │ matched_photo_ids│
    ┌────────▼─────────┐    │   Favorite      │   │ created_at       │
    │     Photo         │    ├────────────────┤   └──────────────────┘
    ├──────────────────┤    │ id (PK, UUID)  │
    │ id (PK, UUID)    │    │ couple_sess_id │
    │ event_id (FK)    │    │ photo_id (FK)  │
    │ folder_id (FK)   │    │ created_at     │
    │ filename         │    └────────────────┘
    │ original_s3_key  │
    │ proxy_s3_key     │
    │ blurhash         │
    │ width            │
    │ height           │
    │ file_size        │
    │ mime_type        │
    │ face_count       │
    │ processing_status│
    │ uploaded_at      │
    │ created_at       │
    └────────┬─────────┘
             │
    ┌────────▼─────────┐    ┌──────────────────┐
    │  FaceEmbedding    │    │   FaceCluster     │
    ├──────────────────┤    ├──────────────────┤
    │ id (PK, UUID)    │    │ id (PK, UUID)    │
    │ photo_id (FK)    │    │ event_id (FK)    │
    │ event_id (FK)    │    │ centroid (vec512)│
    │ embedding (vec512)│──N:1│ cluster_size    │
    │ cluster_id (FK)  │    │ created_at       │
    │ bbox_x           │    │ updated_at       │
    │ bbox_y           │    │                  │
    │ bbox_w           │    └──────────────────┘
    │ bbox_h           │
    │ detection_score  │
    │ blur_score       │
    │ created_at       │
    └──────────────────┘

    ┌──────────────────┐
    │  AnalyticsEvent   │
    ├──────────────────┤
    │ id (PK, UUID)    │
    │ event_id (FK)    │
    │ photo_id (FK)    │
    │ guest_session_id │
    │ action (enum)    │  ← 'view', 'download'
    │ created_at       │
    └──────────────────┘
```

### 4.2 Table Definitions

#### `photographers`

```sql
CREATE TABLE photographers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    studio_name     VARCHAR(255) NOT NULL,
    phone           VARCHAR(20) NOT NULL,
    phone_verified  BOOLEAN DEFAULT FALSE,
    logo_url        VARCHAR(500),
    watermark_url   VARCHAR(500),
    storage_used_bytes   BIGINT DEFAULT 0,
    storage_limit_bytes  BIGINT DEFAULT 214748364800,  -- 200GB default
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_photographers_email ON photographers (email);
```

#### `events`

```sql
CREATE TYPE event_status AS ENUM ('draft', 'uploading', 'processing', 'ready', 'archived');
CREATE TYPE event_type AS ENUM ('wedding', 'corporate', 'birthday', 'other');

CREATE TABLE events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photographer_id     UUID NOT NULL REFERENCES photographers(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    slug                VARCHAR(255) NOT NULL UNIQUE,
    date_start          DATE,
    date_end            DATE,
    event_type          event_type DEFAULT 'wedding',
    status              event_status DEFAULT 'draft',
    description         TEXT,
    cover_photo_id      UUID,
    download_enabled    BOOLEAN DEFAULT TRUE,
    master_link_active  BOOLEAN DEFAULT TRUE,
    guest_link_active   BOOLEAN DEFAULT TRUE,
    total_photos        INTEGER DEFAULT 0,
    total_faces         INTEGER DEFAULT 0,
    processed_photos    INTEGER DEFAULT 0,
    archive_at          TIMESTAMPTZ,    -- auto-set to created_at + 2 months
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_photographer ON events (photographer_id);
CREATE INDEX idx_events_slug ON events (slug);
CREATE INDEX idx_events_status ON events (status);
CREATE INDEX idx_events_archive_at ON events (archive_at) WHERE status != 'archived';
```

#### `folders`

```sql
CREATE TABLE folders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id    UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    parent_id   UUID REFERENCES folders(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    sort_order  INTEGER DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (event_id, parent_id, name)
);

CREATE INDEX idx_folders_event ON folders (event_id);
CREATE INDEX idx_folders_parent ON folders (parent_id);
```

#### `photos`

```sql
CREATE TYPE processing_status AS ENUM ('pending', 'processing', 'completed', 'failed');

CREATE TABLE photos (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    folder_id           UUID REFERENCES folders(id) ON DELETE SET NULL,
    filename            VARCHAR(500) NOT NULL,
    original_s3_key     VARCHAR(500) NOT NULL,
    proxy_s3_key        VARCHAR(500),
    blurhash            VARCHAR(50),
    width               INTEGER,
    height              INTEGER,
    file_size_bytes     BIGINT NOT NULL,
    mime_type           VARCHAR(50) NOT NULL,
    face_count          INTEGER DEFAULT 0,
    processing_status   processing_status DEFAULT 'pending',
    processing_error    TEXT,
    uploaded_at         TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_photos_event ON photos (event_id);
CREATE INDEX idx_photos_folder ON photos (folder_id);
CREATE INDEX idx_photos_event_folder ON photos (event_id, folder_id);
CREATE INDEX idx_photos_processing ON photos (processing_status) WHERE processing_status != 'completed';
```

#### `face_embeddings`

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE face_embeddings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id        UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    event_id        UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    cluster_id      UUID REFERENCES face_clusters(id) ON DELETE SET NULL,
    embedding       vector(512) NOT NULL,
    bbox_x          REAL NOT NULL,
    bbox_y          REAL NOT NULL,
    bbox_w          REAL NOT NULL,
    bbox_h          REAL NOT NULL,
    detection_score REAL,
    blur_score      REAL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_face_embeddings_photo ON face_embeddings (photo_id);
CREATE INDEX idx_face_embeddings_event ON face_embeddings (event_id);
CREATE INDEX idx_face_embeddings_cluster ON face_embeddings (cluster_id);

-- HNSW index for fast vector similarity search (cosine distance)
CREATE INDEX idx_face_embeddings_vector ON face_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

#### `face_clusters`

```sql
CREATE TABLE face_clusters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    centroid        vector(512) NOT NULL,
    cluster_size    INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_face_clusters_event ON face_clusters (event_id);
```

#### `guest_sessions`

```sql
CREATE TABLE guest_sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    phone               VARCHAR(20) NOT NULL,
    phone_verified      BOOLEAN DEFAULT FALSE,
    selfie_s3_key       VARCHAR(500),
    selfie_embedding    vector(512),
    matched_cluster_ids UUID[] DEFAULT '{}',
    matched_photo_count INTEGER DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (event_id, phone)
);

CREATE INDEX idx_guest_sessions_event ON guest_sessions (event_id);
CREATE INDEX idx_guest_sessions_phone ON guest_sessions (event_id, phone);
```

#### `couple_sessions`

```sql
CREATE TABLE couple_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name            VARCHAR(255) NOT NULL,
    phone           VARCHAR(20) NOT NULL,
    phone_verified  BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (event_id, phone)
);

CREATE INDEX idx_couple_sessions_event ON couple_sessions (event_id);
```

#### `favorites`

```sql
CREATE TABLE favorites (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    couple_session_id   UUID NOT NULL REFERENCES couple_sessions(id) ON DELETE CASCADE,
    photo_id            UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (couple_session_id, photo_id)
);

CREATE INDEX idx_favorites_couple ON favorites (couple_session_id);
```

#### `analytics_events`

```sql
CREATE TYPE analytics_action AS ENUM ('view', 'download');

CREATE TABLE analytics_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    photo_id            UUID REFERENCES photos(id) ON DELETE CASCADE,
    guest_session_id    UUID REFERENCES guest_sessions(id) ON DELETE SET NULL,
    couple_session_id   UUID REFERENCES couple_sessions(id) ON DELETE SET NULL,
    action              analytics_action NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_analytics_event ON analytics_events (event_id);
CREATE INDEX idx_analytics_photo ON analytics_events (photo_id);
CREATE INDEX idx_analytics_action ON analytics_events (event_id, action);
-- Partial index for efficient download counts
CREATE INDEX idx_analytics_downloads ON analytics_events (event_id, photo_id)
    WHERE action = 'download';
```

### 4.3 Key Design Decisions

1. **UUIDs as primary keys:** Prevents enumeration attacks (guests can't iterate through photo IDs). Also enables distributed ID generation without coordination.

2. **pgvector for face embeddings:** Eliminates the need for a separate vector database (Pinecone, Milvus). pgvector's HNSW index provides sub-millisecond cosine similarity search at the scale we need (< 100K embeddings per event). Significant cost savings.

3. **Denormalized counters on `events` table:** `total_photos`, `processed_photos`, `total_faces` are maintained via triggers or application-level increments to avoid expensive `COUNT(*)` queries on large photo tables.

4. **`matched_cluster_ids` as UUID array on `guest_sessions`:** After face matching, the guest's matched cluster IDs are stored directly. The photo lookup becomes: "get all photos that have a face_embedding in any of these clusters." This avoids re-running the vector search on subsequent visits.

5. **Analytics as append-only event log:** Every view and download is recorded as an immutable event. Aggregation queries (total views, top photos) run against this log. This pattern is simple, auditable, and can later be moved to a dedicated analytics store if needed.

6. **Soft archive via `archive_at`:** Instead of deleting, events transition to `archived` status. A scheduled Celery beat task checks `archive_at` and triggers the archival workflow.

---

## 5. Authentication & Authorization

### 5.1 Authentication Flows

#### Photographer Authentication (JWT-based)

```
Registration:
  1. POST /api/v1/auth/register (email, password, studio_name, phone)
  2. Send OTP to phone → POST /api/v1/auth/send-otp
  3. Verify OTP → POST /api/v1/auth/verify-otp
  4. Account created; return JWT access_token + refresh_token

Login:
  1. POST /api/v1/auth/login (email, password)
  2. Verify password hash
  3. Return JWT access_token (15min expiry) + refresh_token (7d expiry)

Token Refresh:
  1. POST /api/v1/auth/refresh (refresh_token)
  2. Validate refresh_token
  3. Issue new access_token + refresh_token (rotate)
```

**JWT Structure:**
```json
{
  "sub": "photographer-uuid",
  "type": "access",
  "exp": 1693500000,
  "iat": 1693499100
}
```

#### Guest/Couple Authentication (OTP-based, stateless)

```
Guest Auth:
  1. POST /api/v1/event/{slug}/auth (name, phone, link_type: "guest" | "master")
  2. Send OTP to phone
  3. POST /api/v1/event/{slug}/auth/verify (phone, otp)
  4. Create or retrieve guest_session / couple_session
  5. Return session_token (JWT, 30-day expiry, scoped to event)
```

**Guest/Couple JWT:**
```json
{
  "sub": "guest-session-uuid",
  "event_id": "event-uuid",
  "type": "guest",         // or "couple"
  "exp": 1696092000
}
```

### 5.2 OTP Implementation

```python
class OTPService:
    """OTP generation, storage, and verification using Redis."""

    OTP_LENGTH = 6
    OTP_EXPIRY_SECONDS = 300  # 5 minutes
    MAX_ATTEMPTS = 3
    COOLDOWN_SECONDS = 60     # minimum time between OTP sends

    async def send_otp(self, phone: str, purpose: str) -> None:
        """Generate OTP, store in Redis, send via SMS provider."""
        cooldown_key = f"otp:cooldown:{phone}:{purpose}"
        if await self.redis.exists(cooldown_key):
            raise OTPCooldownError("Please wait before requesting a new OTP")

        otp = self._generate_otp()
        otp_key = f"otp:{phone}:{purpose}"
        attempts_key = f"otp:attempts:{phone}:{purpose}"

        await self.redis.setex(otp_key, self.OTP_EXPIRY_SECONDS, otp)
        await self.redis.setex(cooldown_key, self.COOLDOWN_SECONDS, "1")
        await self.redis.delete(attempts_key)

        await self.sms_provider.send(phone, f"Your verification code is: {otp}")

    async def verify_otp(self, phone: str, purpose: str, otp: str) -> bool:
        """Verify OTP against stored value. Rate-limited to MAX_ATTEMPTS."""
        attempts_key = f"otp:attempts:{phone}:{purpose}"
        attempts = await self.redis.incr(attempts_key)
        await self.redis.expire(attempts_key, self.OTP_EXPIRY_SECONDS)

        if attempts > self.MAX_ATTEMPTS:
            raise OTPMaxAttemptsError("Too many attempts. Request a new OTP.")

        otp_key = f"otp:{phone}:{purpose}"
        stored_otp = await self.redis.get(otp_key)

        if stored_otp and stored_otp == otp:
            await self.redis.delete(otp_key)
            await self.redis.delete(attempts_key)
            return True
        return False

    def _generate_otp(self) -> str:
        """Cryptographically secure OTP generation."""
        return "".join(secrets.choice(string.digits) for _ in range(self.OTP_LENGTH))
```

### 5.3 Authorization Model

| Role | Scope | Permissions |
|---|---|---|
| **Photographer** | Global (own data) | Full CRUD on own events, photos, folders, profile. View own analytics. |
| **Couple** | Single event (via Master Link) | View all photos, mark favorites, download originals (if enabled). |
| **Guest** | Single event (via Guest Link) | View matched photos only, download originals (if enabled). |

**Authorization Dependency:**

```python
async def get_current_photographer(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Photographer:
    """Extract and validate photographer from JWT."""
    payload = decode_jwt(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    photographer = await db.get(Photographer, payload["sub"])
    if not photographer or not photographer.is_active:
        raise HTTPException(status_code=401, detail="Account not found or inactive")
    return photographer


async def get_current_guest_session(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> GuestSession:
    """Extract and validate guest session from JWT."""
    payload = decode_jwt(token)
    if payload.get("type") != "guest":
        raise HTTPException(status_code=401, detail="Invalid token type")

    session = await db.get(GuestSession, payload["sub"])
    if not session:
        raise HTTPException(status_code=401, detail="Session not found")
    return session
```

### 5.4 Event Ownership Validation

Every photographer API endpoint that operates on an event validates ownership:

```python
async def get_photographer_event(
    event_id: UUID,
    photographer: Photographer = Depends(get_current_photographer),
    db: AsyncSession = Depends(get_db),
) -> Event:
    """Ensure the event belongs to the authenticated photographer."""
    event = await db.get(Event, event_id)
    if not event or event.photographer_id != photographer.id:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
```

---

## 6. API Specification

### 6.1 API Conventions

- **Base URL:** `/api/v1/`
- **Content Type:** `application/json` (except file uploads)
- **Authentication:** `Authorization: Bearer <token>` header
- **Pagination:** Offset-based with `?offset=0&limit=50`
- **Sorting:** `?sort_by=created_at&sort_order=desc`
- **Error Format:**

```json
{
  "detail": "Human-readable error message",
  "code": "MACHINE_READABLE_ERROR_CODE",
  "errors": [
    {
      "field": "email",
      "message": "Email already registered"
    }
  ]
}
```

### 6.2 Endpoint Specifications

#### Authentication

**POST `/api/v1/auth/register`**

```python
# Request
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    studio_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(pattern=r"^\+91\d{10}$")

# Response (201 Created)
class RegisterResponse(BaseModel):
    id: UUID
    email: str
    studio_name: str
    phone: str
    message: str  # "OTP sent to your phone for verification"
```

**POST `/api/v1/auth/login`**

```python
# Request
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Response (200 OK)
class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    photographer: PhotographerProfile
```

**POST `/api/v1/auth/send-otp`**

```python
# Request
class SendOTPRequest(BaseModel):
    phone: str
    purpose: Literal["registration", "login", "guest_auth"]

# Response (200 OK)
class SendOTPResponse(BaseModel):
    message: str  # "OTP sent successfully"
    expires_in: int  # seconds
```

**POST `/api/v1/auth/verify-otp`**

```python
# Request
class VerifyOTPRequest(BaseModel):
    phone: str
    otp: str = Field(min_length=6, max_length=6)
    purpose: str

# Response (200 OK)
class VerifyOTPResponse(BaseModel):
    verified: bool
```

#### Events

**GET `/api/v1/events`**

```python
# Query params: offset, limit, sort_by, sort_order, status (filter)
# Response (200 OK)
class EventListResponse(BaseModel):
    events: list[EventSummary]
    total: int
    offset: int
    limit: int

class EventSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    date_start: date | None
    date_end: date | None
    event_type: EventType
    status: EventStatus
    total_photos: int
    folder_count: int
    guest_count: int
    cover_image_url: str | None
    created_at: datetime
```

**POST `/api/v1/events`**

```python
# Request
class CreateEventRequest(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    date_start: date | None = None
    date_end: date | None = None
    event_type: EventType = EventType.WEDDING
    description: str | None = Field(None, max_length=500)

# Response (201 Created)
class EventDetail(BaseModel):
    id: UUID
    name: str
    slug: str
    date_start: date | None
    date_end: date | None
    event_type: EventType
    status: EventStatus
    description: str | None
    download_enabled: bool
    master_link_active: bool
    guest_link_active: bool
    master_link_url: str
    guest_link_url: str
    total_photos: int
    processed_photos: int
    created_at: datetime
    archive_at: datetime
```

**GET `/api/v1/events/{event_id}`** → Returns `EventDetail`

**PUT `/api/v1/events/{event_id}`** → Partial update (name, dates, description, type)

**DELETE `/api/v1/events/{event_id}`** → Soft delete, frees storage

#### Folders

**GET `/api/v1/events/{event_id}/folders`**

```python
# Response (200 OK) — returns nested tree structure
class FolderTree(BaseModel):
    folders: list[FolderNode]

class FolderNode(BaseModel):
    id: UUID
    name: str
    sort_order: int
    photo_count: int
    children: list[FolderNode]
```

**POST `/api/v1/events/{event_id}/folders`**

```python
# Request
class CreateFolderRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    parent_id: UUID | None = None  # null = root level

# Response (201 Created) → FolderNode
```

**PUT `/api/v1/events/{event_id}/folders/{folder_id}`**

```python
# Request (partial update)
class UpdateFolderRequest(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    parent_id: UUID | None = None  # move to different parent
```

**DELETE `/api/v1/events/{event_id}/folders/{folder_id}`** → Deletes folder (photos move to root or get deleted based on query param `?delete_photos=true`)

#### Photos

**GET `/api/v1/events/{event_id}/photos`**

```python
# Query params: folder_id, offset, limit, sort_by
# Response (200 OK)
class PhotoListResponse(BaseModel):
    photos: list[PhotoSummary]
    total: int
    has_more: bool
    offset: int
    limit: int

class PhotoSummary(BaseModel):
    id: UUID
    filename: str
    folder_id: UUID | None
    proxy_url: str          # presigned S3 URL for web-proxy
    blurhash: str | None
    width: int
    height: int
    file_size_bytes: int
    face_count: int
    processing_status: ProcessingStatus
    uploaded_at: datetime
```

**POST `/api/v1/events/{event_id}/photos/move`**

```python
# Request
class MovePhotosRequest(BaseModel):
    photo_ids: list[UUID]
    target_folder_id: UUID | None  # null = root
```

**DELETE `/api/v1/events/{event_id}/photos/{photo_id}`** → Deletes photo + original + proxy + embeddings

**GET `/api/v1/events/{event_id}/photos/{photo_id}/download`** → Returns presigned S3 URL for original file (redirects or returns URL in JSON)

#### Upload Webhook

**POST `/api/v1/upload/hook`** (called by tusd on upload completion)

```python
# Request (from tusd webhook)
class TusHookPayload(BaseModel):
    upload: TusUploadInfo

class TusUploadInfo(BaseModel):
    id: str
    size: int
    offset: int
    metadata: dict  # Contains event_id, folder_id, filename, photographer_id
    storage: dict   # Contains S3 key

# This endpoint:
# 1. Creates a Photo record in the database
# 2. Dispatches Celery tasks: resize, watermark, face detection
# 3. Updates event photo counters
```

#### Guest Endpoints

**GET `/api/v1/event/{slug}/info`** (public, no auth)

```python
# Response (200 OK)
class EventPublicInfo(BaseModel):
    name: str
    date_start: date | None
    date_end: date | None
    studio_name: str
    studio_logo_url: str | None
    guest_link_active: bool
    master_link_active: bool
```

**POST `/api/v1/event/{slug}/auth`**

```python
# Request
class EventAuthRequest(BaseModel):
    name: str
    phone: str
    link_type: Literal["guest", "master"]

# Response (200 OK)
class EventAuthResponse(BaseModel):
    message: str  # "OTP sent"
```

**POST `/api/v1/event/{slug}/auth/verify`**

```python
# Request
class EventAuthVerifyRequest(BaseModel):
    phone: str
    otp: str
    link_type: Literal["guest", "master"]

# Response (200 OK)
class EventAuthVerifyResponse(BaseModel):
    session_token: str
    session_type: str
    needs_selfie: bool  # true for guests without existing match
```

**POST `/api/v1/event/{slug}/selfie`** (guest auth required)

```python
# Request: multipart/form-data with selfie image
# Response (200 OK)
class SelfieMatchResponse(BaseModel):
    matched_photo_count: int
    status: Literal["matched", "no_match", "processing"]
```

**GET `/api/v1/event/{slug}/guest/photos`** (guest auth required)

```python
# Query params: offset, limit
# Response: PhotoListResponse (same structure, filtered to matched photos)
```

#### Couple Endpoints

**GET `/api/v1/event/{slug}/master/photos`** (couple auth required)

```python
# Query params: folder_id, offset, limit
# Response: PhotoListResponse (all photos)
```

**GET `/api/v1/event/{slug}/master/folders`** (couple auth required) → `FolderTree`

**POST `/api/v1/event/{slug}/master/favorite`** (couple auth required)

```python
# Request
class ToggleFavoriteRequest(BaseModel):
    photo_id: UUID

# Response (200 OK)
class ToggleFavoriteResponse(BaseModel):
    is_favorite: bool
```

**GET `/api/v1/event/{slug}/master/favorites`** → `PhotoListResponse` (favorites only)

#### Analytics

**GET `/api/v1/events/{event_id}/analytics/summary`**

```python
# Response (200 OK)
class AnalyticsSummary(BaseModel):
    total_guests: int
    total_views: int
    total_downloads: int
```

**GET `/api/v1/events/{event_id}/analytics/top-photos`**

```python
# Query param: ?metric=views|downloads&limit=10
# Response (200 OK)
class TopPhotosResponse(BaseModel):
    photos: list[PhotoWithStats]

class PhotoWithStats(BaseModel):
    id: UUID
    filename: str
    folder_name: str | None
    proxy_url: str
    views: int
    downloads: int
```

**GET `/api/v1/events/{event_id}/analytics/guests`**

```python
# Query params: offset, limit, sort_by
# Response (200 OK)
class GuestListResponse(BaseModel):
    guests: list[GuestAnalytics]
    total: int
    offset: int
    limit: int

class GuestAnalytics(BaseModel):
    name: str
    phone: str
    first_visited: datetime
    photos_matched: int
    photos_downloaded: int
```

**GET `/api/v1/events/{event_id}/analytics/guests/export`** → Returns CSV file download

#### Profile

**GET `/api/v1/profile`** → `PhotographerProfile`

**PUT `/api/v1/profile`** → Update studio_name, phone, etc.

**POST `/api/v1/profile/logo`** → Multipart upload, stores in S3, returns URL

**POST `/api/v1/profile/watermark`** → Multipart upload, stores in S3, returns URL

**GET `/api/v1/profile/storage`**

```python
# Response (200 OK)
class StorageInfo(BaseModel):
    used_bytes: int
    limit_bytes: int
    active_bytes: int     # storage used by active events
    archived_bytes: int   # storage used by archived events
    used_percentage: float
```

---

## 7. Upload Pipeline

### 7.1 Architecture: tusd + S3 + Celery

The upload pipeline uses **tusd** (a Go-based tus protocol server) as a sidecar service that handles the complexity of chunked, resumable uploads directly to S3. This separates the upload data path (heavy I/O) from the FastAPI application (business logic).

```
Browser (tus-js-client)
        │
        │  TUS Protocol (PATCH chunks)
        ▼
┌──────────────────┐
│      tusd         │
│  (tus server)     │
│                   │
│  Stores chunks    │
│  directly to S3   │
│  (multipart)      │
└────────┬─────────┘
         │  POST webhook on completion
         ▼
┌──────────────────┐
│    FastAPI         │
│  /api/v1/upload/   │
│  hook              │
│                    │
│  1. Create Photo   │
│     record in DB   │
│  2. Dispatch       │
│     Celery tasks   │
└────────┬──────────┘
         │  Task dispatch
         ▼
┌──────────────────┐
│  Celery Workers   │
│                   │
│  1. Generate      │
│     web-proxy     │
│  2. Apply         │
│     watermark     │
│  3. Generate      │
│     blurhash      │
│  4. Face detect   │
│  5. Extract       │
│     embeddings    │
│  6. Update DB     │
└──────────────────┘
```

### 7.2 tusd Configuration

```yaml
# tusd configuration
storage: s3
s3-bucket: "platform-uploads"
s3-endpoint: "https://s3.ap-south-1.amazonaws.com"
s3-object-prefix: "originals/"
s3-part-size: 5242880  # 5MB chunks

hooks:
  enabled-hooks:
    - post-finish     # Fires when upload completes
    - post-terminate  # Fires when upload is cancelled
  http:
    endpoint: "http://fastapi:8000/api/v1/upload/hook"
    retry: 3
    backoff: 1

max-size: 52428800  # 50MB max file size
behind-proxy: true
```

### 7.3 Upload Metadata

When the frontend initiates a tus upload, it includes metadata:

```typescript
// Frontend tus upload creation
const upload = new tus.Upload(file, {
  endpoint: '/api/upload/',
  retryDelays: [0, 1000, 3000, 5000],
  chunkSize: 5 * 1024 * 1024, // 5MB
  metadata: {
    filename: file.name,
    filetype: file.type,
    event_id: eventId,
    folder_id: folderId,
    photographer_id: photographerId,
  },
  onProgress: (bytesUploaded, bytesTotal) => { ... },
  onSuccess: () => { ... },
  onError: (error) => { ... },
});
```

### 7.4 Post-Upload Processing Chain (Celery)

When tusd fires the `post-finish` webhook:

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_uploaded_photo(self, photo_id: str, s3_key: str, event_id: str) -> None:
    """Orchestrates the full processing chain for an uploaded photo."""
    try:
        # Step 1: Generate web-proxy
        proxy_s3_key = generate_web_proxy(s3_key, event_id)

        # Step 2: Apply watermark to web-proxy
        watermark_url = get_photographer_watermark(event_id)
        if watermark_url:
            apply_watermark(proxy_s3_key, watermark_url)

        # Step 3: Generate blurhash
        blurhash = generate_blurhash(proxy_s3_key)

        # Step 4: Extract image dimensions
        width, height = get_image_dimensions(s3_key)

        # Step 5: Update photo record
        update_photo_record(
            photo_id=photo_id,
            proxy_s3_key=proxy_s3_key,
            blurhash=blurhash,
            width=width,
            height=height,
            processing_status="completed",
        )

        # Step 6: Dispatch face detection (separate task)
        detect_faces_task.delay(photo_id, s3_key, event_id)

    except Exception as exc:
        update_photo_record(photo_id=photo_id, processing_status="failed",
                          processing_error=str(exc))
        raise self.retry(exc=exc)
```

```python
@celery_app.task(bind=True, max_retries=2)
def detect_faces_task(self, photo_id: str, s3_key: str, event_id: str) -> None:
    """Detect faces, extract embeddings, update clusters."""
    # Calls into the AI/ML pipeline (Component 3)
    face_service = get_face_service()
    results = face_service.process_photo(s3_key)

    for face in results.faces:
        # Store embedding in pgvector
        create_face_embedding(
            photo_id=photo_id,
            event_id=event_id,
            embedding=face.embedding,
            bbox=face.bbox,
            detection_score=face.score,
            blur_score=face.blur_score,
        )

    # Update photo face count
    update_photo_face_count(photo_id, len(results.faces))

    # Trigger incremental clustering for this event
    update_event_clusters.delay(event_id)
```

### 7.5 Event Processing Status Tracking

The event status transitions based on photo processing progress:

```python
async def update_event_processing_status(event_id: UUID, db: AsyncSession) -> None:
    """Update event status based on photo processing completion."""
    event = await db.get(Event, event_id)

    stats = await db.execute(
        select(
            func.count(Photo.id).label("total"),
            func.count(Photo.id).filter(
                Photo.processing_status == "completed"
            ).label("completed"),
        ).where(Photo.event_id == event_id)
    )
    total, completed = stats.one()

    event.total_photos = total
    event.processed_photos = completed

    if total == 0:
        event.status = EventStatus.DRAFT
    elif completed < total:
        event.status = EventStatus.PROCESSING
    elif completed == total:
        event.status = EventStatus.READY
        # Trigger notification to photographer
        notify_processing_complete.delay(str(event_id))

    await db.commit()
```

---

## 8. Dual-Resolution Processing Engine

### 8.1 Web-Proxy Generation

```python
class ImageProcessingService:
    """Generates web-optimized proxy images from originals."""

    PROXY_MAX_DIMENSION = 2048
    PROXY_QUALITY_WEBP = 82
    PROXY_QUALITY_JPEG = 85
    PROXY_TARGET_SIZE_KB = 500

    async def generate_web_proxy(
        self, original_s3_key: str, event_id: str
    ) -> str:
        """Download original, generate optimized proxy, upload to hot storage."""
        image_bytes = await self.storage.download(original_s3_key)
        image = Image.open(io.BytesIO(image_bytes))

        # Handle EXIF orientation
        image = ImageOps.exif_transpose(image)

        # Resize (maintain aspect ratio)
        image.thumbnail(
            (self.PROXY_MAX_DIMENSION, self.PROXY_MAX_DIMENSION),
            Image.LANCZOS,
        )

        # Convert to RGB (handle RGBA, CMYK, etc.)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        # Encode as WebP (primary) with JPEG fallback
        proxy_buffer = io.BytesIO()
        image.save(proxy_buffer, format="WEBP", quality=self.PROXY_QUALITY_WEBP)

        # If WebP output is too large, reduce quality iteratively
        quality = self.PROXY_QUALITY_WEBP
        while proxy_buffer.tell() > self.PROXY_TARGET_SIZE_KB * 1024 and quality > 50:
            quality -= 5
            proxy_buffer = io.BytesIO()
            image.save(proxy_buffer, format="WEBP", quality=quality)

        proxy_s3_key = f"proxies/{event_id}/{uuid4()}.webp"
        await self.storage.upload(
            proxy_s3_key,
            proxy_buffer.getvalue(),
            content_type="image/webp",
            storage_class="STANDARD",  # hot storage for frequent access
        )

        return proxy_s3_key

    def generate_blurhash(self, image: Image.Image) -> str:
        """Generate a compact blurhash string for placeholder rendering."""
        small = image.copy()
        small.thumbnail((32, 32))
        return blurhash_encode(
            numpy.array(small.convert("RGB")),
            x_components=4,
            y_components=3,
        )
```

### 8.2 HEIC/HEIF Handling

```python
from pillow_heif import register_heif_opener

register_heif_opener()

def load_image(file_bytes: bytes, mime_type: str) -> Image.Image:
    """Load image from bytes, handling HEIC/HEIF transparently."""
    image = Image.open(io.BytesIO(file_bytes))
    return ImageOps.exif_transpose(image)
```

### 8.3 Storage Tiering

| Asset | S3 Storage Class | Bucket/Prefix | Access Pattern |
|---|---|---|---|
| Original photos | S3 Infrequent Access (S3-IA) | `originals/{event_id}/{uuid}.{ext}` | Only on explicit download; rare |
| Web-proxies | S3 Standard | `proxies/{event_id}/{uuid}.webp` | Every gallery view; frequent |
| Thumbnails/blurhash | Database (text column) | N/A | Every gallery grid load |
| Selfie images | S3 Standard | `selfies/{event_id}/{session_id}.jpg` | Once during processing; deleted after embedding extraction |
| Watermark images | S3 Standard | `watermarks/{photographer_id}.png` | Every proxy generation; cached |
| Studio logos | S3 Standard | `logos/{photographer_id}.{ext}` | Every page load; CDN-cached |
| Archived originals | S3 Glacier Instant Retrieval | `archive/{event_id}/...` | Rare restore operations |
| Archived proxies | Deleted on archive | N/A | Not needed after archive |

---

## 9. Watermark Engine

```python
class WatermarkService:
    """Applies photographer's watermark to web-proxy images."""

    WATERMARK_OPACITY = 0.4       # 40% opacity (semi-transparent)
    WATERMARK_MAX_WIDTH_RATIO = 0.2  # watermark max 20% of image width
    WATERMARK_PADDING_RATIO = 0.02   # 2% padding from edges

    async def apply_watermark(
        self, proxy_s3_key: str, watermark_s3_key: str
    ) -> None:
        """Download proxy and watermark, composite, re-upload."""
        proxy_bytes = await self.storage.download(proxy_s3_key)
        watermark_bytes = await self.storage.download(watermark_s3_key)

        proxy = Image.open(io.BytesIO(proxy_bytes)).convert("RGBA")
        watermark = Image.open(io.BytesIO(watermark_bytes)).convert("RGBA")

        # Scale watermark proportionally
        max_wm_width = int(proxy.width * self.WATERMARK_MAX_WIDTH_RATIO)
        wm_ratio = max_wm_width / watermark.width
        wm_size = (max_wm_width, int(watermark.height * wm_ratio))
        watermark = watermark.resize(wm_size, Image.LANCZOS)

        # Apply opacity
        alpha = watermark.split()[3]
        alpha = alpha.point(lambda p: int(p * self.WATERMARK_OPACITY))
        watermark.putalpha(alpha)

        # Position: bottom-right with padding
        padding = int(proxy.width * self.WATERMARK_PADDING_RATIO)
        position = (
            proxy.width - watermark.width - padding,
            proxy.height - watermark.height - padding,
        )

        # Composite
        proxy.paste(watermark, position, watermark)

        # Convert back to RGB and save as WebP
        result = proxy.convert("RGB")
        buffer = io.BytesIO()
        result.save(buffer, format="WEBP", quality=82)

        await self.storage.upload(proxy_s3_key, buffer.getvalue(), content_type="image/webp")
```

---

## 10. Notification Service

### 10.1 Notification Types

| Notification | Channel | Trigger |
|---|---|---|
| Phone OTP | SMS | Registration, login, guest auth |
| Processing Complete | Email + SMS | All event photos processed |
| Archival Warning (7 days) | Email | 7 days before auto-archive |
| Archival Warning (1 day) | Email | 1 day before auto-archive |

### 10.2 SMS Provider

For OTP and SMS notifications, use an SMS gateway that supports Indian numbers:

```python
class SMSService:
    """SMS delivery via provider API (MSG91, Twilio, or AWS SNS)."""

    async def send(self, phone: str, message: str) -> bool:
        """Send SMS to phone number."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.provider_url}/sms/send",
                json={
                    "to": phone,
                    "message": message,
                    "sender_id": self.sender_id,
                },
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            return response.status_code == 200
```

### 10.3 Email Service

```python
class EmailService:
    """Email delivery via AWS SES or SMTP."""

    async def send_processing_complete(
        self, photographer_email: str, event_name: str,
        photo_count: int, event_url: str,
    ) -> None:
        """Send processing complete notification."""
        await self.send(
            to=photographer_email,
            subject=f"Your event '{event_name}' is ready to share!",
            template="processing_complete",
            context={
                "event_name": event_name,
                "photo_count": photo_count,
                "event_url": event_url,
            },
        )

    async def send_archival_warning(
        self, photographer_email: str, event_name: str,
        days_remaining: int, event_url: str,
    ) -> None:
        """Send archival warning notification."""
        await self.send(
            to=photographer_email,
            subject=f"Event '{event_name}' will be archived in {days_remaining} day(s)",
            template="archival_warning",
            context={
                "event_name": event_name,
                "days_remaining": days_remaining,
                "event_url": event_url,
            },
        )
```

---

## 11. Analytics Service

### 11.1 Event Tracking

Analytics events are recorded as lightweight database inserts on every photo view and download:

```python
class AnalyticsService:
    """Records and queries analytics events."""

    async def record_view(
        self, event_id: UUID, photo_id: UUID,
        session_id: UUID | None = None,
        session_type: str | None = None,
    ) -> None:
        """Record a photo view event."""
        analytics_event = AnalyticsEvent(
            event_id=event_id,
            photo_id=photo_id,
            guest_session_id=session_id if session_type == "guest" else None,
            couple_session_id=session_id if session_type == "couple" else None,
            action=AnalyticsAction.VIEW,
        )
        self.db.add(analytics_event)
        await self.db.flush()

    async def record_download(
        self, event_id: UUID, photo_id: UUID,
        session_id: UUID | None = None,
        session_type: str | None = None,
    ) -> None:
        """Record a photo download event."""
        analytics_event = AnalyticsEvent(
            event_id=event_id,
            photo_id=photo_id,
            guest_session_id=session_id if session_type == "guest" else None,
            couple_session_id=session_id if session_type == "couple" else None,
            action=AnalyticsAction.DOWNLOAD,
        )
        self.db.add(analytics_event)
        await self.db.flush()

    async def get_summary(self, event_id: UUID) -> AnalyticsSummary:
        """Get aggregate stats for an event."""
        guest_count = await self.db.scalar(
            select(func.count(GuestSession.id)).where(
                GuestSession.event_id == event_id,
                GuestSession.phone_verified.is_(True),
            )
        )

        stats = await self.db.execute(
            select(
                func.count(AnalyticsEvent.id).filter(
                    AnalyticsEvent.action == "view"
                ).label("views"),
                func.count(AnalyticsEvent.id).filter(
                    AnalyticsEvent.action == "download"
                ).label("downloads"),
            ).where(AnalyticsEvent.event_id == event_id)
        )
        row = stats.one()

        return AnalyticsSummary(
            total_guests=guest_count,
            total_views=row.views,
            total_downloads=row.downloads,
        )

    async def get_top_photos(
        self, event_id: UUID, metric: str = "views", limit: int = 10,
    ) -> list[PhotoWithStats]:
        """Get most viewed or most downloaded photos."""
        action_filter = "view" if metric == "views" else "download"
        query = (
            select(
                Photo,
                func.count(AnalyticsEvent.id).label("count"),
            )
            .join(AnalyticsEvent, AnalyticsEvent.photo_id == Photo.id)
            .where(
                Photo.event_id == event_id,
                AnalyticsEvent.action == action_filter,
            )
            .group_by(Photo.id)
            .order_by(desc("count"))
            .limit(limit)
        )
        results = await self.db.execute(query)
        return [
            PhotoWithStats(photo=row.Photo, count=row.count)
            for row in results
        ]

    async def get_guest_list(
        self, event_id: UUID, offset: int = 0, limit: int = 20,
    ) -> tuple[list[GuestAnalytics], int]:
        """Get guest list with analytics for lead capture."""
        total = await self.db.scalar(
            select(func.count(GuestSession.id)).where(
                GuestSession.event_id == event_id,
                GuestSession.phone_verified.is_(True),
            )
        )

        download_subq = (
            select(
                AnalyticsEvent.guest_session_id,
                func.count(AnalyticsEvent.id).label("download_count"),
            )
            .where(
                AnalyticsEvent.event_id == event_id,
                AnalyticsEvent.action == "download",
            )
            .group_by(AnalyticsEvent.guest_session_id)
            .subquery()
        )

        query = (
            select(GuestSession, download_subq.c.download_count)
            .outerjoin(download_subq, GuestSession.id == download_subq.c.guest_session_id)
            .where(
                GuestSession.event_id == event_id,
                GuestSession.phone_verified.is_(True),
            )
            .order_by(GuestSession.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        results = await self.db.execute(query)
        guests = [
            GuestAnalytics(
                name=row.GuestSession.name,
                phone=row.GuestSession.phone,
                first_visited=row.GuestSession.created_at,
                photos_matched=row.GuestSession.matched_photo_count,
                photos_downloaded=row.download_count or 0,
            )
            for row in results
        ]
        return guests, total

    async def export_guest_csv(self, event_id: UUID) -> str:
        """Generate CSV of all guests for the event."""
        guests, _ = await self.get_guest_list(event_id, offset=0, limit=10000)
        return generate_csv(
            headers=["Name", "Phone", "First Visited", "Photos Matched", "Photos Downloaded"],
            rows=[
                [g.name, g.phone, g.first_visited.isoformat(),
                 str(g.photos_matched), str(g.photos_downloaded)]
                for g in guests
            ],
        )
```

---

## 12. Data Retention & Archival

### 12.1 Archival Scheduler

A Celery Beat periodic task runs daily to check for events that need archival:

```python
# Celery Beat schedule
celery_app.conf.beat_schedule = {
    "check-archival": {
        "task": "app.tasks.archival_tasks.check_events_for_archival",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM IST
    },
    "send-archival-warnings": {
        "task": "app.tasks.archival_tasks.send_archival_warnings",
        "schedule": crontab(hour=10, minute=0),  # Daily at 10 AM IST
    },
}
```

### 12.2 Archival Workflow

```python
@celery_app.task
def check_events_for_archival() -> None:
    """Check for events past their archive_at date and archive them."""
    overdue_events = db.query(Event).filter(
        Event.archive_at <= datetime.utcnow(),
        Event.status != EventStatus.ARCHIVED,
    ).all()

    for event in overdue_events:
        archive_event.delay(str(event.id))


@celery_app.task(bind=True, max_retries=3)
def archive_event(self, event_id: str) -> None:
    """Archive an event: move originals to Glacier, delete proxies."""
    event = db.get(Event, event_id)

    # 1. Move originals from S3-IA to S3 Glacier Instant Retrieval
    for photo in event.photos:
        storage.change_storage_class(
            photo.original_s3_key,
            target_class="GLACIER_IR",
        )

    # 2. Delete web-proxies (no longer needed; link shows "archived" page)
    for photo in event.photos:
        if photo.proxy_s3_key:
            storage.delete(photo.proxy_s3_key)
            photo.proxy_s3_key = None

    # 3. Delete face embeddings from pgvector (free up index space)
    db.execute(
        delete(FaceEmbedding).where(FaceEmbedding.event_id == event_id)
    )

    # 4. Delete face clusters
    db.execute(
        delete(FaceCluster).where(FaceCluster.event_id == event_id)
    )

    # 5. Update event status
    event.status = EventStatus.ARCHIVED
    db.commit()

    # 6. Notify photographer
    send_archival_complete_email.delay(event_id)
```

### 12.3 Storage Accounting

```python
async def recalculate_photographer_storage(photographer_id: UUID) -> None:
    """Recalculate total storage used across all events (active + archived)."""
    total = await db.scalar(
        select(func.coalesce(func.sum(Photo.file_size_bytes), 0))
        .join(Event, Photo.event_id == Event.id)
        .where(Event.photographer_id == photographer_id)
    )
    await db.execute(
        update(Photographer)
        .where(Photographer.id == photographer_id)
        .values(storage_used_bytes=total)
    )
    await db.commit()
```

---

## 13. Error Handling & Logging

### 13.1 Exception Hierarchy

```python
class AppException(Exception):
    """Base application exception."""
    def __init__(self, message: str, code: str, status_code: int = 400):
        self.message = message
        self.code = code
        self.status_code = status_code

class NotFoundError(AppException):
    def __init__(self, resource: str):
        super().__init__(f"{resource} not found", "NOT_FOUND", 404)

class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTH_FAILED", 401)

class AuthorizationError(AppException):
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, "FORBIDDEN", 403)

class OTPCooldownError(AppException):
    def __init__(self, message: str = "Please wait before requesting a new OTP"):
        super().__init__(message, "OTP_COOLDOWN", 429)

class OTPMaxAttemptsError(AppException):
    def __init__(self, message: str = "Too many attempts"):
        super().__init__(message, "OTP_MAX_ATTEMPTS", 429)

class StorageLimitError(AppException):
    def __init__(self):
        super().__init__("Storage limit exceeded", "STORAGE_LIMIT", 402)

class ProcessingError(AppException):
    def __init__(self, message: str):
        super().__init__(message, "PROCESSING_ERROR", 500)
```

### 13.2 Global Exception Handler

```python
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "code": "VALIDATION_ERROR",
            "errors": [
                {"field": ".".join(str(l) for l in e["loc"]), "message": e["msg"]}
                for e in exc.errors()
            ],
        },
    )
```

### 13.3 Structured Logging

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()

# Usage in services
logger.info("photo.processed",
    photo_id=str(photo.id),
    event_id=str(event.id),
    processing_time_ms=elapsed_ms,
    face_count=face_count,
)

logger.error("photo.processing_failed",
    photo_id=str(photo.id),
    error=str(exc),
    retry_count=self.request.retries,
)
```

### 13.4 Request Logging Middleware

```python
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    logger.info("http.request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        elapsed_ms=round(elapsed_ms, 2),
    )

    response.headers["X-Request-ID"] = request_id
    return response
```

---

## 14. Configuration Management

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Application
    app_name: str = "AI Photo Sharing Platform"
    debug: bool = False
    environment: str = "development"  # development, staging, production
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    secret_key: str  # for JWT signing

    # Database
    database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/photoshare"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # AWS S3
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "ap-south-1"
    s3_bucket_originals: str = "platform-originals"
    s3_bucket_proxies: str = "platform-proxies"
    s3_bucket_assets: str = "platform-assets"  # logos, watermarks
    s3_presigned_url_expiry: int = 3600  # 1 hour

    # JWT
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_guest_token_expire_days: int = 30

    # OTP
    otp_expiry_seconds: int = 300
    otp_max_attempts: int = 3
    otp_cooldown_seconds: int = 60

    # SMS Provider
    sms_provider: str = "log"  # log | msg91 | twilio — Phase 1: log OTP
    sms_api_key: str = ""
    sms_sender_id: str = "PHOTOS"

    # Email
    email_provider: str = "none"  # none | log | ses | smtp — Phase 1: none/log
    email_from: str = "noreply@platform.com"
    ses_region: str = "ap-south-1"

    # Processing
    proxy_max_dimension: int = 2048
    proxy_quality: int = 82
    watermark_opacity: float = 0.4
    max_upload_size_bytes: int = 52428800  # 50MB

    # Sentry
    sentry_dsn: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

---

## 15. Testing Strategy

### 15.1 Testing Stack

| Type | Tool | Coverage |
|---|---|---|
| **Unit** | `pytest` + `pytest-asyncio` | Services, utilities, models |
| **Integration** | `pytest` + `httpx` (TestClient) | API endpoints end-to-end |
| **Database** | `pytest` + testcontainers or temp DB | Schema, queries, migrations |
| **Mocking** | `pytest-mock` + `respx` | External services (S3, SMS, email) |
| **Factory** | `factory_boy` | Test data generation |

### 15.2 Test Configuration

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture
async def db_session():
    """Create a clean database session for each test."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def client(db_session):
    """Create a test HTTP client."""
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

@pytest.fixture
async def authenticated_client(client, photographer_factory):
    """Create an authenticated test client."""
    photographer = await photographer_factory.create()
    token = create_access_token(str(photographer.id))
    client.headers["Authorization"] = f"Bearer {token}"
    return client, photographer
```

### 15.3 Test Example

```python
class TestEventCRUD:
    async def test_create_event(self, authenticated_client):
        client, photographer = authenticated_client
        response = await client.post("/api/v1/events", json={
            "name": "Test Wedding",
            "date_start": "2026-06-12",
            "event_type": "wedding",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Wedding"
        assert data["status"] == "draft"
        assert data["slug"]  # auto-generated

    async def test_create_event_unauthorized(self, client):
        response = await client.post("/api/v1/events", json={
            "name": "Test Wedding",
        })
        assert response.status_code == 401

    async def test_list_events_only_own(self, authenticated_client, event_factory):
        client, photographer = authenticated_client
        own_event = await event_factory.create(photographer_id=photographer.id)
        other_event = await event_factory.create()  # different photographer

        response = await client.get("/api/v1/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["id"] == str(own_event.id)
```

---

## 16. API Rate Limiting & Security

### 16.1 Rate Limiting

| Endpoint Group | Limit | Window | Purpose |
|---|---|---|---|
| Auth (login, register) | 5 requests | 1 minute | Prevent brute force |
| OTP send | 3 requests | 5 minutes | Prevent SMS abuse |
| OTP verify | 5 requests | 5 minutes | Prevent brute force |
| Photo listing | 60 requests | 1 minute | Normal usage |
| Download | 30 requests | 1 minute | Prevent bulk scraping |
| Upload webhook | 100 requests | 1 minute | Handle burst uploads |

Rate limiting is implemented via Redis counters:

```python
class RateLimiter:
    """Redis-backed sliding window rate limiter."""

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        now = time.time()
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        return results[2] <= limit
```

### 16.2 Security Measures

| Measure | Implementation |
|---|---|
| **CORS** | Restrict origins to frontend domain |
| **HTTPS** | SSL termination at load balancer |
| **SQL Injection** | SQLAlchemy parameterized queries (never raw SQL) |
| **XSS** | Pydantic input validation; no raw HTML rendering |
| **CSRF** | SameSite cookies + Bearer token auth (not cookie-based) |
| **File Validation** | Validate MIME type and magic bytes on upload; reject non-image files |
| **S3 Security** | Presigned URLs with expiry for all S3 access; no public buckets |
| **Secrets** | All secrets via environment variables; never in code |
| **Dependency Scanning** | `pip-audit` in CI pipeline |
| **Helmet-equiv headers** | `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security` |

---

*End of Backend & API Component Document v1.0*
