# AGENTS.md — AI Photo Sharing Platform

> This file provides context and rules for any AI coding agent working on this repository.  
> It is tool-agnostic — applicable to Cursor, Claude Code, GitHub Copilot, Aider, Windsurf, or any AI assistant.  
> Scoped rules for specific parts of the codebase live in `frontend/AGENTS.md` and `backend/AGENTS.md`.

---

## Project Overview

An AI-powered event photo delivery platform for professional photographers. Photographers upload event photos post-event; the system uses facial recognition to detect and cluster faces, then delivers personalized galleries to guests via a browser link (PWA). No app download required.

**Primary market:** Indian wedding photography (event-agnostic, wedding-focused).  
**Buyer:** Professional photographers and studios.  
**End users:** Wedding couples and their guests.

## Monorepo Structure

```
event-vision-pipeline/
├── frontend/                  # Next.js 14+ (App Router, TypeScript, Tailwind, Shadcn/UI)
│   ├── src/
│   │   ├── app/              # Next.js App Router pages
│   │   ├── components/       # React components (dashboard/, gallery/, guest/, couple/, shared/, ui/)
│   │   ├── lib/              # Utilities, API client, upload manager
│   │   ├── stores/           # Zustand stores
│   │   ├── hooks/            # Custom React hooks
│   │   ├── types/            # TypeScript type definitions
│   │   └── mocks/            # MSW mock handlers and data
│   ├── public/               # Static assets, PWA manifest
│   └── AGENTS.md             # Frontend-specific AI agent rules
│
├── backend/                   # Python 3.10 (FastAPI, Celery, SQLAlchemy)
│   ├── app/
│   │   ├── api/v1/           # REST API route handlers
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic layer
│   │   ├── tasks/            # Celery background tasks
│   │   ├── ml/               # AI/ML pipeline (face detection, embeddings, clustering)
│   │   │   ├── detection/    # SCRFD face detector
│   │   │   ├── embedding/    # InsightFace R100 / AdaFace / MobileFaceNet
│   │   │   ├── quality/      # Blur + head pose filtering
│   │   │   ├── clustering/   # Incremental DBSCAN + Agglomerative
│   │   │   ├── matching/     # Guest selfie → cluster matching
│   │   │   └── liveness/     # Basic liveness detection
│   │   ├── core/             # Database, security, middleware, exceptions
│   │   └── utils/            # Helpers
│   ├── models/               # ML model weight files (.onnx, .pt, .tflite)
│   ├── alembic/              # Database migrations
│   ├── tests/
│   └── AGENTS.md             # Backend-specific AI agent rules
│
├── infrastructure/            # Terraform (AWS Mumbai)
├── docs/                      # Product and component documentation
│   ├── PRD.md                # Master product requirements document
│   ├── component_frontend.md
│   ├── component_backend.md
│   ├── component_ai_ml.md
│   └── component_infrastructure.md
│
└── AGENTS.md                  # This file — project-wide rules
```

## Tech Stack

| Layer | Technology | Version / Notes |
|-------|-----------|----------------|
| Frontend framework | Next.js (App Router) | 14+ |
| Frontend language | TypeScript | Strict mode |
| Frontend styling | Tailwind CSS + Shadcn/UI | |
| Frontend state | Zustand (client) + React Query (server) | |
| Backend framework | FastAPI | Async, ASGI |
| Backend language | Python | **3.10 only** |
| ORM | SQLAlchemy 2.x | Async with asyncpg |
| Database | PostgreSQL + pgvector | Face embedding vector search |
| Cache / Broker | Redis | Celery broker + OTP storage + caching |
| Task Queue | Celery | CPU: proxy + watermark. Face jobs stubbed until ML host exists |
| Face Detection / embeddings | PicSee pipeline | **Not on the app EC2.** Later separate machine. |
| Object Storage | AWS S3 (storage account) | Dual-tier: Standard (proxies) + IA (originals). Presigned URLs, no CloudFront |
| App server | EC2 `m6i.xlarge` Ubuntu | Compute account, **ap-south-1**, Docker Compose (Postgres, Redis, API, web, tusd, Celery) |
| IaC | Terraform | Storage account only: S3 + IAM + TF state. Not ECS/RDS/ALB |

