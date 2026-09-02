# Infrastructure (Terraform)

Terraform for the event photo delivery platform. Region: **ap-south-1** (Mumbai).

This directory uses a **single AWS account** with two logical environments — `dev` and `production` — isolated by separate state files in the same S3 bucket.

## Layout

```
infrastructure/
├── bootstrap/                  # One-time setup: state bucket + lock table (local state)
├── environments/
│   ├── storage/                # backend.hcl for shared S3 + IAM state (INF-002+)
│   ├── dev/                    # backend.hcl for dev state (reserved for future use)
│   └── production/             # backend.hcl for production state (reserved)
├── modules/
│   ├── s3/                     # Media buckets (INF-002)
│   └── iam-app-user/           # EC2 S3 IAM user (INF-003)
├── backend.tf                  # Partial S3 backend — values via backend.hcl
├── main.tf                     # Root module wiring
├── variables.tf
├── outputs.tf
├── terraform.tfvars.example    # Copy to terraform.tfvars (gitignored)
├── versions.tf                 # Terraform and AWS provider pins
└── README.md
```

**Never commit** `*.tfstate` files, `environments/**/backend.hcl`, or `terraform.tfvars` (gitignored).

**Do commit** `.terraform.lock.hcl` and `*.example` files.

---

## Prerequisites

Install on your machine:

- [Terraform](https://developer.hashicorp.com/terraform/install) `>= 1.9`
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) v2

On macOS:

```bash
brew install terraform awscli
```
- I have installed terraform v1.16.0 on darwin_arm64 and aws cli version aws-cli/2.31.27 

---

## Step 1 — AWS account credentials

You have a new AWS account with no local credentials yet. Set them up once:

### 1a. Secure the root user (console)

