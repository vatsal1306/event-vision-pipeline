# AI Photo Sharing Platform — Backend

FastAPI + Celery backend for the AI-powered event photo delivery platform.

## Quick Start

```bash
# Install dependencies
uv sync --dev

# Start Postgres + Redis
make infra

# Run the dev server
make dev

# Run tests
make test
```

## Stack

- **Python 3.10** — FastAPI (async ASGI)
- **PostgreSQL 16** — pgvector for face embeddings
- **Redis 7** — Celery broker, caching, OTP storage
- **Celery** — Background photo and face processing
- **SCRFD + InsightFace R100** — Face detection and embedding

See `docs/component_backend.md` and `docs/component_ai_ml.md` for architecture details.
