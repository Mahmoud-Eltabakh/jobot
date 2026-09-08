---
phase: 03
slug: 03-multi-source-scraping-engine-filter-pipeline-and-background-worker
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-07
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_filter_pipeline.py tests/test_scrapers.py tests/test_stepstone.py tests/test_scheduler.py -q` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~3 seconds |

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
| 03-01-01 | 01 | 1 | REQ-SCR-03 | T-03 | Deduplication hashing and normalized SQLite insert | unit | `pytest tests/test_scraper_pipeline.py` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | REQ-SCR-01 | T-04 | JobSpy scraper integration for LinkedIn & Google Jobs | unit | `pytest tests/test_scrapers.py` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 1 | REQ-SCR-02 | T-06 | StepStone Playwright crawler DOM and card extraction | unit | `pytest tests/test_stepstone.py` | ❌ W0 | ⬜ pending |
| 03-04-01 | 04 | 2 | REQ-SCR-04 | T-01 | Title & Keyword Pre-Filter Pipeline evaluation | unit | `pytest tests/test_filter_pipeline.py` | ❌ W0 | ⬜ pending |
| 03-05-01 | 05 | 2 | REQ-SCH-01 | T-06 | APScheduler periodic worker and on-demand trigger | integration | `pytest tests/test_scheduler.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_scraper_pipeline.py` — unit tests for deduplication and pipeline persistence
- [ ] `tests/test_scrapers.py` — unit tests for JobSpy wrapper
- [ ] `tests/test_stepstone.py` — unit tests for StepStone Playwright crawler
- [ ] `tests/test_filter_pipeline.py` — unit tests for Title & Keyword Pre-Filter Pipeline
- [ ] `tests/test_scheduler.py` — integration tests for APScheduler and on-demand triggers

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
