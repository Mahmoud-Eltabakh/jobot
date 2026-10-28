---
phase: "18"
slug: live-model-discovery-for-cloud-providers-and-ollama
status: validated
nyquist_compliant: false
wave_0_complete: false
created: "2026-10-28"
---

# Phase 18 - Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | pytest 8+, pytest-asyncio |
| Config file | `pyproject.toml` |
| Interpreter | `.venv\Scripts\python.exe` (Python 3.14.7); project floor is Python 3.10, not executed here |
| Quick run command | `.venv\Scripts\python.exe tests/run_phase17.py tests/test_model_catalog.py -q --tb=short` |
| Full suite command | `.venv\Scripts\python.exe tests/run_phase17.py tests -q --tb=short` |
| Full suite result | 690 passed, 4 existing deprecation warnings, 73.39s |

The runner establishes disposable DB/Chroma/key paths before imports and blocks service sockets. Provider transports are mocked in automated tests; live provider behavior is covered only by operator UAT.

## Sampling Rate

- After every task/source slice: run that plan's focused `tests/run_phase17.py` command.
- After the final integration slice: run the full suite through the same isolated runner.
- No bare pytest command is safe because shared fixtures clear configured SQL tables.
- No dependency installs or network access were used.

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 1 | REQ-HYB-07 | T-18-01, T-18-04 | Owner-scoped key header; filtered escaped listing | integration | `tests/test_ai_client.py tests/test_web_routes.py -k "gemini and (list or discovery or provider_models)"` | yes | green |
| 18-01-02 | 01 | 1 | REQ-HYB-07 | T-18-01, T-18-03 | Bounded pagination, caps, safe errors | unit | `tests/test_ai_client.py` | yes | green |
| 18-01-03 | 01 | 1 | REQ-HYB-07 | T-18-01, T-18-02, T-18-03, T-18-04 | Header-only credentials, URL hygiene, escaped IDs | integration | `tests/test_ai_client.py tests/test_web_routes.py` | yes | green |
| 18-02-01 | 02 | 2 | REQ-HYB-08 | T-18-05, T-18-06 | Owner/key/endpoint cache isolation; no raw key storage | unit | `tests/test_model_catalog.py` | yes | green |
| 18-02-02 | 02 | 2 | REQ-HYB-07, REQ-HYB-08 | T-18-07 | TTL expiry, bounded cache, no failure caching | unit | `tests/test_model_catalog.py` | yes | green |
| 18-02-03 | 02 | 2 | REQ-HYB-07, REQ-HYB-08 | T-18-05, T-18-06, T-18-07 | Refresh cooldown and per-owner listing separation | unit | `tests/test_model_catalog.py tests/test_ai_client.py` | yes | green |
| 18-03-01 | 03 | 3 | REQ-HYB-08 | T-18-08, T-18-11 | Owner credentials; no silent model rewrite | integration | `tests/test_web_routes.py -k "provider and (model or discovery or refresh or test_provider)"` | yes | green |
| 18-03-02 | 03 | 3 | REQ-HYB-08 | T-18-09, T-18-10 | Escaped safe warnings and inert Ollama hints | integration | `tests/test_web_routes.py tests/test_ai_client.py -k "ollama or embedding"` | yes | green |
| 18-03-03 | 03 | 3 | REQ-HYB-08 | T-18-11 | Cache-only save warnings preserve exact input | integration | `tests/test_web_routes.py` | yes | green |
| 18-04-01 | 04 | 4 | REQ-HYB-07 | T-18-12, T-18-13 | Refresh POST body; empty password fields and stable targets | UI render | `tests/test_web_routes.py -k "provider_settings or refresh_models"` | yes | green |
| 18-04-02 | 04 | 4 | REQ-HYB-07 | T-18-13 | Provider-bound task model datalists | UI render | `tests/test_web_routes.py tests/test_htmx_views.py` | yes | green |
| 18-04-03 | 04 | 4 | REQ-HYB-08 | T-18-12, T-18-14 | Accessible non-blocking warning slots; no load/focus requests | UI render | `tests/test_web_routes.py tests/test_htmx_views.py` | yes | green |
| 18-05-01 | 05 | 5 | REQ-HYB-07, REQ-HYB-08 | T-18-15, T-18-16 | Incident and secret-leak regressions use mocked transports | integration | `tests/test_web_routes.py tests/test_ai_client.py -k "incident or gemini or ollama"` | yes | green |
| 18-05-02 | 05 | 5 | REQ-HYB-07, REQ-HYB-08 | T-18-15, T-18-16 | Cross-account isolation and full regression | integration | `tests` | yes | green |
| 18-05-03 | 05 | 5 | REQ-HYB-07, REQ-HYB-08 | T-18-17 | Documentation terms match implementation | static | `python -c` manual/contributor term assertion | yes | green |

All 15 implementation tasks map to existing automated targets. The final full suite passed on Python 3.14.7; Python 3.10 compatibility was not runtime-tested in this environment.

## Wave 0 Requirements

- Existing pytest/httpx fixtures and the isolated runner cover all phase requirements; no framework or dependency installation was needed.
- A separate pre-edit collection baseline was not recorded.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions / Result |
|----------|-------------|------------|----------------------------|
| Live model payloads, configured-host Ollama hints, browser keyboard/datalist/warning behavior, and provider listing spot checks | REQ-HYB-07, REQ-HYB-08 | Requires operator credentials, the configured Ollama host, and browser/assistive technology; mocks cannot prove these | Recorded as 4/4 passed in `18-UAT.md`; credentials were not shared in chat. |
| Approximate module-level meaningful comment/docstring target | REQ-QUAL-01 | Qualitative target; no reliable automated test or tool-measured coverage report was produced | Not measured or certified. No cosmetic padding was added. |

## Validation Sign-Off

- [x] All 15 implementation tasks have automated verification commands.
- [x] No three consecutive implementation tasks lack an executable check.
- [x] No package installs or watch-mode commands were used.
- [x] Full isolated suite passed: 690 tests, 4 existing warnings.
- [ ] `nyquist_compliant: true` remains unset because REQ-QUAL-01 coverage was not measured.

**Approval:** Behavioral coverage validated 2026-10-28; REQ-QUAL-01 remains an explicit unmeasured quality limitation.

## Validation Audit 2026-10-28

| Metric | Count |
|---|---|
| Gaps found | 1 |
| Resolved | 0 |
| Escalated | 1 |
