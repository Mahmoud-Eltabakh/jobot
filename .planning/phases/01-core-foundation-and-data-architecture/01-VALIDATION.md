---
phase: 01
slug: 01-core-foundation-and-data-architecture
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-07
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_config.py tests/test_db.py tests/test_vector.py -q` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick test suite
- **After every plan wave:** Run full test suite `pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | REQ-DB-01 | — | Valid environment and config parsing | unit | `pytest tests/test_config.py` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | REQ-DB-01 | — | FastAPI application startup and healthcheck | integration | `pytest tests/test_main.py` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | REQ-DB-01 | — | SQLite WAL mode and table creation | unit | `pytest tests/test_db.py` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | REQ-DB-03 | — | Schema migrations & model CRUD | integration | `pytest tests/test_db.py` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 2 | REQ-DB-02 | — | Persistent ChromaDB client & collection CRUD | unit | `pytest tests/test_vector.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — project metadata and test runner configuration
- [ ] `tests/conftest.py` — shared fixtures for temporary SQLite database and ChromaDB persistence
- [ ] `tests/test_config.py` — config unit tests
- [ ] `tests/test_main.py` — FastAPI startup tests
- [ ] `tests/test_db.py` — SQLModel schema tests
- [ ] `tests/test_vector.py` — ChromaDB vector store tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| None | — | All phase behaviors have automated tests | N/A |

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
