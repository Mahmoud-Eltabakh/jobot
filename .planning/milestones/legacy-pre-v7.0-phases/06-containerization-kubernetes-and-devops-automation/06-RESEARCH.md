# Phase 6: Containerization, Kubernetes & DevOps Automation - Research

## Overview
Phase 6 delivers production packaging and infrastructure automation for Jobot. It provides a multi-stage production `Dockerfile` with headless Playwright Chromium support, production multi-container `docker-compose.yml` linking Jobot and Ollama with GPU passthrough / CPU fallback, complete Kubernetes manifests (`k8s/`), and cross-platform automation scripts (`scripts/`) in Bash and PowerShell for building, running, model pre-pulling, and deploying.

## Technical Architecture & Design Decisions

### 1. Production Dockerfile Strategy
- **Base Image**: `python:3.11-slim` with minimal Debian runtime packages.
- **Playwright Dependencies**: Installs required shared libraries (`libnss3`, `libatk1.0-0`, `libcups2`, `libdrm2`, `libgbm1`, `libpango-1.0-0`, `libcairo2`, `libasound2`) without dragging in full desktop environments.
- **Browser Installation**: `playwright install chromium` inside the image to ensure fully offline/deterministic runtime execution without downloading binaries at container startup.
- **User Permissions & Security (STRIDE T-05)**: Non-root user `appuser` (UID 10001) owning `/app` and `/app/data` to prevent container breakout risks.
- **Healthcheck**: Built-in `HEALTHCHECK` directive probing `http://localhost:8000/health`.

### 2. Docker Compose Production Stack (`docker-compose.yml`)
- **Service Topology**:
  1. `jobot`: Port 8000 exposed, depends on `ollama` with `condition: service_started`, mounts persistent volume `jobot_data:/app/data`.
  2. `ollama`: Official image `ollama/ollama:latest`, port 11434 exposed locally, mounts persistent volume `ollama_data:/root/.ollama`.
- **GPU Acceleration**:
  - Configures `deploy.resources.reservations.devices` with driver `nvidia`, count `all`, capabilities `[gpu]` under an optional profile or standard definition with graceful CPU fallback.
- **Network Isolation**: Dedicated bridge network `jobot_network` ensuring internal DNS resolution (`http://ollama:11434`).

### 3. Kubernetes Architecture (`k8s/`)
- **Namespace**: `jobot` to isolate all resources.
- **Storage**:
  - `PersistentVolumeClaim` for Jobot data (`jobot-data-pvc`, 5Gi, ReadWriteOnce) storing SQLite database and ChromaDB vectors.
  - `PersistentVolumeClaim` for Ollama models (`ollama-models-pvc`, 20Gi, ReadWriteOnce) caching pulled LLMs across pod restarts.
- **Deployments**:
  - `jobot-deployment`: 1 replica (enforced to prevent concurrent multi-node SQLite file locking issues), with `livenessProbe` and `readinessProbe` pointing to `/health`.
  - `ollama-deployment`: 1 replica, exposing port 11434, with optional `nvidia.com/gpu: 1` resource limits.
- **Networking**:
  - `Service` (ClusterIP) for `jobot-service` and `ollama-service`.
  - `Ingress` routing external traffic (`jobot.local` or configurable host) to `jobot-service:8000`.
- **Config & Secrets**:
  - `ConfigMap` (`jobot-config`) for non-sensitive settings (`APP_NAME`, `LOG_LEVEL`, `OLLAMA_BASE_URL`, `DATABASE_URL`).
  - `Secret` (`jobot-secrets`) for optional cloud API keys (`OPENAI_API_KEY`).

### 4. Cross-Platform Automation Scripts (`scripts/`)
- **Bash Scripts** (Linux/macOS):
  - `scripts/build.sh`: Builds and tags `jobot:latest` and `jobot:dev`.
  - `scripts/run-docker.sh`: Spins up compose stack, waits for Ollama, and triggers `ollama pull qwen2.5:7b` & `ollama pull nomic-embed-text`.
  - `scripts/deploy-k8s.sh`: Applies manifests in dependency order and checks rollout status.
- **PowerShell Scripts** (Windows):
  - `scripts/build.ps1`
  - `scripts/run-docker.ps1`
  - `scripts/deploy-k8s.ps1`

## Validation Strategy
- Validate Dockerfile syntax and buildability.
- Validate `docker-compose.yml` configuration syntax with `docker compose config`.
- Validate Kubernetes manifests syntax using `kubectl apply --dry-run=client` or schema verification.
- Test cross-platform script syntax and execution flags.
