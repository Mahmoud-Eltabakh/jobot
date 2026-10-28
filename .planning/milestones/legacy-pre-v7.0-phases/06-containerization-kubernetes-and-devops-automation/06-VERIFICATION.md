---
phase: 06-containerization-kubernetes-and-devops-automation
verified: 2026-10-28T02:00:00Z
status: human_needed
score: 13/14 must-haves verified
verified_truths: 13
total_truths: 14
behavior_unverified: 0
overrides_applied: 0
gaps: []
deferred: []
human_verification:
  - "docker compose up --build: confirm jobot reports healthy and ollama-pull completes (not run: no Docker/network)"
covered_files:
  - ".planning/phases/06-containerization-kubernetes-and-devops-automation/06-01-PLAN.md"
  - ".planning/phases/06-containerization-kubernetes-and-devops-automation/06-01-SUMMARY.md"
  - ".planning/phases/06-containerization-kubernetes-and-devops-automation/06-02-PLAN.md"
  - ".planning/phases/06-containerization-kubernetes-and-devops-automation/06-02-SUMMARY.md"
  - ".planning/phases/06-containerization-kubernetes-and-devops-automation/06-03-PLAN.md"
  - ".planning/phases/06-containerization-kubernetes-and-devops-automation/06-03-SUMMARY.md"
  - ".planning/phases/06-containerization-kubernetes-and-devops-automation/06-04-PLAN.md"
  - ".planning/phases/06-containerization-kubernetes-and-devops-automation/06-04-SUMMARY.md"
  - "Dockerfile"
  - "app/core/config.py"
  - "app/main.py"
  - "docker-compose.yml"
  - "k8s/deployment-jobot.yaml"
covered_digest: "v3:sha256:bad0cf64faf2e43b3dbfcc83af11655a177e0133bd83212a41b618adf465283f"
audit_acknowledged:
  milestone: v7.0
  at: 2026-10-28
  status: human_needed
---

# Phase 6: Containerization, Kubernetes & DevOps Automation Verification Report

**Phase Goal:** Production image, Compose stack, Kubernetes manifests and automation scripts that run Jobot and Ollama.
**Verified:** 2026-10-28T02:00:00Z
**Status:** human_needed
**Re-verification:** No, initial verification. The files exist and `test_devops.py` passes, but the stack would not run correctly when started.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Self-contained image: Python 3.11, deps, Playwright Chromium | VERIFIED | Multi-stage Dockerfile, `python:3.11-slim`, `playwright install chromium`. Not built (no network). |
| 2 | Non-root `appuser` | VERIFIED | `Dockerfile:82-87` uid 10001, `USER appuser`. |
| 3 | HEALTHCHECK polls the health endpoint | FAILED | `Dockerfile:102` polls `/api/health` -> 404. See gap 2. |
| 4 | Entrypoint uvicorn `app.main:app` on 8000 | VERIFIED | `Dockerfile:104`, single worker (SQLite-safe). |
| 5 | Compose defines `jobot` and `ollama` with named volumes | VERIFIED | `jobot_data`, `ollama_storage`. |
| 6 | GPU reservation with CPU fallback | VERIFIED | nvidia device reservation in compose. |
| 7 | Isolated bridge network, DNS | VERIFIED | `jobot_net`. |
| 8 | Jobot links to `ollama:11434` | FAILED | Declared via `JOBOT_OLLAMA_BASE_URL`, which `Settings` ignores. See gap 1. |
| 9 | k8s manifests in `jobot` namespace | VERIFIED | namespace, configmap, secrets, pvc, 2 deployments, ingress; `jobot-all.yaml` bundle. |
| 10 | PVCs for data and models | VERIFIED | `pvc.yaml`. |
| 11 | Probes and single replica | PARTIAL | `replicas: 1` is correct; probe path is wrong (gap 2). |
| 12 | k8s config reaches the app | FAILED | ConfigMap `JOBOT_*` ignored (gap 1). |
| 13 | Bash and PowerShell scripts for build, run, deploy | VERIFIED | `scripts/*.sh` and `*.ps1`; `test_scripts_exist_and_executable`. |
| 14 | Scripts pre-pull Ollama models | FAILED | None found (gap 3). |

**Score:** 10/14 (some compound rows above are counted separately).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Env prefix probe | `JOBOT_OLLAMA_BASE_URL=http://ollama:11434` then `Settings(_env_file=None)` | `http://localhost:11434 sqlite:///data/jobot.db` | FAIL |
| Health routes probe (`TestClient`, temp storage) | GET `/health`, `/api/health`, `/api/diagnostics/health` | 200, 404, 401 | FAIL for `/api/health` |
| DevOps tests | `python tests/run_phase17.py <20 files> -q` | 424 passed in 35.55s | PASS (tests are shallow) |

Docker, Compose and kubectl were not run (no network, and the runtime state would be changed).

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `tests/test_devops.py` | Asserts that a string appears in the YAML rather than that the app honors it | Blocker (masks gaps 1-2) | Green tests, broken stack. |

### Human Verification Required

None until the gaps are closed. After that, one `docker compose up` run is advisable to confirm `healthy`.

### Gaps Summary

Two blockers: `JOBOT_*` configuration never reaches the app, and the health probes use a non-existent path. The model pre-pull is missing. `docker-compose.dev.yml` works because it uses unprefixed variables, which suggests the simplest fix is to align production files with that contract.

---

_Verified: 2026-10-28T02:00:00Z_
_Verifier: the agent (gsd-verifier)_

## Gap Closure (2026-10-28)

- Config: `Settings` now reads `JOBOT_<NAME>` as an alias of `<NAME>` (precedence: init > unprefixed env > `JOBOT_*` > `.env`). Compose and k8s files are unchanged. `JOBOT_DATA_DIR` is now a Settings field (`data_dir`): when set, `DATABASE_URL`, `CHROMA_DIR` and `ENCRYPTION_KEY_FILE` not set explicitly derive from it (`<dir>/jobot.db`, `<dir>/chroma`, `<dir>/.jobot-encryption-key`); explicit values win. Compose/k8s `/app/data` resolves to the same location as before.
- Health: Dockerfile HEALTHCHECK and k8s probes (`deployment-jobot.yaml`, `jobot-all.yaml`) now use `/health`.
- Pre-pull: compose `ollama-pull` one-shot service (jobot waits for completion); k8s ollama `postStart` background pull in `deployment-ollama.yaml` and `jobot-all.yaml`. `docker-compose.host-ollama.yml` has no pull step; the host operator pulls models.
- Tests: `test_devops.py` loads `Settings` under the declared compose/ConfigMap env, checks probe paths against registered app routes, and checks pre-pull wiring. Full suite 560 passed (includes `test_data_dir_derives_unset_paths_and_explicit_values_win`).
- Remaining: separate `k8s/service.yaml` accepted as an override (Services live in the deployment files). Docker, Compose and kubectl were not run; `covered_digest` was recomputed with `verification.fingerprint` on 2026-10-28 after the last edits to the covered files.
