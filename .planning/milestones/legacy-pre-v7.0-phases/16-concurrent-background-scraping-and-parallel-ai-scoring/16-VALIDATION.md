---
phase: 16
slug: 16-concurrent-background-scraping-and-parallel-ai-scoring
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-11
---

# Phase 16 — Validation Strategy

> Reconstructed from the completed Phase 16 artifacts and the live parallel execution test suite.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_parallel_execution.py -q` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** run the focused phase suite
- **After every plan wave:** run the full project suite `pytest`
- **Before `/gsd-verify-work`:** full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | REQ-PAR-01 | — | Type-specific queue claiming prevents cross-worker contention | unit | `pytest tests/test_parallel_execution.py -q` | ✅ | ✅ green |
| 16-01-02 | 01 | 1 | REQ-PAR-01 | — | Scraping and evaluator loops run concurrently without blocking each other | integration | `pytest tests/test_parallel_execution.py -q` | ✅ | ✅ green |
| 16-01-03 | 01 | 1 | REQ-PAR-06 | — | Worker failure isolation and clean pause/stop lifecycle | integration | `pytest tests/test_parallel_execution.py -q` | ✅ | ✅ green |
| 16-02-01 | 02 | 2 | REQ-PAR-03 | — | LinkedIn/Google/StepStone scrapes are dispatched concurrently | integration | `pytest tests/test_parallel_execution.py -q` | ✅ | ✅ green |
| 16-02-02 | 02 | 2 | REQ-PAR-02 | — | AI evaluation runs in bounded parallel batches without unbounded concurrency | integration | `pytest tests/test_parallel_execution.py -q` | ✅ | ✅ green |
| 16-02-03 | 02 | 2 | REQ-PAR-03 | — | Deduplicated scrape results avoid duplicate evaluation tasks | integration | `pytest tests/test_parallel_execution.py -q` | ✅ | ✅ green |
| 16-03-01 | 03 | 3 | REQ-PAR-04 | — | Runtime concurrency settings persist and render in Settings UI | integration | `pytest tests/test_parallel_execution.py -q` | ✅ | ✅ green |
| 16-03-02 | 03 | 3 | REQ-PAR-05 | — | AI Queue View displays active scraping and AI-scoring indicators | integration | `pytest tests/test_parallel_execution.py -q` | ✅ | ✅ green |
| 16-03-03 | 03 | 3 | REQ-PAR-02 / REQ-PAR-03 / REQ-PAR-04 / REQ-PAR-05 | — | Full regression coverage for concurrency settings, queue metrics, and scraper/scorer behavior | regression | `pytest tests/test_parallel_execution.py -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_parallel_execution.py` — focused regression suite for parallel scraping and scoring
- [x] `app/queue/worker.py` — decoupled scraper and evaluator loops
- [x] `app/queue/task_queue.py` — task-type-aware claiming and worker scheduling
- [x] `app/scrapers/scheduler.py` — concurrent multi-source scraping orchestration
- [x] `app/api/settings.py` — runtime concurrency configuration persistence
- [x] `app/web/routes.py` — queue metrics and settings API wiring

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | — | All user-visible behaviors are covered by automated integration and UI tests | N/A |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
