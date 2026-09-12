# GPU ML host — compute account (INF-009)

Manual console setup for a **second** EC2 in the **same compute AWS account** as
`platform-app`. This box runs only the Celery `face_processing` worker. Keep it
**stopped** when idle.

**Region:** `ap-south-1` (Mumbai), **same VPC / subnet family** as `platform-app`.

Do **not** put the GPU worker on the `m6i.xlarge` app host.

---

## Why we keep the 100 GB disk when stopped

Deleting the volume on every stop would save about **$9/month**. Starting from a
blank disk each job would mean reinstalling NVIDIA drivers, CUDA, PyTorch, and
copying ~1 GB of model weights (often **20–40 minutes** extra, billed). We
**stop** (not terminate) the instance so the root volume stays. GPU compute is
$0 while stopped; you only pay the disk.

---

## Cost (Mumbai, on-demand, ballpark)

| Item | Stopped | Running |
|------|---------|---------|
| `g4dn.xlarge` (T4 16 GB) | $0 | ~$0.58/hour |
| 100 GB gp3 | ~$9/month | same |
| VPC / security groups | $0 | $0 |
| NAT Gateway | **do not create** | — |
| Elastic IP on this box | **do not allocate** | — |

A 15k-photo event is typically **$1–2** of GPU time. Guest selfie matching does
not use this host.

---

## IAM user for start/stop (compute account)

Create a **separate** IAM user from the storage-account S3 user. Example name:
`platform-gpu-lifecycle`.

Attach an inline policy from
`infrastructure/compute/gpu-lifecycle-iam-policy.json`. Replace:

- `ACCOUNT_ID` — compute account ID
- `INSTANCE_ID` — `i-…` of this GPU instance (after you launch it)

Required actions:

| Action | Why |
|--------|-----|
| `ec2:DescribeInstances` | Read state (`stopped` / `running` / `stopping`) |
| `ec2:DescribeInstanceStatus` | Optional status checks |
| `ec2:StartInstances` | Boot when the photographer starts face processing |
| `ec2:StopInstances` | Stop after 10 minutes idle |

Create an access key. Put it **only** on the **app** EC2 `.env` as
`AWS_COMPUTE_ACCESS_KEY_ID` / `AWS_COMPUTE_SECRET_ACCESS_KEY`. Never commit it.
Do **not** reuse Terraform/S3 keys.

---

## 1. Security groups

### `platform-ml-gpu-sg` (new)

Same VPC as `platform-app`.

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | Your home/office IP only | First-time setup |
| (no 80/443) | — | — | This host is not public HTTP |

Outbound: default **all** (S3 + Ubuntu updates).

### `platform-app-sg` (edit)

Add **two** inbound rules. Source = `platform-ml-gpu-sg` (the SG id, not `0.0.0.0/0`):

| Type | Port | Source |
|------|------|--------|
| PostgreSQL | 5432 | `platform-ml-gpu-sg` |
| Custom TCP | 6379 | `platform-ml-gpu-sg` |

Do **not** open 5432/6379 to the internet.

---

## 2. Launch the instance (once)

EC2 → Launch instance:

| Setting | Value |
|---------|--------|
| Name | `platform-ml-gpu` |
| AMI | **Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.6** (Ubuntu 22.04, x86) in `ap-south-1`. If that AMI is missing, Ubuntu 24.04 x86 + NVIDIA drivers (see AWS “NVIDIA GRID / Tesla” for `g4dn`). |
| Instance type | **`g4dn.xlarge`** (1× T4 16 GB, 4 vCPU, 16 GB RAM) |
| Key pair | Same SSH key as the app box is fine |
| Network | **Same VPC** as `platform-app` |
| Subnet | A **public** subnet (auto-assign public IP **enabled** so the box can reach S3 without a NAT Gateway). Public IP will change each start — that is OK. |
| Security group | `platform-ml-gpu-sg` |
| Storage | **100 GiB gp3**, 3000 IOPS, 125 MB/s. Delete on termination: **No** (we stop, we do not terminate). |
| IAM instance profile | **None** (S3 via storage-account keys in `.env`) |

Launch. Copy the **instance id** (`i-…`) and the **private IPv4**.

On the **app** instance, copy its **private IPv4** too (`hostname -I` or the EC2 NIC).

---

## 3. App Compose: Postgres and Redis for the GPU

`docker-compose.prod.yml` publishes 5432 and 6379 on the app host. After pulling
this change:

```bash
cd ~/event-vision-pipeline
docker compose -f docker-compose.prod.yml up -d
```

