---
phase: 12-strict-real-data-enforcement-and-actionable-error-ui
plan: 03
subsystem: diagnostics
tags:
  - fastapi
  - diagnostics
  - tests
dependency_graph:
  requires:
    - "12-01"
  provides: []
  affects: []
key_files:
  created: []
  modified: []
status: complete
---

# Phase 12 Plan 03: System Diagnostics Health API & Zero-Mock Verification Suite Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
**Three of the four planned tasks are not present.**
- `app/api/diagnostics.py`: does not exist; `/api/diagnostics/health` is not registered in `app/main.py`.
- `tests/test_real_data_enforcement.py`: does not exist.
- `docs/USER_MANUAL.md`, `docs/CONTRIBUTING.md` and `README.md` do not mention a diagnostics endpoint.

## Related Behaviour That Does Exist
- `GET /health` (`tests/test_main.py::test_health_check`) is the generic liveness check, not the planned diagnostics.
- `JobEvaluator.purge_non_matching_jobs` (called from rescoring and profile save) deletes 0-fit and zero-skill-match jobs; `test_purge_non_matching_jobs` passes. ROADMAP lists this under the plan.
- `test_scraping_provider_failure_is_not_synthetic_success` covers part of the zero-mock intent.

## Verification
- Targeted tests pass, but none exercise the planned artifacts.

## Closed 2026-10-28
`app/api/diagnostics.py` (`GET /api/diagnostics/health`, authenticated, registered in `app/main.py`; database, vector store, queue counts, configured provider name, alerts; no secrets or URLs; no provider reachability probe), `tests/test_real_data_enforcement.py`, and docs (`docs/USER_MANUAL.md` section 11a, `docs/CONTRIBUTING.md`) now exist. README was not changed.

## Self-Check: PASSED
- `app/api/diagnostics.py` FOUND
- `tests/test_real_data_enforcement.py` FOUND
- Docs sync FOUND (USER_MANUAL, CONTRIBUTING)
