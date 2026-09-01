# Infrastructure (Terraform)

Terraform for the event photo delivery platform. Region: **ap-south-1** (Mumbai).

This directory uses a **single AWS account** with two logical environments — `dev` and `production` — isolated by separate state files in the same S3 bucket.

## Layout

```
infrastructure/
├── bootstrap/                  # One-time setup: state bucket + lock table (local state)
├── environments/
│   ├── dev/                    # backend.hcl for dev state
│   └── production/             # backend.hcl for production state
├── modules/                    # Shared modules (added in INF-002+)
├── backend.tf                  # Partial S3 backend — values via backend.hcl
├── versions.tf                 # Terraform and AWS provider pins
└── README.md
```

**Never commit** `*.tfstate` files or `environments/**/backend.hcl` (gitignored).

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

There are no VPC/ECS/RDS modules. Next storage-account work is **INF-002** (media buckets + IAM), documented in `docs/component_infrastructure.md` v2. App compute is a separate AWS account: **EC2 m6i.xlarge, ap-south-1**.

---

## Environment strategy

| Environment | State key | When to use |
|-------------|-----------|-------------|
| `dev` | `dev/terraform.tfstate` | Experimentation, early integration, cheaper/smaller resources |
| `production` | `production/terraform.tfstate` | Real events and customer-facing workloads |

Both environments share the **storage AWS account** and one state bucket. They are isolated by state file path. This account is **S3 + IAM only** — not ECS/RDS.

When working on infra, always confirm which backend you initialized:

```bash
terraform init -backend-config=environments/dev/backend.hcl -reconfigure
```

Switching environments requires re-init with the other `backend.hcl`.

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
