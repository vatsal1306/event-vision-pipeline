# App EC2 — compute account (INF-004)

Manual console setup for the **compute AWS account**. S3 lives in the **storage account** (INF-002/003); this instance only runs Docker Compose.

**Region:** `ap-south-1` (Mumbai) — required for free same-region EC2 → S3 transfer.

---

## Before you start

| Item | Where |
|------|--------|
| AWS Console login | **Compute account** (not the storage account) |
| SSH key pair | Create or import in `ap-south-1` |
| S3 credentials | From storage account: `terraform output -raw app_env_file_snippet` (INF-003) |
| Domain | `event-vision.example.com` → will point to Elastic IP |

**Cross-account note:** The IAM user (`platform-app-ec2`) lives in the **storage account**. You copy its access key to this EC2. No bucket policy or IAM role on the EC2 is required — the key authenticates directly to S3.

Use separate AWS CLI profiles locally, e.g. `platform` (storage) and `compute` (this account).

---

## 1. Security group

Create `platform-app-sg` in `ap-south-1`:

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | **Your home/office IP only** (`x.x.x.x/32`) | Admin access |
| HTTP | 80 | `0.0.0.0/0` | Caddy → Let's Encrypt HTTP-01 challenge |
| HTTPS | 443 | `0.0.0.0/0` | App traffic (photographers, guests) |

**Do not** add rules for 5432 (Postgres) or 6379 (Redis). They stay inside Docker on localhost.

Update the SSH rule when your IP changes.

---

## 2. Launch the instance

EC2 → Launch instance:

| Setting | Value |
|---------|--------|
| Name | `platform-app` |
| AMI | **Ubuntu Server 24.04 LTS**, 64-bit (**x86**), not ARM |
| Instance type | **`m6i.xlarge`** (4 vCPU, 16 GiB) — not t3/t4g |
| Key pair | Your SSH key |
| Network | Default VPC is fine |
| Subnet | Any public subnet in `ap-south-1` |
| Auto-assign public IP | **Enable** (needed before EIP, or attach EIP immediately) |
| Security group | `platform-app-sg` |
| Storage | **200 GiB gp3**, 3000 IOPS, 125 MB/s throughput |
| Advanced → IAM instance profile | **None** (S3 via access keys in `.env`, not instance role) |

Launch.

---

## 3. Elastic IP

1. EC2 → Elastic IPs → Allocate
2. Associate with `platform-app`
3. Note the IP — e.g. `3.x.x.x`

**Important:** Release the EIP if you terminate the instance, or you pay for an unused IP.

---

## 4. DNS

At your DNS provider (Cloudflare, Namecheap, etc.):

| Type | Name | Value |
|------|------|-------|
| A | `event-vision` | `<Elastic IP>` |

Result: `https://event-vision.example.com` → your EC2.

Caddy (INF-005) will obtain Let's Encrypt certs automatically once DNS propagates.

Update `infrastructure/terraform.tfvars` CORS to include `https://event-vision.example.com` if not already done.

---

## 5. First SSH + base setup

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<ELASTIC_IP>
```

On the instance:

```bash
sudo apt update && sudo apt upgrade -y

# Docker (official convenience script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu

# Docker Compose plugin
sudo apt install -y docker-compose-plugin

# Re-login so docker group applies
exit
```

SSH back in, verify:

```bash
docker --version
docker compose version
```

Optional hardening (INF-008, can do now):

```bash
sudo apt install -y fail2ban unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## 6. App secrets on the EC2

```bash
sudo mkdir -p /opt/platform
sudo nano /opt/platform/.env
```

Paste from your local saved snippet (INF-003) **plus** app secrets you'll add in INF-005:

```bash
# --- S3 (storage account) — from terraform output ---
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-south-1
S3_BUCKET_ORIGINALS=platform-originals-702872201750
S3_BUCKET_PROXIES=platform-proxies-702872201750
S3_BUCKET_ASSETS=platform-assets-702872201750

# --- App (add in INF-005) ---
# DATABASE_URL=postgresql+asyncpg://...
# REDIS_URL=redis://redis:6379/0
# JWT_SECRET=...
# FRONTEND_URL=https://event-vision.example.com
```

```bash
sudo chmod 600 /opt/platform/.env
sudo chown root:root /opt/platform/.env
```

**File on disk, not shell export** — survives reboots. Docker Compose reads this file.

---

## 7. Verify S3 from the EC2 (optional smoke test)

```bash
# Install AWS CLI if needed
sudo apt install -y awscli

# Load vars temporarily for testing only
export $(grep -E '^AWS_|^S3_' /opt/platform/.env | xargs)

aws sts get-caller-identity
aws s3 ls s3://$S3_BUCKET_ORIGINALS/
```

You should see the storage-account IAM user ARN and an empty bucket listing.

---

## 8. What not to do

| Avoid | Why |
|-------|-----|
| `t3.xlarge` / `t4g` | Burstable credits collapse during 15k-file uploads |
| GPU / `g4dn` instances | CPU-only stack; ML is a later machine |
| RDS / ElastiCache | Postgres + Redis run in Docker on this box |
| Opening 5432/6379 | Database must not be internet-facing |
| SSH open to `0.0.0.0/0` | Brute-force risk; restrict to your IP |
| Putting S3 keys in git | Use `/opt/platform/.env` only |

---

## 9. INF-004 acceptance checklist

- [ ] Instance `m6i.xlarge` in **ap-south-1**
- [ ] Ubuntu 24.04 LTS
- [ ] 200 GB gp3 root volume
- [ ] Elastic IP attached
- [ ] Security group: 22 (your IP), 80/443 (world), no 5432/6379
- [ ] DNS A record → EIP
- [ ] Docker + Compose installed
- [ ] `/opt/platform/.env` with S3 credentials (chmod 600)
- [ ] Optional: `aws s3 ls` smoke test passes

**Next:** INF-005 — `docker-compose.prod.yml`, Caddy TLS, tusd, Postgres, Redis, Celery.

---

## Cost ballpark (compute account)

| Resource | Approx |
|----------|--------|
| `m6i.xlarge` on-demand | ~$0.192/hr ≈ **$140/month** if 24/7 |
| 200 GB gp3 | ~$16/month |
| Elastic IP (attached) | Free while attached |

Use Savings Plans or Reserved Instances later if you run 24/7 in production. Stop the instance when not testing to save money.
