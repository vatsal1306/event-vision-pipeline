#!/usr/bin/env bash
# Daily Postgres dump to S3 (INF-007).
# Run on the app EC2 via cron. Requires Docker Compose stack and AWS CLI.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/event-vision-pipeline}"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_DIR/docker-compose.prod.yml}"
LOG_DIR="${LOG_DIR:-$REPO_DIR/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/pg-backup.log}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
S3_PREFIX="${S3_PREFIX:-backups/pg}"
BACKUP_TZ="${BACKUP_TZ:-Asia/Kolkata}"

mkdir -p "$LOG_DIR"

log() {
  echo "[$(TZ="$BACKUP_TZ" date '+%Y-%m-%d %H:%M:%S %Z')] $*" | tee -a "$LOG_FILE"
}

die() {
  log "ERROR: $*"
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

load_env_var() {
  local key="$1"
  local line value

  line="$(grep -E "^${key}=" "$ENV_FILE" | tail -1 || true)"
  [ -n "$line" ] || die "Missing ${key} in ${ENV_FILE}"

  value="${line#*=}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"

  [ -n "$value" ] || die "Empty ${key} in ${ENV_FILE}"
  printf '%s' "$value"
}

require_command docker
require_command aws
require_command gzip

[ -f "$ENV_FILE" ] || die "Env file not found: ${ENV_FILE}"
[ -f "$COMPOSE_FILE" ] || die "Compose file not found: ${COMPOSE_FILE}"

AWS_ACCESS_KEY_ID="$(load_env_var AWS_ACCESS_KEY_ID)"
AWS_SECRET_ACCESS_KEY="$(load_env_var AWS_SECRET_ACCESS_KEY)"
AWS_REGION="$(load_env_var AWS_REGION)"
S3_BUCKET_ORIGINALS="$(load_env_var S3_BUCKET_ORIGINALS)"

export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_DEFAULT_REGION="$AWS_REGION"

BACKUP_DATE="$(TZ="$BACKUP_TZ" date '+%Y-%m-%d')"
OBJECT_KEY="${S3_PREFIX}/${BACKUP_DATE}.sql.gz"
S3_URI="s3://${S3_BUCKET_ORIGINALS}/${OBJECT_KEY}"
TMP_FILE="$(mktemp /tmp/pg-backup-XXXXXX.sql.gz)"
trap 'rm -f "$TMP_FILE"' EXIT

log "Starting Postgres backup for ${BACKUP_DATE}"

if ! docker compose -f "$COMPOSE_FILE" ps --status running --services db 2>/dev/null | grep -qx db; then
  die "Postgres container (db) is not running"
fi

log "Running pg_dump via Docker..."
docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U postgres -d photoshare --no-owner --no-acl \
  | gzip -c > "$TMP_FILE"

DUMP_BYTES="$(wc -c < "$TMP_FILE" | tr -d ' ')"
[ "$DUMP_BYTES" -gt 0 ] || die "pg_dump produced an empty file"

log "Uploading ${DUMP_BYTES} bytes to ${S3_URI}"
aws s3 cp "$TMP_FILE" "$S3_URI" --only-show-errors

log "Pruning backups older than ${RETENTION_DAYS} days from s3://${S3_BUCKET_ORIGINALS}/${S3_PREFIX}/"
CUTOFF_DATE="$(TZ="$BACKUP_TZ" date -d "${RETENTION_DAYS} days ago" '+%Y-%m-%d')"
DELETED=0

while IFS= read -r line; do
  [ -n "$line" ] || continue

  filename="${line##* }"
  backup_date="${filename%.sql.gz}"

  if [[ ! "$backup_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
    continue
  fi

  if [[ "$backup_date" < "$CUTOFF_DATE" ]] || [[ "$backup_date" == "$CUTOFF_DATE" ]]; then
    log "Deleting expired backup ${filename} (date ${backup_date}, cutoff ${CUTOFF_DATE})"
    aws s3 rm "s3://${S3_BUCKET_ORIGINALS}/${S3_PREFIX}/${filename}" --only-show-errors
    DELETED=$((DELETED + 1))
  fi
done < <(aws s3 ls "s3://${S3_BUCKET_ORIGINALS}/${S3_PREFIX}/" 2>/dev/null || true)

log "Backup complete: ${S3_URI} (pruned ${DELETED} expired object(s))"
