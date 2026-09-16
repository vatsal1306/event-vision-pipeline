#!/usr/bin/env bash
# Sync repo + ML deps on the GPU host before face_processing worker starts.
# Invoked by systemd ExecStartPre on every boot/restart of spotme-face-worker.
#
# TODO(OBS-002): On non-zero exit, notify #spotme-alerts (e.g. gpu_sync_failed) so
# jobs do not sit in Redis unnoticed when pull or uv sync fails.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/event-vision-pipeline}"
BACKEND_DIR="${REPO_DIR}/backend"

if [ ! -d "${REPO_DIR}/.git" ]; then
  echo "Git repo not found at ${REPO_DIR}" >&2
  exit 1
fi

cd "$REPO_DIR"

echo "Fetching origin/main..."
git fetch origin main

LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse origin/main)"

if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
  echo "Already on latest main (${LOCAL_SHA}); skipping pull and uv sync."
  exit 0
fi

echo "Updating ${LOCAL_SHA} -> ${REMOTE_SHA}"
git checkout main
git pull --ff-only origin main

cd "$BACKEND_DIR"

if [ -f "$HOME/.local/bin/env" ]; then
  # shellcheck source=/dev/null
  source "$HOME/.local/bin/env"
fi

echo "Running uv sync --extra ml..."
uv sync --extra ml

# Replace CPU wheels from PyPI with CUDA builds (see infrastructure/compute/gpu-host.md).
echo "Installing CUDA PyTorch and onnxruntime-gpu..."
uv pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
uv pip uninstall -y onnxruntime || true
uv pip install onnxruntime-gpu

echo "GPU sync complete at $(git rev-parse --short HEAD)"
