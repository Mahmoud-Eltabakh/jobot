---
phase: 04
slug: 04-modern-web-dashboard-and-job-tracker-ui
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-07
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for the web UI, templates, HTMX components, and filter toolbar.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + starlette.testclient |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_web_routes.py tests/test_htmx_views.py tests/test_ui_filters.py -q` |
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
| 04-01-01 | 01 | 1 | REQ-UI-01 | T-05 | Base layout and Jinja2 template setup | unit | `pytest tests/test_web_routes.py` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | REQ-UI-02 | T-05 | Kanban board rendering & 8-stage transitions | integration | `pytest tests/test_htmx_views.py::test_kanban_view` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | REQ-UI-03 | T-05 | Data Table view rendering & sorting | integration | `pytest tests/test_htmx_views.py::test_table_view` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 2 | REQ-UI-03 | T-05 | Multi-Criteria Toolbar dynamic filtering | integration | `pytest tests/test_ui_filters.py` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04 | 2 | REQ-UI-04 | T-05 | Job Inspector split-pane & user notes editor | integration | `pytest tests/test_htmx_views.py::test_job_inspector` | ❌ W0 | ⬜ pending |
| 04-05-01 | 05 | 2 | REQ-CFG-03 | T-07 | Settings panel AI Provider toggle & blacklist | integration | `pytest tests/test_web_routes.py::test_settings_routes` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_web_routes.py` — unit tests for web router and template endpoints
- [ ] `tests/test_htmx_views.py` — integration tests for Kanban, Table, and Job Inspector HTMX partials
- [ ] `tests/test_ui_filters.py` — integration tests for multi-criteria filtering and sorting queries

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
