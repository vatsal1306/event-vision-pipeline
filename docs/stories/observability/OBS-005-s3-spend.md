# OBS-005 — Daily S3 size vs storage-account budget

**Type:** Feature  
**Depends on:** OBS-001 (Slack `#spotme-alerts`), OBS-002 (`scripts/slack-ops-alert.sh` or equivalent), INF-002 (bucket names in `.env`)  
**Area:** `scripts/s3-bucket-size.sh`, cron install, optional Prometheus textfile, Grafana panel  
**Python:** none required

## Business outcome

The operator gets a Slack push on `#spotme-alerts` when **total S3 stored bytes** for SpotMe media buckets exceed the cheap-account envelope (**default 350 GB**), *before* the month’s bill surprises them. A Grafana number (optional) shows the last measured GB.

This is **platform S3 spend**, not photographer quota (that is OBS-002 `storage_quota`).

## Purpose

The storage account target is ~$60/year. Originals in Standard-IA are on the order of $0.0125/GB-month; **350 GB** is a conservative tripwire under that envelope plus proxies. Guest **egress** is a separate risk and is **out of scope** (CloudWatch GET/egress analytics would be a later story).

Recursive `aws s3 ls --summarize` on a 15k-photo bucket is **forbidden** (LIST cost and time). Use AWS-provided daily `AWS/S3` `BucketSizeBytes` in CloudWatch. That is **not** the CloudWatch Agent, **not** custom metrics, **not** SNS.

## References (read first)

- `docs/component_observability.md` §7.3, §8.1 `backup_failed` pattern, §12 `SPOTME_S3_BUDGET_GB`
- `docs/component_infrastructure.md` §5 ($60/year, IA)
- `.env.prod.example` — `S3_BUCKET_ORIGINALS`, `S3_BUCKET_PROXIES`, `S3_BUCKET_ASSETS`
- `scripts/postgres-backup.sh` — env loading, logging, cron installer pattern (`scripts/install-postgres-backup-cron.sh`)
- `scripts/slack-ops-alert.sh` from OBS-002

## Out of scope

- CloudWatch Agent on EC2
- Custom CloudWatch metrics
- Per-photographer quota (OBS-002)
- S3 request/egress billing alarms
- Glacier inventory jobs
- Changing lifecycle rules

## Non-negotiables

1. **No** recursive listing of bucket contents to compute size.
2. Slack only when **over budget** (and optionally once per day while over — not every cron hour). Default cron: **once daily** 06:30 IST (after S3’s daily metric typically lands).
3. Channel: `#spotme-alerts`. Use `SLACK_WEBHOOK_ALERTS_URL`. Empty URL → skip Slack, still log GB.
4. Include **originals + proxies + assets**. Do not invent a fourth bucket. If a bucket has no datapoint yet (empty), treat size as 0.
5. Same IAM user as tusd (`AWS_ACCESS_KEY_ID` in app `.env`) must be allowed `cloudwatch:GetMetricStatistics` on `AWS/S3` in the **storage** account. If the current IAM policy cannot read CloudWatch, **extend** `infrastructure/modules/iam-app-user` with the **minimum** action (`cloudwatch:GetMetricStatistics` and if required `cloudwatch:ListMetrics`) on `*`. Do not grant `cloudwatch:PutMetricData`. Run Terraform in the storage account as part of this story if the policy must change.
6. Region `ap-south-1` (buckets are there). `BucketSizeBytes` is in the bucket’s region.

## Implementation plan

### Step 1 — IAM (only if needed)

Read `infrastructure/modules/iam-app-user/main.tf`. If CloudWatch GetMetricStatistics is missing, add it. Apply via existing storage-account Terraform workflow (`infrastructure/README.md`). Do not create a new IAM user.

Verify from the app EC2 after apply:

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/S3 \
  --metric-name BucketSizeBytes \
  --dimensions Name=BucketName,Value="$S3_BUCKET_ORIGINALS" Name=StorageType,Value=StandardStorage \
  --start-time "$(date -u -d '3 days ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 86400 \
  --statistics Average \
  --region ap-south-1
