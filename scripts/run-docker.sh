#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-prod}"
COMPOSE_FILE="docker-compose.yml"

if [[ "$MODE" == "--dev" || "$MODE" == "dev" ]]; then
  COMPOSE_FILE="docker-compose.dev.yml"
elif [[ "$MODE" == "--host-ollama" || "$MODE" == "host-ollama" ]]; then
  COMPOSE_FILE="docker-compose.host-ollama.yml"
fi

docker compose -f "$COMPOSE_FILE" up --build -d
docker image prune -f --filter "dangling=true" >/dev/null 2>&1 || true

echo "Jobot is running at http://localhost:8000 (Mode: $MODE)"