Confirm beat is running (`celery-beat`) — it stops the GPU after idle.

App `.env` additions (see `.env.prod.example`):

```bash
ML_FACE_PROCESSING_ENABLED=true
GPU_INSTANCE_ID=i-0123456789abcdef0
AWS_COMPUTE_ACCESS_KEY_ID=...
AWS_COMPUTE_SECRET_ACCESS_KEY=...
AWS_COMPUTE_REGION=ap-south-1
GPU_IDLE_STOP_MINUTES=10
```

Redeploy/restart `backend`, `celery-worker`, and `celery-beat` so they load the
new env.

---

## 4. First SSH + software on the GPU box

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<GPU_PUBLIC_IP>
```

The public IP exists only while the instance is running.

```bash
sudo apt update && sudo apt install -y git
# NVIDIA driver is included on the Deep Learning AMI. Check:
nvidia-smi
```

Install uv and clone the repo:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

git clone git@github.com:<your-org>/event-vision-pipeline.git ~/event-vision-pipeline
cd ~/event-vision-pipeline/backend
uv sync --extra ml
```

Install **CUDA** PyTorch (replaces the CPU wheel from PyPI):

```bash
uv pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
uv pip uninstall -y onnxruntime || true
uv pip install onnxruntime-gpu
```

Copy model weights into `backend/models/` (rsync from your laptop or from a
private S3 prefix). Same files as local ML-001 setup.

Create `~/event-vision-pipeline/backend/.env` from `.env.gpu.example`. Use the
**app private IP** (not `db` / `redis` Docker names):

```bash
APP_PRIVATE_IP=172.31.x.x   # platform-app private IPv4
DATABASE_URL=postgresql+asyncpg://postgres:APP_POSTGRES_PASSWORD@${APP_PRIVATE_IP}:5432/photoshare
REDIS_URL=redis://${APP_PRIVATE_IP}:6379/0
CELERY_BROKER_URL=redis://${APP_PRIVATE_IP}:6379/1
CELERY_RESULT_BACKEND=redis://${APP_PRIVATE_IP}:6379/2
```

Storage-account `AWS_*` / `S3_BUCKET_*` must match the app (same keys as S3).

```bash
ML_FACE_PROCESSING_ENABLED=true
ML_DEVICE=cuda
```

Do **not** set `GPU_INSTANCE_ID` on the GPU box.

Smoke-test from the GPU host:

```bash
nc -vz "$APP_PRIVATE_IP" 5432
nc -vz "$APP_PRIVATE_IP" 6379
```

Install the worker so it starts on every boot:

```bash
chmod +x ~/event-vision-pipeline/scripts/install-gpu-face-worker.sh
~/event-vision-pipeline/scripts/install-gpu-face-worker.sh
```

---

## 5. Stop the instance (you do this once)

After the worker is healthy:

```bash
sudo systemctl status spotme-face-worker
```

In the AWS console: **Stop instance** (not Terminate). From then on the app
starts and stops it.

---

## 6. What the code does

1. Photographer `POST /api/v1/events/{id}/start-face-processing` returns immediately.
2. Face job is queued on Redis `face_processing`.
3. App Celery (`photo_processing`) runs `ensure_gpu_host_running` → `StartInstances`.
4. GPU boots, systemd starts the face worker, it drains the queue.
5. Every minute, beat runs `stop_idle_gpu_host`. If there is no pipeline lock,
   no clustering lock, and the `face_processing` list is empty for **10 minutes**,
   it calls `StopInstances`.

Laptop: leave `GPU_INSTANCE_ID` empty and run:

```bash
cd backend
uv run celery -A app.tasks.celery_app worker -Q face_processing -c 1
```

---

## 7. INF-009 checklist

- [ ] `g4dn.xlarge` in **ap-south-1**, 100 GB gp3, tag `Name=platform-ml-gpu`
- [ ] Same VPC as `platform-app`; no EIP; no NAT Gateway
- [ ] `platform-ml-gpu-sg` SSH from your IP only
- [ ] App SG: 5432 + 6379 from GPU SG only
- [ ] Compute IAM user with start/stop on this instance id
- [ ] App `.env`: `ML_FACE_PROCESSING_ENABLED=true` + compute keys + `GPU_INSTANCE_ID`
- [ ] GPU `.env` points at app **private IP**; systemd face worker enabled
- [ ] Instance left **stopped** after first setup
- [ ] Guest selfie still works with GPU stopped (CPU on app)
