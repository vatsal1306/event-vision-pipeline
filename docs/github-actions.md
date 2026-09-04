# GitHub Actions (INF-006)

CI/CD for this monorepo. **No auto-deploy on push to `main`.**

## Workflows

| File | Trigger | Purpose |
|------|---------|---------|
| `.github/workflows/backend-ci.yml` | PR → `main`, `backend/**` paths | Ruff lint + pytest with coverage (no AWS) |
| `.github/workflows/ec2-deploy.yml` | `workflow_dispatch` | Start EC2 if needed → SSH deploy `main` |
| `.github/workflows/ec2-stop.yml` | `workflow_dispatch` | Stop EC2 (not terminate) |

## AWS auth (deploy / stop)

Uses **GitHub OIDC** → `sts:AssumeRoleWithWebIdentity`. No long-lived AWS access keys in GitHub.

- Repository variable: `AWS_ROLE_ARN` (compute account IAM role ARN)
- Workflows need `permissions: id-token: write`

OIDC covers **EC2 start/stop/describe only**. SSH deploy still uses GitHub secrets `EC2_HOST` and `EC2_SSH_PRIVATE_KEY` (EC2 key pair `.pem`, not IAM).

## EC2 instance lookup

Instance resolved by tag **`Name=platform-app`** in `ap-south-1` via `aws ec2 describe-instances`. If multiple match, the newest by `LaunchTime` is used. Prefer exactly one instance with this tag.

## Deploy flow (`ec2-deploy.yml`)

1. Checkout `main` at workflow SHA.
2. Resolve instance by name tag; fail if not found.
3. If `stopped` → start + wait `instance-running` + `instance-status-ok`.
4. If `stopping` → wait stopped → start → wait running.
5. If already `running`, skip start.
6. Wait up to 10 min for SSH (`BatchMode`, 15s retry).
7. Run `scripts/deploy-ec2.sh <sha>` over SSH on `~/event-vision-pipeline`.
8. Script skips Docker rebuild if EC2 `git rev-parse HEAD` already equals target SHA.
9. Otherwise `git pull`, `docker compose -f docker-compose.prod.yml build && up -d`.
10. Alembic runs only if `backend/alembic.ini` exists inside container (BE-003).
11. Health check: `https://spotme.hpklabs.ai/health` must return `{"status":"ok"}`.

`.env` on EC2 is never modified by deploy.

## Stop flow (`ec2-stop.yml`)

Find instance by same tag; `stop-instances` unless already stopped/stopping.

## Backend CI (`backend-ci.yml`)

- Python 3.10 via `uv`, deps from `backend/pyproject.toml` (`--extra dev`)
- `ruff check` + `ruff format --check` on `app/` and `tests/`
- `pytest --cov=app` with 60% fail-under (`app/ml/*` omitted from coverage)
- Uploads `coverage.xml` artifact

## Related files

- `scripts/deploy-ec2.sh` — remote deploy script (stdin over SSH)
- `docker-compose.prod.yml` — production stack on EC2
- `infrastructure/compute/README.md` — EC2 / domain context

## Constraints for agents

- Do not add `on: push` deploy to `main` unless explicitly requested.
- Do not put AWS access keys in workflows; use OIDC role.
- Deploy workflows target **compute account** EC2 only (not storage-account Terraform).
- Production app URL: `https://spotme.hpklabs.ai`
