#!/bin/sh
# Write per-compose-service container RSS to a Prometheus textfile for Alloy.
# Ubuntu 24.04 / cgroup v2: Docker API may not expose .CgroupPath — resolve via
# container ID scope name or /proc/<pid>/cgroup (requires pid:host on the service).

set -eu

OUT_DIR="${TEXTFILE_DIR:-/textfile}"
OUT_FILE="${OUT_DIR}/spotme_container_memory.prom"
TMP_FILE="${OUT_FILE}.$$"
KEEP="caddy frontend backend tusd celery-worker celery-beat db redis"

mkdir -p "$OUT_DIR"

memory_file_for_container() {
  cid="$1"
  full_id="$(docker inspect -f '{{.Id}}' "$cid" 2>/dev/null | sed 's/^sha256://')"
  [ -n "$full_id" ] || return 1

  for mem_file in \
    "/sys/fs/cgroup/system.slice/docker-${full_id}.scope/memory.current" \
    "/sys/fs/cgroup/docker/${full_id}/memory.current"
  do
    if [ -f "$mem_file" ]; then
      echo "$mem_file"
      return 0
    fi
  done

  pid="$(docker inspect -f '{{.State.Pid}}' "$cid" 2>/dev/null || echo 0)"
  if [ "$pid" -gt 0 ] && [ -r "/proc/${pid}/cgroup" ]; then
    cgroup_rel="$(awk -F: '{print $3}' "/proc/${pid}/cgroup" | head -n 1)"
    if [ -n "$cgroup_rel" ] && [ -f "/sys/fs/cgroup${cgroup_rel}/memory.current" ]; then
      echo "/sys/fs/cgroup${cgroup_rel}/memory.current"
      return 0
    fi
  fi

  return 1
}

{
  echo '# HELP spotme_container_memory_rss_bytes Resident memory per compose service (bytes).'
  echo '# TYPE spotme_container_memory_rss_bytes gauge'

  for cid in $(docker ps -q); do
    service="$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.service" }}' "$cid" 2>/dev/null || true)"
    [ -n "$service" ] || continue
    echo "$KEEP" | tr ' ' '\n' | grep -qx "$service" || continue

    mem_file="$(memory_file_for_container "$cid" || true)"
    [ -n "$mem_file" ] || continue

    bytes="$(cat "$mem_file")"
    echo "spotme_container_memory_rss_bytes{instance=\"spotme-app\",name=\"${service}\"} ${bytes}"
  done
} > "$TMP_FILE"

mv "$TMP_FILE" "$OUT_FILE"