1. Sign in to the [AWS Console](https://console.aws.amazon.com/) as the root user.
2. Enable **MFA** on the root account (IAM → Security credentials → Assign MFA).
3. Do **not** use root credentials for day-to-day work or Terraform.

### 1b. Create an IAM user for Terraform

1. IAM → **Users** → **Create user**.
2. User name: `terraform-admin` (or similar).
3. Attach policy: **AdministratorAccess** (fine for a solo bootstrap; tighten later in INF-013).
4. Create user → **Security credentials** → **Create access key** → choose **Command Line Interface**.
5. Save the **Access key ID** and **Secret access key** (shown once).

### 1c. Configure the AWS CLI locally

```bash
aws configure --profile platform
```

Enter when prompted:

| Prompt | Value |
|--------|-------|
| AWS Access Key ID | your access key |
| AWS Secret Access Key | your secret key |
| Default region name | `ap-south-1` |
| Default output format | `json` |

Verify:

```bash
export AWS_PROFILE=platform
aws sts get-caller-identity
```

You should see your account ID and the `terraform-admin` user ARN.

Add to your shell profile (`~/.zshrc`) so you don't have to export every session:

```bash
export AWS_PROFILE=platform
export AWS_REGION=ap-south-1
```

---

## Step 2 — Bootstrap remote state (one time)

Bootstrap creates:

| Resource | Purpose |
|----------|---------|
| S3 bucket `platform-terraform-state-<account-id>` | Stores Terraform state (SSE-S3, no versioning) |
| DynamoDB table `terraform-locks` | State locking (pay per request) |

Bootstrap uses **local state** on your machine — it cannot use the remote backend it is creating.

```bash
cd infrastructure/bootstrap

terraform init
terraform plan
terraform apply
```

Review the plan, then type `yes` to apply.

After apply, note the outputs:

```bash
terraform output state_bucket_name
terraform output -raw backend_config_dev
terraform output -raw backend_config_production
```

---

## Step 3 — Configure backend for each environment

Create `backend.hcl` files from the bootstrap outputs (not committed to git):

**Dev:**

```bash
cd infrastructure/bootstrap
terraform output -raw backend_config_dev > ../environments/dev/backend.hcl
```

Or copy the example and fill in the bucket name:

```bash
cp environments/dev/backend.hcl.example environments/dev/backend.hcl
# Set BUCKET_NAME from: cd infrastructure/bootstrap && terraform output -raw state_bucket_name
```

**Production** (same pattern):

```bash
cd infrastructure/bootstrap
terraform output -raw backend_config_production > ../environments/production/backend.hcl
```

---

## Step 4 — Verify remote backend init

From `infrastructure/`, confirm Terraform can reach the remote backend:

```bash
cd infrastructure

# Dev
terraform init -backend-config=environments/dev/backend.hcl -reconfigure

# Production (when you need it)
terraform init -backend-config=environments/production/backend.hcl -reconfigure
```

A successful init prints `Terraform has been successfully initialized!` with no errors about S3 or DynamoDB access.

---

## Step 5 — S3 media buckets (INF-002)

Shared storage resources (S3 buckets) use a **single Terraform state** (`storage/terraform.tfstate`), not separate dev/prod bucket sets. Both a dev EC2 and a production EC2 can point at the same buckets — photos are isolated by `event_id` in key prefixes.

### 5a. Configure the storage backend

```bash
cd infrastructure/bootstrap
terraform output -raw backend_config_storage > ../environments/storage/backend.hcl
```

### 5b. Set CORS origins

```bash
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set your production, dev, and localhost origins
```

### 5c. Init, plan, apply

```bash
cd infrastructure
terraform init -backend-config=environments/storage/backend.hcl -reconfigure
terraform plan
terraform apply
```

After apply, note bucket names:

```bash
terraform output bucket_names
```

| Bucket | Class | Key prefixes |
|--------|-------|--------------|
| `platform-originals-<account_id>` | STANDARD → STANDARD_IA after 7 days | `originals/{event_id}/...`, `backups/pg/` (INF-007) |
| `platform-proxies-<account_id>` | STANDARD | `proxies/{event_id}/...` |
| `platform-assets-<account_id>` | STANDARD | `logos/`, `watermarks/`, `selfies/` |

All buckets: SSE-S3 encryption, public access blocked. CORS on originals + proxies (for presigned GET via browser fetch / PWA service worker). Archive bucket (GLACIER_IR) deferred to BE-018.

### 5d. Monitor S3 spend (~$60/year budget)

Check monthly so storage + egress do not blow the budget:

**AWS Console:** S3 → Storage Lens (free dashboard) → total bytes per bucket.

**CLI (total size per bucket):**

```bash
export AWS_PROFILE=platform
for bucket in $(aws s3api list-buckets --query 'Buckets[].Name' --output text); do
  bytes=$(aws cloudwatch get-metric-statistics \
    --namespace AWS/S3 \
    --metric-name BucketSizeBytes \
    --dimensions Name=BucketName,Value=$bucket Name=StorageType,Value=StandardStorage \
    --start-time $(date -u -v-2d +%Y-%m-%dT00:00:00Z 2>/dev/null || date -u -d '2 days ago' +%Y-%m-%dT00:00:00Z) \
    --end-time $(date -u +%Y-%m-%dT00:00:00Z) \
    --period 86400 \
    --statistics Average \
    --query 'Datapoints[0].Average' --output text 2>/dev/null)
  echo "$bucket: ${bytes:-unknown} bytes (Standard; check IA separately)"
done
```

Simpler alternative — list objects with human-readable sizes (slow on large buckets):

```bash
aws s3 ls s3://platform-originals-YOUR_ACCOUNT_ID --recursive --summarize | tail -2
```

**Targets:** stay under ~300–400 GB stored in IA. Egress (guest original downloads) is the other cost risk.

---

## Step 6 — IAM user for app EC2 (INF-003)

Creates IAM user `platform-app-ec2` in the **storage account** with least-privilege S3 access to the three media buckets only (no `s3:*` on `*`, no access to the Terraform state bucket).

```bash
cd infrastructure
terraform init -backend-config=environments/storage/backend.hcl -reconfigure
terraform plan    # should show IAM user + policy + access key
terraform apply
```

### 6a. Copy credentials to the EC2

After apply, print the `.env` block (contains secrets — do not commit or paste in chat):

```bash
terraform output -raw app_env_file_snippet
```

On the app EC2 (after INF-004), append those lines to `/opt/platform/.env`:

```bash
sudo mkdir -p /opt/platform
sudo nano /opt/platform/.env   # paste the lines, save
sudo chmod 600 /opt/platform/.env
sudo chown root:root /opt/platform/.env
```

Docker Compose reads this file automatically — **do not** `export` them in your shell profile. A file on disk survives reboots; shell exports do not (unless you add them to `.bashrc`, which you should not for secrets).

| Variable | Purpose |
|----------|---------|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Authenticate tusd, FastAPI, and Celery to S3 in the storage account |
| `AWS_REGION` | Must be `ap-south-1` (same region as buckets and EC2) |
| `S3_BUCKET_ORIGINALS` | Full-res uploads (`originals/...`) and Postgres backups (`backups/pg/`) |
| `S3_BUCKET_PROXIES` | Watermarked WebP gallery images |
| `S3_BUCKET_ASSETS` | Studio logos, watermarks, guest selfies during processing |

After updating `.env`, restart services that use S3:

```bash
cd /opt/platform   # or wherever compose lives
docker compose restart backend tusd celery-worker
```

### 6b. Access key rotation

The secret is stored in Terraform state (encrypted in the remote S3 backend). Rotate periodically or if exposed:

1. Generate a new key:
   ```bash
   cd infrastructure
   terraform apply -replace='module.iam_app_user.aws_iam_access_key.app'
   ```
2. Copy the new snippet: `terraform output -raw app_env_file_snippet`
3. Replace the AWS lines in `/opt/platform/.env` on the EC2
4. Restart `backend`, `tusd`, `celery-worker`
5. The old key is invalidated when Terraform replaces it

AWS allows two active keys per user; for zero-downtime rotation, create a second key in the console first, update `.env`, restart, then delete the old key — or use the replace flow above (brief restart window).

---

## Verify bootstrap and backend status

Use these commands to see what has been applied and which backends exist.

**Bootstrap applied?**

```bash
cd infrastructure/bootstrap
terraform output state_bucket_name    # fails if bootstrap never applied
aws s3 ls | grep platform-terraform-state
aws dynamodb describe-table --table-name terraform-locks --region ap-south-1 --query 'Table.TableStatus'
```

**Which remote state files exist?** (shows dev, production, and/or storage)

```bash
cd infrastructure/bootstrap
STATE_BUCKET=$(terraform output -raw state_bucket_name)
aws s3 ls "s3://${STATE_BUCKET}/"
```

You might see only `dev/terraform.tfstate` if you initialized dev but never applied storage or production.

**Which backend is currently active locally?**

```bash
cd infrastructure
cat .terraform/terraform.tfstate | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('backend',{}).get('config',{}), indent=2))"
```

**Which local backend.hcl files exist?** (not in git)

```bash
ls -la infrastructure/environments/*/backend.hcl 2>/dev/null || echo "No backend.hcl files created yet"
```

---

There are no VPC/ECS/RDS modules. Next work is **INF-004** (app EC2 in the compute account). Storage account Terraform (INF-002 + INF-003) is complete after Step 6.

---

## Environment strategy

| State key | Purpose | When to use |
|-----------|---------|-------------|
| `storage/terraform.tfstate` | **S3 media buckets + IAM** (shared across app envs) | INF-002, INF-003 — apply once |
| `dev/terraform.tfstate` | Reserved for future dev-only infra | Not used yet |
| `production/terraform.tfstate` | Reserved for future prod-only infra | Not used yet |

**Why one bucket set, not dev + prod buckets?** At early stage, duplicating three S3 buckets doubles storage cost and complexity for little benefit. Dev and production EC2 instances (when both exist) share the same buckets; isolation is by `event_id` in object keys. If you later need hard isolation, add `-dev` / `-prod` bucket suffixes via a second Terraform workspace.

Both environments share the **storage AWS account** and one state bucket for Terraform remote state. This account is **S3 + IAM only** — not ECS/RDS.

When working on storage infra:

```bash
terraform init -backend-config=environments/storage/backend.hcl -reconfigure
```

The `dev/` and `production/` backend configs remain available if you later need environment-specific Terraform state.

---

## Who can run Terraform

| Actor | Access needed |
|-------|---------------|
| You (local dev) | IAM user with S3 + DynamoDB permissions on the state bucket/table, plus permissions for resources being managed |
| CI/CD (later, INF-006) | GitHub Actions for tests; production deploy is **SSH to EC2**, not OIDC-to-ECS |

State bucket and lock table are created once in bootstrap. All future `terraform apply` runs (local or CI) read/write state through this backend.

---

## Destroying bootstrap (danger)

```bash
cd infrastructure/bootstrap
terraform destroy
```

This deletes the state bucket and lock table. **Only do this if you have migrated or no longer need any Terraform state.** All environment state files in the bucket will be lost.
