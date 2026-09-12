#!/usr/bin/env bash
# Install daily Postgres backup cron on the app EC2.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/event-vision-pipeline}"
BACKUP_SCRIPT="${REPO_DIR}/scripts/postgres-backup.sh"

if [ ! -f "$BACKUP_SCRIPT" ]; then
  echo "Backup script not found: ${BACKUP_SCRIPT}" >&2
  exit 1
fi

chmod +x "$BACKUP_SCRIPT"

# 22:00 UTC = 03:30 IST — after Celery archival (02:00 IST) and before morning traffic.
# EC2 system clock is UTC; the backup script names files using Asia/Kolkata.
CRON_MARKER="postgres-backup"
CRON_LINE="0 22 * * * REPO_DIR=${REPO_DIR} ${BACKUP_SCRIPT} # ${CRON_MARKER}"

EXISTING="$(crontab -l 2>/dev/null || true)"
FILTERED="$(printf '%s\n' "$EXISTING" | grep -Fv "$CRON_MARKER" || true)"

{
  printf '%s\n' "$FILTERED"
  printf '%s\n' "$CRON_LINE"
} | sed '/^$/d' | crontab -

echo "Installed daily Postgres backup cron (22:00 UTC / 03:30 IST)."
echo "Logs: ${REPO_DIR}/logs/pg-backup.log"
crontab -l | grep "$CRON_MARKER" || true