## Documentation

Before writing code for any component, **always read** the corresponding document in `docs/`:

- `docs/PRD.md` — Complete product spec, user flows, business model, competitive landscape
- `docs/component_frontend.md` — Frontend architecture, screen designs, API contract, mock data strategy
- `docs/component_backend.md` — API endpoints, database schema, upload pipeline, Celery tasks
- `docs/component_ai_ml.md` — Face detection/embedding/clustering pipeline (based on PicSee)
- `docs/component_infrastructure.md` — AWS architecture, storage tiers, CI/CD, cost optimization

---

## Universal Coding Standards

### Architecture Principles

- **Service layer pattern:** Business logic lives in dedicated service classes, never in route handlers, React components, or Celery tasks. Routes and components are thin wrappers.
- **Single Responsibility:** Each class, module, and function does one thing. Split files exceeding ~300 lines.
- **Dependency Injection:** Pass dependencies explicitly. In Python, use FastAPI's `Depends()` and constructor injection. In TypeScript, use React Context or prop passing. No hidden global mutable state.
- **Fail fast:** Validate all inputs at system boundaries (API request handlers, task entry points, component props). Invalid data should never propagate deep into the call stack.
- **Explicit over implicit:** Favor verbose clarity over clever brevity. Code is read far more than written.

### Error Handling

- Never swallow errors silently. No bare `except:` (Python) or empty `.catch()` (TypeScript).
- Define **custom exception/error classes** for domain-specific errors. Don't reuse generic `ValueError` or `Error`.
- Always include **context** in error messages: entity IDs, the operation being attempted, and what specifically went wrong.
- Use **structured logging** — `structlog` in Python, structured JSON in TypeScript. No `print()` or `console.log()` for production code.

### Code Quality

- No magic strings or magic numbers. Use **constants, enums, or config** values.
- No commented-out code in commits. Git has history.
- Functions exceeding 60 lines likely need decomposition. Prefer small, composable functions.
- Prefer **early returns** over deep `if/else` nesting.
- Write **docstrings** (Python) and **JSDoc** (TypeScript) for every public class and function. Describe intent and contracts, not implementation.

### Naming Conventions

- Name things by **what they are or do**, not by how they work internally.
- Booleans: prefix with `is_`, `has_`, `can_`, `should_` (Python) or `is`, `has`, `can`, `should` (TypeScript).
- Avoid abbreviations except universally understood ones: `db`, `id`, `url`, `api`, `auth`.
- Files: `kebab-case` in frontend, `snake_case` in backend.

### Testing

- Every service/utility method must be **testable in isolation** with mocked dependencies.
- Test **behavior**, not implementation details. Tests should survive internal refactoring.
- Test naming: `test_{method}_{scenario}_{expected_result}` (Python) or `it("should {behavior} when {condition}")` (TypeScript).
- Don't test framework internals (e.g., don't test that React renders a div).

### Security

- Never hardcode secrets, API keys, or credentials. Use environment variables.
- Validate and sanitize all user inputs. Use Pydantic (Python) and Zod (TypeScript) at API boundaries.
- Use parameterized queries only (SQLAlchemy handles this). Never construct raw SQL with string interpolation.
- All S3 access through presigned URLs with expiry. No public buckets.

### Git Practices

- Commit messages: imperative mood, present tense ("Add upload progress bar", not "Added" or "Adds").
- One logical change per commit. Don't mix feature code with formatting or refactoring.
- Branch from `main`, PR back into `main`.

---

## Development Order

1. **Frontend** (with mock data via MSW — no backend needed)
2. **Backend** (FastAPI + database + upload pipeline)
3. **AI/ML Pipeline** (integrate PicSee into backend)
4. **Infrastructure** (S3 + one EC2 Compose stack; ML host later)
