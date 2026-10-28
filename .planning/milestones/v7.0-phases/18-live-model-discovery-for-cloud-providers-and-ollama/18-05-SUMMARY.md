---
phase: 18-live-model-discovery-for-cloud-providers-and-ollama
plan: "05"
subsystem: verification
status: complete
tags: [regression, isolation, secret-hygiene, docs]
requires: [18-01, 18-02, 18-03, 18-04]
key-files:
  modified: [tests/test_web_routes.py, tests/test_auth_security.py, docs/USER_MANUAL.md, docs/CONTRIBUTING.md]
requirements-covered: [REQ-HYB-07, REQ-HYB-08]
requirements-completed: []
actuals:
  tokens: null
  tasks: 3
  commits: 0
actuals-basis: Token cost not measured.
completed: 2026-10-28
---

# Phase 18 Plan 05: Regressions, Isolation, Docs Summary

## Completed Tasks

1. **Incident regressions** (`tests/test_web_routes.py`): Gemini listed-but-unusable case (generateContent filter, chosen model flagged, listing served from cache on the following test, stored value unchanged) and Ollama missing chat plus `nomic-embed-text` hints that disappear once the host lists both. Mocked transports only. Plan 03 tests already covered the first-level incidents; these add the end-to-end sequences.
2. **Isolation and hygiene** (`tests/test_auth_security.py`): unauthenticated rejection, no environment-key fallback, a sentinel-key leak test parametrized over seven key-bearing providers (list, refresh, test, save, Settings page, JSON, URLs, caplog, catalog repr), and a second-account test (own key required, no cached list or key shown, exactly one provider request). Ollama (no key by default) is covered by the Plan 03 host tests.
3. **Docs**: USER_MANUAL "Refreshing Model Suggestions (Phase 18)" and updated "Last updated" line; CONTRIBUTING "Phase 18 Model Discovery Contracts".

## Verification

- `.venv\Scripts\python.exe tests/run_phase17.py tests -q` -> **670 passed**, 0 failed, 4 pre-existing warnings (655 before this work + 15 new).
- Docs term check (`Refresh models`, `ollama pull`, `ModelCatalog`, `_discovery_http_client`) passed.

## Deviations from Plan

- The `_discovery_http_client` seam is exercised through the `provider_transport` fixture, not by monkeypatching the factory directly.
- Isolation tests live in `test_auth_security.py` as planned; the catalog tests in `test_model_catalog.py` were not extended (already covered by Plan 02).
- Comment pass skipped: `model_catalog.py` carries a module invariants docstring plus class/function docstrings and inline rationale comments, so it is not clearly under the 20-30% target; `client.py` is large and mostly Phase 17 code. Coverage was spot-checked, not measured by tool.
- Docs were not exercised against a live provider.

## Unresolved

- Live provider/Ollama checks and browser/keyboard/screen-reader acceptance (human_needed).
- Independent code review of Phase 18 has not run.

No commits, installs, network, or `data/` access; no real key printed.

## Self-Check: PASSED
