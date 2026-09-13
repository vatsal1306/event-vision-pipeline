#!/bin/sh
# Apply schema before serving. Idempotent; safe on every container start.
set -eu

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  echo "Running Alembic migrations..."
  alembic upgrade head
fi

exec "$@"
