#!/usr/bin/env bash
# Jobot Management Automation Script (Linux / macOS / WSL)
# Automates environment setup, testing, Docker builds, Compose stack, and Kubernetes deployment.

set -euo pipefail

show_help() {
    cat << EOF
============================================================
              JOBOT AUTOMATION CLI (Bash)
============================================================
Usage: ./scripts/manage.sh <command>

Available Commands:
  setup                  - Initialize virtual environment, install requirements and Playwright
  test                   - Run complete pytest test suite with coverage
  dev                    - Launch local FastAPI development server with hot reload
  docker-build           - Build production Docker image (jobot:latest)
  docker-up              - Build & start production Docker Compose stack (Jobot + Ollama)
  docker-up-host-ollama  - Build & start Jobot connected to Ollama running on host machine
  docker-down            - Stop Docker Compose stack
  k8s-deploy             - Apply all Kubernetes manifests from k8s/ directory
  backup                 - Create a timestamped backup archive of data/ (SQLite + Chroma)
  help                   - Display this help message
============================================================
EOF
}

CMD=${1:-help}

case "$CMD" in
    setup)
        echo "==> Setting up Python virtual environment..."
        if [ ! -d ".venv" ]; then
            python3 -m venv .venv
        fi
        echo "==> Installing dependencies..."
        .venv/bin/pip install -r requirements.txt
        echo "==> Installing Playwright Chromium browser..."
        .venv/bin/playwright install chromium
        echo "==> Setup complete!"
        ;;
    test)
        echo "==> Running test suite..."
        .venv/bin/pytest -v
        ;;
    dev)
        echo "==> Launching Jobot development server on http://localhost:8000..."
        .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
        ;;
    docker-build)
        echo "==> Building production Docker image (jobot:latest)..."
        docker build -t jobot:latest .
        echo "==> Docker image built successfully!"
        ;;
    docker-up)
        echo "==> Building & starting Docker Compose stack..."
        docker compose -f docker-compose.yml up --build -d
        echo "==> Jobot stack running at http://localhost:8000"
        ;;
    docker-up-host-ollama)
        echo "==> Building & starting Jobot connected to Host Ollama..."
        docker compose -f docker-compose.host-ollama.yml up --build -d
        echo "==> Jobot stack running at http://localhost:8000 (connected to host Ollama)"
        ;;
    docker-down)
        echo "==> Stopping Docker Compose stack..."
        docker compose down
        ;;
    k8s-deploy)
        echo "==> Deploying Jobot to Kubernetes namespace 'jobot'..."
        kubectl apply -f k8s/jobot-all.yaml
        echo "==> Manifests applied successfully!"
        ;;
    backup)
        TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
        mkdir -p backups
        BACKUP_FILE="backups/jobot_backup_${TIMESTAMP}.tar.gz"
        echo "==> Creating backup: ${BACKUP_FILE}..."
        tar -czf "${BACKUP_FILE}" -C data .
        echo "==> Backup complete!"
        ;;
    help|*)
        show_help
        ;;
esac
