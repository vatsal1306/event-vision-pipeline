#!/usr/bin/env bash
# Run on the EC2 host via SSH from GitHub Actions (INF-006).
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/event-vision-pipeline}"
TARGET_SHA="${1:?Usage: deploy-ec2.sh <git-sha>}"

cd "$REPO_DIR"

CURRENT_SHA="$(git rev-parse HEAD)"
if [ "$CURRENT_SHA" = "$TARGET_SHA" ]; then
  echo "Already deployed commit ${TARGET_SHA}; skipping build."
  exit 0
fi

echo "Deploying ${CURRENT_SHA} -> ${TARGET_SHA}"
git fetch origin main
git checkout main
git pull --ff-only origin main

docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

if docker compose -f docker-compose.prod.yml exec -T backend test -f alembic.ini 2>/dev/null; then
  echo "Running Alembic migrations..."
  docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head
else
  echo "No alembic.ini yet (BE-003); skipping migrations."
fi

docker image prune -f
echo "Deploy complete at $(git rev-parse --short HEAD)"
