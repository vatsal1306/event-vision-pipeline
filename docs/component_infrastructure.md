# Component Document: Infrastructure & DevOps

> **Version:** 1.0  
> **Last Updated:** September 2026  
> **Scope:** Cloud Architecture, Storage, Containers, CI/CD, Monitoring, Security, Cost Optimization  
> **Development Order:** This is Component 4 — infrastructure is set up incrementally alongside other components, with full hardening as the last step.

---

## Table of Contents

1. [Overview & Cloud Strategy](#1-overview--cloud-strategy)
2. [Cloud Architecture](#2-cloud-architecture)
3. [Storage Architecture](#3-storage-architecture)
4. [Compute Architecture](#4-compute-architecture)
5. [Database Setup](#5-database-setup)
6. [Container Architecture](#6-container-architecture)
7. [Networking & CDN](#7-networking--cdn)
8. [CI/CD Pipeline](#8-cicd-pipeline)
9. [Monitoring & Observability](#9-monitoring--observability)
10. [Security](#10-security)
11. [Cost Optimization](#11-cost-optimization)
12. [Disaster Recovery & Backups](#12-disaster-recovery--backups)
13. [Environment Strategy](#13-environment-strategy)
14. [Infrastructure as Code](#14-infrastructure-as-code)

---

## 1. Overview & Cloud Strategy

### 1.1 Cloud Provider: AWS (Mumbai Region — ap-south-1)

**Why AWS:**
- **Prior experience:** Reduces the learning curve and speeds up deployment.
- **Mumbai region (ap-south-1):** Lowest latency for Indian users (primary market). Data residency within India.
- **Cost tools:** Extensive reserved/spot instance options, S3 storage classes, and Savings Plans for cost optimization.
- **Service breadth:** All required managed services are available (S3, RDS, ElastiCache, SES, SQS, CloudFront).

### 1.2 Cost Optimization Philosophy

This platform must be built with aggressive cost optimization from day one. A single developer startup cannot afford to waste cloud spend.

**Principles:**
1. **Use managed services only where the operational overhead justifies it** (RDS for PostgreSQL — yes; ElastiCache for Redis — maybe, could self-host on EC2).
2. **Spot instances for non-critical workloads** (Celery workers, especially face processing).
3. **Right-size everything** — start small, scale up only when metrics show need.
4. **S3 lifecycle policies** automate cost reduction without manual intervention.
5. **Reserved instances** for steady-state workloads (API server, database).
6. **Monitor and alert on cost anomalies** from day one.

---

## 2. Cloud Architecture

### 2.1 High-Level Architecture Diagram

```
                              ┌──────────────────┐
                              │   Route 53 DNS    │
                              │                   │
                              │  platform.com     │
                              │  api.platform.com │
                              │  cdn.platform.com │
                              └────────┬──────────┘
                                       │
                              ┌────────▼──────────┐
                              │   CloudFront CDN   │
                              │                    │
                              │  Static assets     │
                              │  Web-proxy images  │
                              │  Next.js SSR       │
                              └────────┬──────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                   │
           ┌────────▼──────┐  ┌───────▼───────┐  ┌───────▼───────┐
           │ ALB (Public)   │  │  ALB (Public)  │  │ S3 Origin     │
           │ Frontend       │  │  Backend       │  │ (proxies)     │
           └───────┬────────┘  └───────┬────────┘  └───────────────┘
                   │                   │
      ┌────────────┤          ┌────────┤
      │            │          │        │
┌─────▼─────┐     │   ┌──────▼──────┐ │
│ ECS Fargate│     │   │ ECS Fargate │ │
│ Next.js    │     │   │ FastAPI     │ │
│ (2 tasks)  │     │   │ (2 tasks)   │ │
└────────────┘     │   └─────────────┘ │
                   │                   │
                   │          ┌────────▼────────────┐
                   │          │  ECS Fargate / EC2   │
                   │          │  tusd Upload Server  │
                   │          │  (1 task)             │
                   │          └──────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────┐
│                    VPC Private Subnet                 │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ RDS PostgreSQL│  │ ElastiCache  │  │ EC2 Spot   │ │
│  │ (pgvector)   │  │ Redis        │  │ or ECS     │ │
│  │ db.t4g.medium│  │ cache.t4g.   │  │ Celery     │ │
│  │              │  │ micro        │  │ Workers    │ │
│  └──────────────┘  └──────────────┘  │ (GPU for   │ │
│                                       │  face proc)│ │
│                                       └────────────┘ │
│                                                       │
│  ┌──────────────────────────────────────────────────┐ │
│  │                  S3 Buckets                       │ │
│  │  platform-originals (S3-IA)                       │ │
│  │  platform-proxies (S3 Standard)                   │ │
│  │  platform-assets (S3 Standard, logos/watermarks)  │ │
│  │  platform-archive (S3 Glacier IR)                 │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  ┌───────────────┐  ┌───────────────┐                │
│  │ AWS SES       │  │ AWS SQS       │                │
│  │ (Email)       │  │ (Dead letter) │                │
│  └───────────────┘  └───────────────┘                │
└───────────────────────────────────────────────────────┘
```

### 2.2 Service Inventory

| Service | AWS Product | Instance/Config | Purpose | Monthly Cost Estimate |
|---|---|---|---|---|
| **Frontend** | ECS Fargate | 2 tasks × 0.5 vCPU, 1GB RAM | Next.js SSR | ~$30 |
| **Backend API** | ECS Fargate | 2 tasks × 1 vCPU, 2GB RAM | FastAPI application | ~$60 |
| **Upload Server** | ECS Fargate | 1 task × 0.5 vCPU, 1GB RAM | tusd server | ~$15 |
| **Celery Workers (CPU)** | ECS Fargate or EC2 Spot | 2 tasks × 1 vCPU, 2GB RAM | Image processing, notifications | ~$40 |
| **Celery Workers (GPU)** | EC2 Spot (g4dn.xlarge) | 1 instance (on-demand during processing) | Face detection + embedding | ~$100–200 (spot pricing, usage-based) |
| **Database** | RDS PostgreSQL | db.t4g.medium (2 vCPU, 4GB) | Primary database + pgvector | ~$50 |
| **Cache/Broker** | ElastiCache Redis | cache.t4g.micro (0.5GB) | Celery broker, OTP storage, caching | ~$12 |
| **Object Storage** | S3 | Multiple buckets | Photos (originals + proxies + assets) | Variable (~$50–200 based on storage) |
| **CDN** | CloudFront | Standard distribution | Web-proxy delivery, static assets | ~$20–50 (based on traffic) |
| **DNS** | Route 53 | Hosted zone | Domain management | ~$1 |
| **Email** | SES | Standard | Notifications, processing alerts | ~$1 |
| **SSL** | ACM | Free certificates | HTTPS for all domains | Free |
| **Monitoring** | CloudWatch | Basic | Logs, metrics, alarms | ~$10–20 |
| **Load Balancer** | ALB | 2 (frontend + backend) | Traffic distribution | ~$35 |

**Estimated Monthly Total (startup phase):** ~$350–650/month

---

## 3. Storage Architecture

### 3.1 S3 Bucket Design

```
platform-originals/
├── {event_id}/
│   ├── {uuid}.jpg        # Original uploaded files
│   ├── {uuid}.png
│   └── {uuid}.heic       # (converted before storage, but keeping orig ext)
│
platform-proxies/
├── {event_id}/
│   └── {uuid}.webp       # Web-optimized proxies (watermarked)
│
platform-assets/
├── logos/
│   └── {photographer_id}.{ext}    # Studio logos
├── watermarks/
│   └── {photographer_id}.png      # Watermark images
└── selfies/
    └── {event_id}/
        └── {session_id}.jpg       # Guest selfies (temporary)
│
platform-archive/
├── {event_id}/
│   └── {uuid}.jpg        # Archived originals (Glacier IR)
```

### 3.2 S3 Configuration

```hcl
# platform-originals bucket
resource "aws_s3_bucket" "originals" {
  bucket = "platform-originals"
}

resource "aws_s3_bucket_lifecycle_configuration" "originals_lifecycle" {
  bucket = aws_s3_bucket.originals.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 1
      storage_class = "STANDARD_IA"
    }
  }
}

# platform-proxies bucket
resource "aws_s3_bucket" "proxies" {
  bucket = "platform-proxies"
}

# CORS for direct browser access (presigned URLs)
resource "aws_s3_bucket_cors_configuration" "proxies_cors" {
  bucket = aws_s3_bucket.proxies.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = ["https://platform.com"]
    max_age_seconds = 3600
  }
}

# Block public access on all buckets
resource "aws_s3_bucket_public_access_block" "all_buckets" {
  for_each = toset(["originals", "proxies", "assets", "archive"])

  bucket                  = "platform-${each.key}"
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

### 3.3 S3 Access Patterns

| Operation | Access Method | Caching |
|---|---|---|
| **Gallery browsing (web-proxies)** | CloudFront → S3 presigned URL | CloudFront cache (24h TTL) |
| **Original download** | Presigned S3 URL (1h expiry) | No caching (one-time download) |
| **Upload** | tusd → S3 multipart | N/A |
| **Logo/watermark** | CloudFront → S3 | CloudFront cache (7d TTL) |
| **Selfie upload** | Direct S3 PUT via presigned URL | Deleted after processing |

### 3.4 Storage Cost Projections

For a photographer with 10 active events, each with 5,000 photos averaging 15MB:

| Asset | Size Per Event | Total (10 events) | Storage Class | Monthly Cost |
|---|---|---|---|---|
| Originals | 75GB | 750GB | S3-IA ($0.0125/GB) | $9.38 |
| Web-proxies | 2.5GB | 25GB | S3 Standard ($0.023/GB) | $0.58 |
| Face embeddings | ~15MB | ~150MB | pgvector (in RDS) | Included |
| **Total** | | **~775GB** | | **~$10/month** |

After archival (Glacier IR at $0.004/GB): same 750GB costs **$3/month** instead of $9.38.

---

## 4. Compute Architecture

### 4.1 GPU Strategy for Face Processing

Face detection and embedding extraction require GPU access. Options:

| Option | Cost | Pros | Cons |
|---|---|---|---|
| **EC2 Spot g4dn.xlarge** | ~$0.16/hr (spot) vs $0.526/hr (on-demand) | Cheapest GPU; 70% savings on spot | Spot can be interrupted; need handling |
| **ECS Fargate (no GPU)** | Standard Fargate pricing | Simple; no instance management | CPU-only; 10-50x slower for embeddings |
| **Lambda (no GPU)** | Pay-per-invocation | Zero idle cost | No GPU; 15min timeout; cold starts |

**Recommended: EC2 Spot g4dn.xlarge for face processing**

- **g4dn.xlarge:** 1 NVIDIA T4 GPU (16GB), 4 vCPU, 16GB RAM
- **Spot pricing:** ~$0.16/hr (Mumbai), 70% cheaper than on-demand
- **Usage pattern:** Spin up when a photographer uploads an event, process all photos, shut down. A 10,000-photo event takes ~15 minutes; cost = ~$0.04 per event.
- **Spot interruption handling:** Use Celery task checkpointing; if interrupted, remaining tasks are re-queued to a new instance.

```python
# Celery worker on GPU instance
# Launched via EC2 Auto Scaling Group (min=0, max=2) with spot fleet

# User data script for GPU instance
#!/bin/bash
# Install NVIDIA drivers and container toolkit
nvidia-smi  # verify GPU
docker run -d --gpus all \
  -e CELERY_BROKER_URL=$REDIS_URL \
  -e DATABASE_URL=$DB_URL \
  platform-celery-worker:latest \
  celery -A app.tasks.celery_app worker -Q face_processing -c 2
```

### 4.2 Auto-Scaling Configuration

**Frontend (ECS Fargate):**
- Min: 2 tasks, Max: 6 tasks
- Scale on: CPU utilization > 70% or request count > 1000/min
- Scale-in cooldown: 300 seconds

**Backend API (ECS Fargate):**
- Min: 2 tasks, Max: 8 tasks
- Scale on: CPU utilization > 60% or request latency P95 > 500ms
- Scale-in cooldown: 300 seconds

**GPU Workers (EC2 Spot):**
- Min: 0, Max: 2
- Scale on: Celery queue depth (face_processing queue > 100 tasks)
- Scale to zero when queue is empty for 10 minutes (cost optimization)

---

## 5. Database Setup

### 5.1 RDS PostgreSQL with pgvector

```hcl
resource "aws_db_instance" "main" {
  identifier             = "platform-db"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t4g.medium"  # 2 vCPU, 4GB RAM
  allocated_storage      = 100               # GB (gp3)
  max_allocated_storage  = 500               # auto-scale up to 500GB
  storage_type           = "gp3"
  storage_encrypted      = true

  db_name  = "photoshare"
  username = "admin"
  password = var.db_password

  multi_az               = false  # single AZ for cost (enable in production at scale)
  publicly_accessible    = false
  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.private.name

  backup_retention_period = 7
  backup_window          = "03:00-04:00"      # UTC (8:30 AM IST)
  maintenance_window     = "Sun:04:00-Sun:05:00"

  parameter_group_name = aws_db_parameter_group.pgvector.name

  tags = { Environment = "production" }
}

resource "aws_db_parameter_group" "pgvector" {
  family = "postgres16"
  name   = "platform-pgvector"

  parameter {
    name  = "shared_preload_libraries"
    value = "vector"
  }

  # Tuning for photo workload
  parameter {
    name  = "work_mem"
    value = "64MB"
  }
  parameter {
    name  = "maintenance_work_mem"
    value = "256MB"
  }
  parameter {
    name  = "effective_cache_size"
    value = "3GB"  # 75% of 4GB RAM
  }
}
```

### 5.2 pgvector Index Tuning

```sql
-- HNSW index for face embedding similarity search
-- Tuned for the expected scale: <100K embeddings per event
CREATE INDEX idx_face_embeddings_vector ON face_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (
        m = 16,                 -- connections per layer (default 16)
        ef_construction = 64    -- build-time search breadth (default 64)
    );

-- At query time, increase ef_search for better recall
SET hnsw.ef_search = 100;  -- default 40; higher = better recall, slower
```

**Expected performance:**
- 10,000 embeddings: < 5ms for top-5 nearest neighbors
- 100,000 embeddings: < 20ms for top-5 nearest neighbors

### 5.3 Connection Pooling

Use PgBouncer as a connection pooler between the application and RDS:

```yaml
# PgBouncer configuration (runs as sidecar container)
[databases]
photoshare = host=platform-db.xxxxx.ap-south-1.rds.amazonaws.com port=5432 dbname=photoshare

[pgbouncer]
pool_mode = transaction
max_client_conn = 200
default_pool_size = 20
min_pool_size = 5
reserve_pool_size = 5
```

---

## 6. Container Architecture

### 6.1 Docker Images

```
platform-frontend          # Next.js application
platform-backend           # FastAPI application
platform-celery-worker     # Celery worker (CPU tasks)
platform-celery-gpu        # Celery worker (GPU tasks, includes CUDA)
platform-tusd              # tusd upload server
platform-pgbouncer         # PgBouncer connection pooler
```

### 6.2 Docker Compose (Local Development)

```yaml
version: "3.8"

services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
      - NEXT_PUBLIC_MOCK_API=false
    depends_on:
      - backend

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/photoshare
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    depends_on:
      - db
      - redis

  tusd:
    image: tusproject/tusd:latest
    ports:
      - "1080:1080"
    command: >
      -s3-bucket platform-uploads
      -s3-endpoint https://s3.ap-south-1.amazonaws.com
      -hooks-http http://backend:8000/api/v1/upload/hook
      -hooks-enabled-hooks post-finish,post-terminate
    depends_on:
      - backend

  celery-worker:
    build: ./backend
    command: celery -A app.tasks.celery_app worker -Q photo_processing,notifications -c 4
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/photoshare
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      - db
      - redis

  celery-beat:
    build: ./backend
    command: celery -A app.tasks.celery_app beat --loglevel=info
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/1
    depends_on:
      - redis

  db:
    image: pgvector/pgvector:pg16
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=photoshare
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

### 6.3 ECS Task Definitions (Production)

```json
{
  "family": "platform-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com/platform-backend:latest",
      "portMappings": [{ "containerPort": 8000 }],
      "environment": [
        { "name": "ENVIRONMENT", "value": "production" }
      ],
      "secrets": [
        { "name": "DATABASE_URL", "valueFrom": "arn:aws:ssm:...:database_url" },
        { "name": "REDIS_URL", "valueFrom": "arn:aws:ssm:...:redis_url" },
        { "name": "SECRET_KEY", "valueFrom": "arn:aws:ssm:...:secret_key" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/platform-backend",
          "awslogs-region": "ap-south-1",
          "awslogs-stream-prefix": "backend"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      }
    }
  ]
}
```

---

## 7. Networking & CDN

### 7.1 VPC Layout

```
VPC: 10.0.0.0/16

  Public Subnets (for ALBs, NAT Gateway):
    10.0.1.0/24 (ap-south-1a)
    10.0.2.0/24 (ap-south-1b)

  Private Subnets (for ECS, RDS, Redis):
    10.0.10.0/24 (ap-south-1a)
    10.0.20.0/24 (ap-south-1b)

  NAT Gateway: 1 (single AZ for cost; multi-AZ for production at scale)
```

### 7.2 CloudFront Configuration

```hcl
resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = ""
  price_class         = "PriceClass_200"  # US, Europe, Asia — excludes expensive regions

  # Origin 1: Next.js frontend (ALB)
  origin {
    domain_name = aws_lb.frontend.dns_name
    origin_id   = "frontend-alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Origin 2: S3 proxies (web-proxy images)
  origin {
    domain_name = aws_s3_bucket.proxies.bucket_regional_domain_name
    origin_id   = "s3-proxies"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.s3.cloudfront_access_identity_path
    }
  }

  # Behavior: Web-proxy images → S3 (cached)
  ordered_cache_behavior {
    path_pattern           = "/photos/*"
    target_origin_id       = "s3-proxies"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 86400     # 24 hours
    max_ttl     = 604800    # 7 days
    compress    = true
  }

  # Default behavior: Everything else → Frontend ALB
  default_cache_behavior {
    target_origin_id       = "frontend-alb"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = true
      headers      = ["Host", "Origin", "Authorization"]
      cookies { forward = "all" }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  # SSL Certificate
  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate.main.arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}
```

---

## 8. CI/CD Pipeline

### 8.1 Pipeline: GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Build and Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_DB: test_photoshare
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
        working-directory: backend
      - run: uv run ruff check .
        working-directory: backend
      - run: uv run mypy app/
        working-directory: backend
      - run: uv run pytest tests/ -v --cov=app --cov-report=xml
        working-directory: backend
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:test@localhost:5432/test_photoshare
          REDIS_URL: redis://localhost:6379/0

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "pnpm"
          cache-dependency-path: frontend/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
        working-directory: frontend
      - run: pnpm lint
        working-directory: frontend
      - run: pnpm type-check
        working-directory: frontend
      - run: pnpm test
        working-directory: frontend

  deploy:
    needs: [test-backend, test-frontend]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/checkout@v4

      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-arn: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: ap-south-1

      - uses: aws-actions/amazon-ecr-login@v2
        id: ecr

      # Build and push backend
      - run: |
          docker build -t ${{ steps.ecr.outputs.registry }}/platform-backend:${{ github.sha }} ./backend
          docker push ${{ steps.ecr.outputs.registry }}/platform-backend:${{ github.sha }}

      # Build and push frontend
      - run: |
          docker build -t ${{ steps.ecr.outputs.registry }}/platform-frontend:${{ github.sha }} ./frontend
          docker push ${{ steps.ecr.outputs.registry }}/platform-frontend:${{ github.sha }}

      # Update ECS services
      - run: |
          aws ecs update-service --cluster platform --service backend --force-new-deployment
          aws ecs update-service --cluster platform --service frontend --force-new-deployment
```

### 8.2 Deployment Strategy

| Component | Strategy | Zero-Downtime |
|---|---|---|
| **Frontend** | ECS rolling update (min 50%, max 200%) | Yes |
| **Backend** | ECS rolling update (min 50%, max 200%) | Yes |
| **Database migrations** | Run via separate ECS task before deployment | Yes (backward-compatible migrations only) |
| **Celery workers** | Graceful shutdown (SIGTERM → finish current task → exit) | Yes |
| **GPU workers** | Terminate and replace (spot instances) | Tasks re-queued automatically |

### 8.3 Database Migration Strategy

```bash
# Run as a one-off ECS task before service deployment
aws ecs run-task \
  --cluster platform \
  --task-definition platform-migration \
  --launch-type FARGATE \
  --overrides '{"containerOverrides": [{"name": "migration", "command": ["alembic", "upgrade", "head"]}]}'
```

**Migration rules:**
- All migrations must be backward-compatible (old code works with new schema)
- No destructive operations in automated migrations (column drops require manual approval)
- Test migrations against a snapshot of production data before applying

---

## 9. Monitoring & Observability

### 9.1 Logging

**Stack:** Application logs → CloudWatch Logs → (optional) CloudWatch Logs Insights for querying

**Log Format:** Structured JSON (via `structlog` in Python, built-in in Next.js)

```json
{
  "timestamp": "2026-09-01T10:30:00Z",
  "level": "info",
  "event": "photo.processed",
  "request_id": "abc-123",
  "photo_id": "uuid-456",
  "event_id": "uuid-789",
  "processing_time_ms": 450,
  "face_count": 3
}
```

**Log Groups:**
- `/ecs/platform-frontend`
- `/ecs/platform-backend`
- `/ecs/platform-celery-worker`
- `/ecs/platform-tusd`

**Retention:** 30 days (CloudWatch) — sufficient for debugging; historical data in metrics.

### 9.2 Metrics & Dashboards

**Custom CloudWatch Metrics:**

| Metric | Source | Alarm Threshold |
|---|---|---|
| `api.request.latency.p95` | Backend middleware | > 2000ms |
| `api.request.error_rate` | Backend middleware | > 5% |
| `upload.throughput.mbps` | tusd + backend | N/A (monitoring only) |
| `photo.processing.queue_depth` | Celery/Redis | > 500 (scale up GPU workers) |
| `photo.processing.duration_seconds` | Celery task | > 60s per photo |
| `face.detection.count_per_photo` | ML pipeline | N/A (monitoring only) |
| `face.quality_rejection_rate` | ML pipeline | > 50% (possible lighting issue) |
| `selfie.match_rate` | Matching service | < 60% (possible model issue) |
| `storage.usage.photographer` | Archival service | > 90% of quota |
| `database.connections.active` | RDS metrics | > 80% of max |
| `database.cpu.utilization` | RDS metrics | > 80% |
| `redis.memory.usage` | ElastiCache metrics | > 80% |

### 9.3 Alerting

**PagerDuty/SNS Alerts (Critical):**
- API error rate > 10% for 5 minutes
- Database CPU > 90% for 10 minutes
- Upload success rate < 95% for 15 minutes
- ECS task count at 0 (service down)

**Email Alerts (Warning):**
- API P95 latency > 2s for 15 minutes
- Processing queue depth > 1000 for 30 minutes
- Storage costs spike > 2x daily average
- Database storage > 80% allocated

### 9.4 Error Tracking

**Sentry** for application error tracking:

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    integrations=[FastApiIntegration(), CeleryIntegration()],
    traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
    environment=settings.environment,
)
```

---

## 10. Security

### 10.1 Network Security

| Layer | Control |
|---|---|
| **VPC** | All compute and data in private subnets; no direct internet access |
| **NAT Gateway** | Outbound internet for private subnet (S3 access, external APIs) |
| **Security Groups** | ALB: 80, 443 from internet. ECS: 8000, 3000 from ALB only. RDS: 5432 from ECS only. Redis: 6379 from ECS only. |
| **S3** | All buckets private; no public access; presigned URLs for all reads |
| **ALB** | HTTPS only; redirect HTTP → HTTPS |

### 10.2 Secrets Management

All secrets stored in **AWS Systems Manager Parameter Store** (SecureString type):

| Secret | Parameter Path |
|---|---|
| Database URL | `/platform/production/database_url` |
| Redis URL | `/platform/production/redis_url` |
| JWT secret key | `/platform/production/secret_key` |
| AWS access keys (for S3) | IAM instance roles (no keys needed) |
| SMS API key | `/platform/production/sms_api_key` |
| Sentry DSN | `/platform/production/sentry_dsn` |

**IAM Roles:** ECS tasks use task execution roles with least-privilege policies. No long-lived access keys.

### 10.3 Data Security

| Data Type | Protection |
|---|---|
| **Passwords** | bcrypt hash (12 rounds) |
| **JWT tokens** | HS256 signed; short-lived access (15min) + rotating refresh (7d) |
| **OTP codes** | Redis with TTL; max 3 attempts |
| **S3 objects** | Server-side encryption (SSE-S3) |
| **RDS** | Encryption at rest (AWS KMS) |
| **Face embeddings** | Stored as vectors in encrypted RDS; not reversible to faces |
| **Guest phone numbers** | Stored in encrypted RDS; accessible only to event photographer |
| **Selfie images** | Temporary; deleted after embedding extraction |

### 10.4 Compliance Considerations

- **India Digital Personal Data Protection Act (DPDPA):** Consent collected at selfie capture step. Face embeddings are mathematical vectors, not biometric templates under most interpretations, but privacy policy must clearly disclose usage.
- **Data localization:** All data stored in AWS Mumbai (ap-south-1). No cross-border transfer.
- **Right to erasure:** Photographer can delete events (hard delete). Guest data is deleted with the event. Archived data counts toward retention policy.

---

## 11. Cost Optimization

### 11.1 Cost Optimization Strategies

| Strategy | Savings | Implementation |
|---|---|---|
| **S3 Intelligent-Tiering** | 20–40% on storage | Auto-transitions objects between access tiers based on usage patterns |
| **S3 Lifecycle → IA after 1 day** | 40% on originals | Originals are rarely re-accessed after initial processing |
| **S3 Glacier IR for archive** | 68% vs Standard | Archived events moved to Glacier IR ($0.004/GB vs $0.023/GB) |
| **EC2 Spot for GPU workers** | 70% vs on-demand | g4dn.xlarge spot ~$0.16/hr vs $0.526/hr on-demand |
| **Scale GPU to zero** | 100% when idle | No GPU instances running between events |
| **Fargate Spot for CPU workers** | 70% vs standard Fargate | Non-critical Celery CPU tasks on Fargate Spot |
| **RDS Reserved Instance (1yr)** | 30–40% | After validating steady-state needs (~3 months in) |
| **CloudFront caching** | 50–80% on S3 egress | Web-proxies served from edge cache instead of S3 |
| **Delete selfie images after processing** | Storage savings | Selfies are temporary; delete after embedding extraction |
| **Proxy deletion on archive** | Storage savings | Web-proxies not needed after event is archived |
| **Single NAT Gateway** | 50% vs multi-AZ | Acceptable risk for startup phase |
| **Single-AZ RDS** | 50% vs Multi-AZ | Enable Multi-AZ when revenue justifies it |

### 11.2 Cost Monitoring

```hcl
# AWS Budget alarm
resource "aws_budgets_budget" "monthly" {
  name         = "platform-monthly"
  budget_type  = "COST"
  limit_amount = "700"  # USD
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = ["alerts@platform.com"]
  }

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_email_addresses = ["alerts@platform.com"]
  }
}
```

### 11.3 Per-Event Cost Breakdown

Estimated cost per event (5,000 photos, 200 guests):

| Cost Center | Amount | Notes |
|---|---|---|
| S3 storage (2 months active) | $1.50 | 75GB originals (IA) + 2.5GB proxies |
| S3 egress (gallery views) | $0.50 | ~5GB proxies served via CloudFront |
| GPU processing | $0.04 | ~15 min on g4dn.xlarge spot |
| RDS (amortized) | $0.10 | Small fraction of shared database |
| CloudFront | $0.10 | CDN cache hits |
| SMS OTP (200 guests) | $0.80 | ~$0.004 per SMS (MSG91 India) |
| **Total per event** | **~$3.00** | |

At ₹999/event pricing, gross margin is approximately **$3 revenue - $3 cost = breakeven at low scale**. Margins improve at scale due to shared infrastructure amortization and S3 storage class optimizations. Storage-based subscription pricing would yield better margins.

---

## 12. Disaster Recovery & Backups

### 12.1 Backup Strategy

| Component | Backup Method | Frequency | Retention |
|---|---|---|---|
| **RDS PostgreSQL** | Automated snapshots | Daily | 7 days |
| **RDS PostgreSQL** | Manual snapshots | Before major deployments | 30 days |
| **S3 (originals)** | S3 versioning (disabled for cost) + cross-region replication (disabled for cost) | N/A | Originals are the photographer's backup; they retain their local copies |
| **Redis** | No backup (ephemeral data: OTPs, cache, queues) | N/A | Acceptable to lose; tasks are re-queued |
| **Application code** | Git (GitHub) | Every push | Indefinite |
| **Infrastructure** | Terraform state (S3 backend) | Every apply | Versioned in S3 |

### 12.2 Recovery Procedures

| Failure Scenario | RTO | RPO | Procedure |
|---|---|---|---|
| **ECS task crash** | < 2 min | 0 | ECS auto-restarts tasks; ALB health check routes around unhealthy tasks |
| **RDS failure** | < 10 min | < 24h | Automated failover (Multi-AZ) or restore from snapshot |
| **Redis failure** | < 5 min | Acceptable loss | ElastiCache auto-recovery; OTPs re-sent; Celery tasks re-queued |
| **S3 bucket deletion** | N/A | N/A | S3 has 99.999999999% durability; MFA delete enabled on buckets |
| **Region failure** | Hours | < 24h | Manual restore in alternate region from S3 and RDS snapshots |
| **Celery worker crash** | < 1 min | 0 | Tasks re-queued automatically; worker auto-scales back |

### 12.3 Data Recovery for Photographers

If a photographer accidentally deletes an event:
- **Within 24 hours:** Support can restore from the most recent RDS snapshot.
- **After 24 hours:** S3 objects may still exist (lifecycle hasn't moved them yet). Database restore from daily snapshot + S3 object listing can reconstruct the event.
- **After archival:** Archived data can be restored (Glacier IR retrieval is near-instant).

---

## 13. Environment Strategy

### 13.1 Environments

| Environment | Purpose | Infrastructure | Data |
|---|---|---|---|
| **Local (Docker Compose)** | Development | All services in containers on developer machine | Mock/seed data |
| **Staging** | Pre-production testing | Scaled-down AWS (single instances, smaller RDS) | Anonymized production subset or synthetic data |
| **Production** | Live users | Full AWS setup per this document | Real data |

### 13.2 Environment Parity

All environments use the same Docker images (different environment variables). Database schema is identical across environments (managed by Alembic migrations).

```
# Environment-specific variables
# Local:      .env.local
# Staging:    AWS SSM /platform/staging/*
# Production: AWS SSM /platform/production/*
```

### 13.3 Staging Environment Cost

Staging runs on minimal infrastructure to keep costs low:

| Service | Staging Config | Monthly Cost |
|---|---|---|
| ECS Fargate | 1 task per service, minimal CPU/RAM | ~$20 |
| RDS | db.t4g.micro (single AZ, no Multi-AZ) | ~$15 |
| ElastiCache | cache.t4g.micro | ~$8 |
| S3 | Same buckets, lifecycle deletes after 7 days | ~$1 |
| **Total staging** | | **~$45/month** |

---

## 14. Infrastructure as Code

### 14.1 Terraform Structure

```
infrastructure/
├── environments/
│   ├── staging/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── terraform.tfvars
│   └── production/
│       ├── main.tf
│       ├── variables.tf
│       └── terraform.tfvars
│
├── modules/
│   ├── vpc/                 # VPC, subnets, NAT, security groups
│   ├── ecs/                 # ECS cluster, services, task definitions
│   ├── rds/                 # RDS instance, parameter groups
│   ├── redis/               # ElastiCache cluster
│   ├── s3/                  # Buckets, lifecycle rules, policies
│   ├── cloudfront/          # CDN distribution
│   ├── alb/                 # Application Load Balancers
│   └── monitoring/          # CloudWatch dashboards, alarms, budgets
│
├── backend.tf               # S3 backend for Terraform state
└── versions.tf              # Provider versions
```

### 14.2 Terraform State

```hcl
# backend.tf
terraform {
  backend "s3" {
    bucket         = "platform-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
```

### 14.3 Initial Setup Checklist

For a single developer getting started, the minimum viable infrastructure setup:

1. **AWS Account** — Create account, enable MFA, create IAM admin user
2. **Domain** — Register domain (or use existing), set up Route 53 hosted zone
3. **Terraform state** — Create S3 bucket + DynamoDB table for state management
4. **VPC** — Run VPC module (subnets, NAT, security groups)
5. **RDS** — Provision PostgreSQL with pgvector
6. **Redis** — Provision ElastiCache (or run on EC2 for lower cost)
7. **S3 Buckets** — Create all buckets with lifecycle rules
8. **ECR** — Create container registries
9. **ECS Cluster** — Create cluster, deploy backend and frontend services
10. **ALB** — Create load balancers, configure target groups
11. **CloudFront** — Create distribution, configure origins
12. **ACM** — Request SSL certificates
13. **SSM** — Store all secrets in Parameter Store
14. **CI/CD** — Configure GitHub Actions with OIDC role assumption
15. **Monitoring** — Set up CloudWatch dashboards and alarms
16. **Budget** — Set monthly budget alarm

**Estimated setup time:** 2–3 days for a developer familiar with AWS and Terraform.

---

*End of Infrastructure & DevOps Component Document v1.0*
