#!/bin/sh
# Write per-compose-service container RSS to a Prometheus textfile for Alloy.
# Requires: docker CLI, host /sys/fs/cgroup (cgroup v2 memory.current).
# Runs inside the container-metrics compose service every 60s.

set -eu

OUT_DIR="${TEXTFILE_DIR:-/textfile}"
OUT_FILE="${OUT_DIR}/spotme_container_memory.prom"
TMP_FILE="${OUT_FILE}.$$"
KEEP="caddy frontend backend tusd celery-worker celery-beat db redis"

mkdir -p "$OUT_DIR"

{
  echo '# HELP spotme_container_memory_rss_bytes Resident memory per compose service (bytes).'
  echo '# TYPE spotme_container_memory_rss_bytes gauge'

  for cid in $(docker ps -q); do
    service="$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.service" }}' "$cid" 2>/dev/null || true)"
    [ -n "$service" ] || continue
    echo "$KEEP" | tr ' ' '\n' | grep -qx "$service" || continue

    cgroup="$(docker inspect -f '{{ .CgroupPath }}' "$cid" 2>/dev/null || true)"
    [ -n "$cgroup" ] || continue

    mem_file="/sys/fs/cgroup${cgroup}/memory.current"
    [ -f "$mem_file" ] || continue

    bytes="$(cat "$mem_file")"
    echo "spotme_container_memory_rss_bytes{instance=\"spotme-app\",name=\"${service}\"} ${bytes}"
  done
} > "$TMP_FILE"

mv "$TMP_FILE" "$OUT_FILE"