```

S3 IA objects use storage type `StandardIAStorage` (confirm current AWS dimension names). **Sum all storage types that exist** for each bucket (StandardStorage, StandardIAStorage, GlacierInstantRetrievalStorage if archival is on). Missing datapoints = 0, not abort.

Document the storage types queried in the script header.

### Step 2 — `scripts/s3-bucket-size.sh`

Mirror backup script quality: `set -euo pipefail`, `load_env_var`, log to `$REPO_DIR/logs/s3-size.log`.

Logic:

1. Load `AWS_*`, three bucket names, `SLACK_WEBHOOK_ALERTS_URL`, `SPOTME_S3_BUDGET_GB` (default **350** if unset).
2. For each bucket, query `BucketSizeBytes` Average over last 3 days, period 86400, **latest** non-empty datapoint per storage type, sum bytes.
3. `TOTAL_GB` = sum / 1024^3 (print with 1 decimal).
4. Log `originals_gb`, `proxies_gb`, `assets_gb`, `total_gb`, `budget_gb`.
5. If `TOTAL_GB > SPOTME_S3_BUDGET_GB`: Slack via `slack-ops-alert.sh` (or curl) with those numbers. Idempotence: write `$LOG_DIR/s3-budget-last-alert-day` (IST date); if already alerted **today**, skip Slack (still log).
6. Exit 0 on success even when over budget (the alert *is* success). Exit non-zero only on AWS API failure; on API failure also Slack `s3_size_check_failed` (ops), using the same webhook helper, without dumping credentials.

Optional: write Prometheus textfile `/var/lib/node_exporter/textfile/s3_bucket_bytes.prom` **only if** Alloy unix exporter is configured with `textfile` collector. **Do not** introduce node_exporter as a new process. If Alloy unix textfile is awkward, skip the metric and put GB only in Slack + log; a Grafana panel is optional. Prefer: Alloy `prometheus.exporter.unix` textfile directory mounted from e.g. `./observability/textfile/` on the app host, metric:

```text
spotme_s3_bucket_bytes{bucket="originals"} 123
spotme_s3_bucket_bytes{bucket="proxies"} 456
spotme_s3_bucket_bytes{bucket="assets"} 789
```

If this requires non-trivial Alloy changes, **logs + Slack are sufficient** for acceptance; document the metric as skipped.

### Step 3 — Cron installer

`scripts/install-s3-size-cron.sh` modelled on `scripts/install-postgres-backup-cron.sh`:

- User crontab on the app EC2 ubuntu user
- `30 6 * * *` Asia/Kolkata (`TZ=Asia/Kolkata` in cron line)
- `SPOTME_S3_BUDGET_GB` from `.env`

Document in `observability/README.md` and `infrastructure/compute/README.md` (one sentence + script path).

### Step 4 — Env

`.env.prod.example`:

```
# OBS-005 — Slack when originals+proxies+assets exceed this (GiB)
SPOTME_S3_BUDGET_GB=350
```

### Step 5 — Grafana (optional)

If the textfile metric exists, add a stat panel to `app-host.json`: total S3 GB vs 350. No Grafana alert required (Slack already comes from cron). If no metric, skip.

### Step 6 — README

Explain:

- Why not `aws s3 ls --recursive`
- Why CloudWatch `AWS/S3` is allowed (component §7.3)
- How to dry-run: `SPOTME_S3_BUDGET_GB=0 ./scripts/s3-bucket-size.sh` should Slack once, then a second run the same day should not

## Acceptance

- [ ] Script sums three buckets using GetMetricStatistics, never recursive list
- [ ] IAM can actually call the API from the app EC2 (Terraform updated if needed)
- [ ] Over budget → one `#spotme-alerts` per IST day; under budget → log only
- [ ] Cron installed via documented script at 06:30 IST
- [ ] `.env.prod.example` has `SPOTME_S3_BUDGET_GB`
- [ ] API failure → Slack + non-zero exit; Slack failure does not hide the AWS error exit
- [ ] No CloudWatch Agent, no PutMetricData

## Verification

1. SSH app EC2, run the script by hand, read the log line with three GB numbers.
2. Compare originals GB to AWS console S3 bucket size (Storage Lens or bucket Metrics) — same order of magnitude (daily metric lags ~24h; do not require exact match).
3. `SPOTME_S3_BUDGET_GB=0` dry-run: phone push once.
4. Confirm crontab `-l` shows the job.

## Done when

A daily, cheap, LIST-free size check pages Slack when S3 stored bytes exceed the configured GB cap.
