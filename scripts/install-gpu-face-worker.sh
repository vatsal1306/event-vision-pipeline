#!/usr/bin/env bash
# Install the GPU face worker systemd unit so it starts when the instance boots.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/event-vision-pipeline}"
UNIT_SRC="${REPO_DIR}/infrastructure/compute/spotme-face-worker.service"
UNIT_DST="/etc/systemd/system/spotme-face-worker.service"

if [ ! -f "$UNIT_SRC" ]; then
  echo "Unit file not found: ${UNIT_SRC}" >&2
  exit 1
fi

sudo cp "$UNIT_SRC" "$UNIT_DST"
sudo systemctl daemon-reload
sudo systemctl enable spotme-face-worker.service
sudo systemctl restart spotme-face-worker.service
sudo systemctl --no-pager --full status spotme-face-worker.service || true

echo "Installed spotme-face-worker. It will start automatically on boot (after GPU start)."
