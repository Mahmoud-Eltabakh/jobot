#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-prod}"

if [[ "$MODE" == "dev" ]]; then
  docker build -f Dockerfile.dev -t jobot:dev .
else
  docker build -t jobot:latest .
fi
docker image prune -f --filter "dangling=true" >/dev/null 2>&1 || true
