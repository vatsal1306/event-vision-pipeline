# Component Document: Infrastructure & DevOps

> **Version:** 2.0  
> **Last Updated:** September 2026  
> **Scope:** Local + one AWS EC2 app server, S3 media, Terraform for cheap AWS resources  
> **Not in scope:** ECS, Fargate, RDS, ElastiCache, ALB, NAT Gateway, CloudFront, GPU instances.

---

## Table of Contents

1. [Overview & two AWS accounts](#1-overview--two-aws-accounts)
2. [What “VPS” means and uplink](#2-what-vps-means-and-uplink)
3. [Recommended app server](#3-recommended-app-server)
4. [Architecture](#4-architecture)
5. [S3 storage (budget account)](#5-s3-storage-budget-account)
6. [Upload path (many photos)](#6-upload-path-many-photos)
7. [Containers on the app server](#7-containers-on-the-app-server)
8. [Database and Redis](#8-database-and-redis)
9. [Networking and TLS](#9-networking-and-tls)
10. [ML placeholder](#10-ml-placeholder)
11. [CI/CD](#11-cicd)
12. [Monitoring](#12-monitoring)
13. [Security](#13-security)
14. [Backups](#14-backups)
15. [Terraform layout](#15-terraform-layout)
16. [Local development](#16-local-development)

---

## 1. Overview & two AWS accounts

| Account | Purpose | Cost posture |
|---------|---------|----------------|
| **Storage / “cheap” account** | S3 media, Terraform state S3 + DynamoDB, IAM user that the app server uses to access S3 | Target **~$60/year**. Watch **S3 GB-month and GET/PUT**. No compute here. |
| **Compute account** | One Ubuntu **EC2** running the whole stack | Separate billing. Size for uploads + CPU image processing, not for AWS managed databases. |

Both accounts use region **ap-south-1 (Mumbai)** so photographer traffic and S3 stay in India and **EC2 → S3 same-region transfer is free**.

**Do not use on the cheap account:** RDS, ElastiCache, ECS, ALB, NAT, CloudFront, GPU.

**Do not run on the app EC2:** InsightFace GPU workers. Face ML is a later decision (another machine or CPU batch). Until then, face Celery tasks are no-ops or stubs.

---

## 2. What “VPS” means and uplink

**VPS** (virtual private server) just means a rented VM. In this project that VM **is an AWS EC2 instance**, not Hetzner/DigitalOcean.

**Uplink for 1–2 photographers (starting stage):**

- **Photographer → EC2:** AWS **inbound** data transfer is **free**. The limit is almost always the photographer’s home/studio ISP (fiber 100–200 Mbps is typical). 300GB of originals at 100 Mbps ≈ **7 hours**. Advise overnight uploads; tus resume handles drops.
- **EC2 → S3 (same region):** **free**. tusd should stream parts to S3; do not hairpin through another region.
- **S3 → guests (downloads):** billed on the **storage account** (egress). Proxies are small; originals are the cost risk. Keep 2-month archival.
- **Do not use t3/t4g burstable** as the upload box: CPU/network credits drain during a 15k-file night and throughput collapses.
- **Same AZ as you like; same region as S3 is mandatory.**

For 1–2 concurrent uploaders, **one** well-networked instance is enough. Browser limit remains **6 parallel tus files**; the server must accept many TCP connections and not fill disk with incomplete tus buffers.

---

## 3. Recommended app server

**Region:** `ap-south-1` (Mumbai). Same region as S3 buckets.

**Instance: `m6i.xlarge`**

| | |
|--|--|
| vCPU | 4 (Intel, non-burstable) |
| RAM | 16 GiB |
| Network | Up to 12.5 Gbps (Nitro); fine for 1–2 studio uplinks |
| Disk | **gp3 200 GB**, 3000 IOPS / 125 MB/s baseline (raise throughput if tusd spills to disk) |
| OS | Ubuntu 24.04 LTS |
| GPU | None |

**Why this size:** Postgres + Redis + Next.js + FastAPI + tusd + several CPU Celery workers for **proxy/watermark** of thousands of JPEGs. `m6i.large` (8 GB) is too tight. Avoid `t3.xlarge` for this workload.

**If proxy generation is too slow** after a 15k upload (CPU bound): scale to **`c6i.2xlarge`** (8 vCPU, 16 GB) in the compute account — still no GPU.

**Elastic IP** so DNS does not change. Security group: 22 from your IP, 80/443 from the world. Postgres/Redis **not** published to the internet.

---

## 4. Architecture

```
Photographer / guest phones
        │  HTTPS
        ▼
┌───────────────────────────────────────┐
│  EC2 m6i.xlarge  Ubuntu  (compute acct)│
│  Caddy (TLS Let's Encrypt)             │
│    ├─ Next.js                          │
│    ├─ FastAPI                          │
│    └─ tusd ──multipart──► S3 (storage acct, ap-south-1)
│  PostgreSQL + pgvector                 │
│  Redis                                 │
│  Celery (CPU): proxy, watermark        │
│  Face queue: stub / disabled           │
└───────────────────────────────────────┘
        │ presigned GET
        ▼
   S3 originals (IA) + proxies (Standard)
```

Guests load **presigned S3 URLs** from the API. No CloudFront in Phase 1.

---

## 5. S3 storage (budget account)

Buckets (names unique per account id):

| Bucket | Class | Contents |
|--------|--------|----------|
| originals | STANDARD → **STANDARD_IA after 7 days** | Full-res uploads |
| proxies | STANDARD | Watermarked WebP |
| assets | STANDARD | Logos, watermarks |
| archive | GLACIER_IR (optional later) | After 2-month event archive |

- Block all public access. Access via **IAM user** on the EC2 (access keys in `/opt/platform/.env`, not in git).
- CORS: `GET`/`PUT`/`HEAD`/`POST` from the app origin (`https://your-domain`).
- Cross-account: storage-account bucket policy allows the compute-account IAM principal (or keys created **in the storage account** and placed on EC2 — simpler for a solo operator: **create the IAM user in the storage account**, put keys on the compute EC2).

**$60/year reality:** that is ~$5/month. Originals in IA are ~$0.0125/GB-month. Stay under ~**300–400 GB** stored or shorten retention. Egress from S3 to the internet is the other risk (guest original downloads).

Terraform state: existing bootstrap bucket + DynamoDB in the **storage account** (pennies).

---

## 6. Upload path (many photos)

Target: **15,000–20,000 files**, 10–30MB each, one photographer at a time (two at most).

| Layer | Setting |
|-------|---------|
| Browser | tus, 5MB chunks, **6 concurrent files**, resume |
| Caddy | `request_body` high; long timeouts (`read_timeout` 1h+) |
| tusd | S3 store, 5MB parts, `max-size` 50MB/file, hooks to FastAPI |
| OS | `nofile` 65535; enough ephemeral disk for in-progress parts |
| FastAPI webhook | idempotent `tus_upload_id`; quota check; enqueue CPU processing |
| Celery | Queue `photo_processing` only; **concurrency 2–3** on 4 vCPU (leave CPU for Postgres/tusd/nginx) |
| S3 | Multipart upload; retry; same region |

Do **not** proxy the entire original through FastAPI. tusd → S3 is the data path.

HEIC convert and WebP proxy run **asynchronously** so upload can finish while processing continues.

---

## 7. Containers on the app server

Single `docker-compose.prod.yml` on the EC2:

- `caddy`
- `frontend` (Next.js)
- `backend` (uvicorn, 2 workers — not 8; leave RAM)
- `tusd`
- `db` (`pgvector/pgvector:pg16`) with volume on gp3
- `redis`
- `celery-worker` (`photo_processing`, `notifications`)
- `celery-beat`

No `celery-gpu` service.

Bind Postgres and Redis to the Docker network only.

---

## 8. Database and Redis

**PostgreSQL 16 + pgvector** in Compose on the EC2. Daily `pg_dump` to the storage-account S3 bucket (gzip). Not RDS.

**Redis 7** in Compose. OTP, Celery, rate limits. Persistence optional (`AOF`); OTP loss is acceptable.

---

## 9. Networking and TLS

- DNS A record → Elastic IP (Route 53 **or** any DNS; Route 53 hosted zone is extra on the cheap account — prefer Cloudflare/Namecheap DNS to save the $0.50/month if the $60 cap is tight).
- Caddy automatic HTTPS.
- Optional subdomain `api.` and `upload.` vs path routing on one host — **one hostname is simpler** (`/`, `/api`, `/files` tus).

---

## 10. ML placeholder

The app server is **CPU-only**. Do not install CUDA or load R100 in production Compose.

- `detect_faces_task`: no-op success or skip enqueue until a later ML host exists.
- Guest selfie API: return a controlled stub (`no_match` / not implemented) **or** wire only after ML stories run on a different machine.

ML code still lives in `backend/app/ml/` for future use (see `docs/component_ai_ml.md`).

---

## 11. CI/CD

- GitHub Actions: lint/test on PR (Postgres service container). **No ECR/ECS deploy.**
- Production: `git pull` on EC2 + `docker compose build && up -d`, or Actions **SSH** to the instance.
- Migrations: `docker compose exec backend alembic upgrade head` on the server.

---

## 12. Monitoring

- `docker compose logs`, Ubuntu `journalctl`
- Disk alarm: gp3 > 80% (tus + Postgres)
- Optional: CloudWatch agent on EC2 (compute account) for disk/CPU — skip if you watch manually
- Sentry on the app if DSN set
- **Storage account:** S3 Storage Lens or a monthly bucket-size check so you do not blow $60/year

---

## 13. Security

- SG: 22 restricted; 80/443 open; 5432/6379 closed
- Fail2ban on SSH
- Unattended-upgrades
- Secrets in `/opt/platform/.env` (600)
- S3 IAM: `s3:PutObject/GetObject/AbortMultipart` on the four buckets only
- JWT secret, DB password on the box only

---

## 14. Backups

| Data | Method |
|------|--------|
| Postgres | Daily dump → S3 `s3://.../backups/pg/` |
| S3 originals | 11 nines durability; lifecycle IA |
| Redis | No backup |
| Compose config | Git |

Restore: new EC2 + compose + `pg_restore` + same IAM/S3.

---

## 15. Terraform layout

Terraform **only** what is cheap and repetitive in the **storage account**:

- State backend (INF-001, done)
- S3 buckets, encryption, lifecycle, CORS, public access block
- IAM user + policy for the app server

**EC2 may be Terraform in the compute account or clicked in console** — one instance; document AMI, type `m6i.xlarge`, gp3 200GB, EIP, SG. Prefer a small `infrastructure/compute/` module later if desired.

**Not Terraform:** RDS, ECS, ALB, CloudFront, ElastiCache, GPU ASG.

```
infrastructure/
├── bootstrap/           # state bucket + lock (storage account)
├── modules/s3/
├── modules/iam-app-user/
└── environments/storage/  # buckets + IAM
```

---

## 16. Local development

Same Compose as production, with MinIO **or** real S3 from `.env`. Dummy OTP `123456` / log OTP. No AWS compute required on a laptop.

---

*End of Infrastructure & DevOps Component Document v2.0*
