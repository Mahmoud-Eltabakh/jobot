---
phase: "17"
slug: multi-provider-and-hybrid-local-cloud-ai-routing
status: validated
nyquist_compliant: true
wave_0_complete: false
created: "2026-10-27"
---

# Phase 17 Validation Strategy

## CR-02 Provider Follow-up Evidence (2026-10-28)

The updated independent review found one remaining CR-02 provider-default blocker after the endpoint/model fix. The follow-up shares non-secret owner/installation provider selection across factory, Settings rendering, saves and legacy probes, while requiring an owner's explicit matching legacy provider for old-key reuse. Task overrides, owner-only vault credentials, explicit local presets and exact preset models remain intact. Only `app/ai/client.py`, `app/api/settings.py` and the existing `tests/test_web_routes.py` source/test module changed; CR-01/03/04 were not edited.

Verification ran in the **main shared checkout**, always with `.venv\Scripts\python.exe tests/run_phase17.py`, disposable DB/vector/key paths before imports and its socket guard. No Git commands/mutations, installs, live requests or production storage use. Exact arguments/results:

| Runner arguments | Result | Disposable root suffix under `C:/Users/melta/AppData/Local/Temp/` |
|---|---|---|
| `tests/test_web_routes.py::test_installation_provider_defaults_match_owner_routing -q --tb=short` before source fix | **2 failed, 2 warnings, 1.09s**, exit 1 (orphan legacy keys unexpectedly accepted) | `jobot-17-04-tests-ggs4wf5k` |
| Identical command immediately after first source edit | **2 passed, 2 warnings, 2.63s**, exit 0 | `jobot-17-04-tests-x6u4vey2` |
| Identical command after sparse-save coverage refinement | **2 passed, 2 warnings, 1.54s**, exit 0 | `jobot-17-04-tests-7x40ph9b` |
| `tests/test_ai_client.py tests/test_auth_security.py tests/test_web_routes.py -q --tb=short` | **309 passed, 4 warnings, 32.46s**, exit 0 | `jobot-17-04-tests-ruqpgl87` |
| `tests -q --tb=short` (full suite run once) | **490 passed, 4 warnings, 67.25s**, exit 0 | `jobot-17-04-tests-i5ex56wu` |

The two OpenAI/custom regressions verify absent owner routing, API/server-rendered UI provider/model parity with the factory, missing-key configuration failure, exclusion of global/environment/orphan legacy keys, saved owner-key probes, model-only/provider-only/no-op routing saves and exact local/hybrid/cloud presets. Existing matching-owner legacy-key contracts pass in the compatibility matrix. No editor errors in changed Python files; no source/test edits after the full run. This supersedes older full-suite counts as fixer evidence only. No new browser run, independent clean verdict, phase/milestone completion, live entitlement/output-quality validation or human acceptance is claimed. Historical evidence below remains attributed to its original executions; `nyquist_compliant` remains false.

## Confirmed Review Fix Evidence (2026-10-28)

All four confirmed findings CR-01..04 have fixes and failing-then-passing regressions in the existing main shared checkout. This is fixer evidence, not independent re-review/phase verification. Original review status is retained with a separate `fixes_applied_pending_independent_rereview` resolution status. Phase/milestone completion and `nyquist_compliant` are unchanged.

| Finding | Implemented contract and regression |
|---|---|
| CR-01 | Optional terminal queue failure persists diagnostic/retry count/failed status in one commit; another real session cannot claim it. Ordinary errors still auto-retry; explicit retry works. |
| CR-02 | Shared non-secret installation/owner Ollama endpoint/model defaults for factory, Settings, probes and presets. Absent-owner/no-op-save tests use a custom installation host/model and exclude installation tokens. Fixed-cloud probes and custom-model precedence remain compatible. |
| CR-03 | Catch both scoring factory and rescore provider failures. Safe escaped bounded HTML, separate switch/Retry and endpoint/target-scoped HTMX swaps; missing-key, scoring 429 and local embedding failure preserve previous score/summary/evidence. |
| CR-04 | Stable original cover-letter options form included by Retry. Three nondefault tones and literal instructions survive failure/switch/retry; old material remains until success. |

Ten new parametrized cases in existing `tests/test_task_queue.py` / `tests/test_web_routes.py`. Every test process uses `.venv/Scripts/python.exe tests/run_phase17.py`, unique database/vector/key paths established before imports and the mandatory socket blocker. Fake test keys only; no service requests, installs, dependency changes or Git mutations.

- Final targeted command: `.venv/Scripts/python.exe tests/run_phase17.py tests/test_task_queue.py tests/test_web_routes.py -q --tb=short`: **42 passed, 2 warnings, 8.12s**, exit 0. Root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-1474agdu`.
- Final full command: `.venv/Scripts/python.exe tests/run_phase17.py tests -q --tb=short`: **488 passed, 4 warnings, 67.74s**, exit 0. Root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-nkdbps0c`. This supersedes older full-suite counts below. No later source changes.
- Affected resolver compatibility matrix passed **299 tests, 4 warnings, 39.73s** after retaining fixed-cloud probe behavior. A later custom-model precedence regression passed after repair and is included in the final full gate.
- Enhanced isolated browser: `.venv/Scripts/python.exe tests/phase17_browser.py serve --port 18793`, then `browse --port 18793`: **12 interaction groups passed**, zero page errors, **10 screenshots** at 375x812 / 1440x900. Artifacts: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-browser-zj7gay5l/`; preview root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-preview-c17lma52`. Server service sockets were blocked, providers mocked and background loops disabled. New checks cover visible Settings rescore configuration/429/outage errors, score preservation, separate local switch/Retry, identical nondefault cover-letter request options and escaped generated content. Four recovery screenshots were inspected; automated overflow/focus checks pass at both sizes. Preview shut down cleanly; existing servers were not changed.
- Initial test-fixture missing location and preview-only detached ORM instance were corrected before successful runs; neither was hidden as product acceptance. Editor diagnostics are clear. Existing deprecation warnings remain. Live model entitlement, output quality, human acceptance and independent re-review are not established.

## Final Orchestrator Regression Evidence

The legacy fixture failures recorded later in this file are historical and resolved.
Four narrow fixture adaptations preserve assertions while supplying mocked local
embeddings or explicit vectors and isolating per-test vector state.
Focused repaired modules: **13 passed**, 2 warnings, 12.96s.
Full suite: `.venv/Scripts/python.exe tests/run_phase17.py tests -q --tb=short`
returned **478 passed**, 4 existing deprecation warnings, 56.79s, exit 0.
Disposable root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-xwtarygg`.
Service sockets were blocked by the test runner. No real credentials or paid calls.
Independent review/verifier outcomes are recorded separately, not inferred here.

Historical Plan 17-05 executor snapshot, superseded by the orchestrator and review-fix evidence above: all five plans implemented; independent verifier/review and human acceptance pending; full regression then 474 passed, 4 failed. No live credentials, paid generation, output quality or economic savings were tested. Historical Plan 01-04 results below are attributed to their summaries, not independently rerun or approved here.

## Test Infrastructure

| Property | Value |
|----------|-------|
| Framework | Existing pytest 8+ / pytest-asyncio; pyproject.toml |
| Interpreter | .venv/Scripts/python.exe from repository root |
| Quick run | `.venv/Scripts/python.exe -m pytest tests/test_ai_client.py -q -x` |
| Full regression | `.venv/Scripts/python.exe -m pytest tests -q` |
| Target feedback latency | Under 60s per focused new-behavior check; measure, not assumed |
| Full-suite latency | Final run 60.13s; initial run 62.01s |

## Mandatory Storage Isolation

tests/conftest.py clears ALL tables in the configured engine. Never run these commands against data/jobot.db or data/chroma. Configure environment in a fresh test process BEFORE app imports; restore previous environment after execution. Temporary artifacts must not be committed.

PowerShell setup (process environment only; no source edits):

```powershell
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("jobot-phase17-" + [guid]::NewGuid().ToString('N'))
[System.IO.Directory]::CreateDirectory($testRoot) | Out-Null
$env:DATABASE_URL = 'sqlite:///' + (Join-Path $testRoot 'test.db').Replace('\', '/')
$env:CHROMA_DIR = Join-Path $testRoot 'chroma'
$env:ENCRYPTION_KEY_FILE = Join-Path $testRoot 'encryption-key'
$env:JOBOT_TESTING = '1'
$env:ENV = 'testing'
$env:ANONYMIZED_TELEMETRY = 'False'
```

Do not print or reuse real provider credentials. Use fake test-only credentials in isolated storage. Existing environment keys must not leak into assertions/network calls; monkeypatch provider config for each test. Keep background scheduler/queue disabled via JOBOT_TESTING; tests explicitly exercise worker methods. Block/mock external transports, including model discovery and local Ollama. Vector dimension tests use isolated collections and fail without destructive resets.

## Sampling Rate

- Wave 0 is test preparation within the first implementation task, not a sixth plan: verify isolated paths/interpreter, collect the existing test targets, and add failing behavior tests before source edits.
- After EVERY production-code slice, immediately run that task's focused command before more reading/patching. When a module is slow, run newly added named tests first and the full listed target at task completion; no skipping checks.
- Each task has automated verification and explicit fails_when. No three tasks can pass without an executable check.
- After each wave, run its listed focused set. Run full suite once in 17-05-02 and again only if later code changes require it.
- Under this delegation: no git commits/staging/branching/stash/reverts. Sampling follows edits/tasks, not commits.

## Per-Task Verification Map

Commands below assume the isolated environment above. All target files already exist. Assertions described here must be implemented in their owning tasks; existing test collection alone is not feature verification.

| Task ID | Wave | Requirement | Threat Ref | Secure Behavior | Automated Command | Status |
|---------|------|-------------|------------|-----------------|-------------------|--------|
| 17-01-01 | 1 | HYB-03/05 | T-17-02/03 | Native payloads and safe bounded errors | `.venv/Scripts/python.exe -m pytest tests/test_ai_client.py -q -x` | Plan 01 recorded 29 passing client tests |
| 17-01-02 | 1 | HYB-03/05 | T-17-02/03 | Exact endpoints, safe SDK failures | `.venv/Scripts/python.exe -m pytest tests/test_ai_client.py -q -x` | Plan 01 recorded 89 passing client tests |
| 17-01-03 | 1 | HYB-01/02/04 | T-17-01 | Legacy signature, owner secrets, local embeddings | `.venv/Scripts/python.exe -m pytest tests/test_ai_client.py tests/test_auth_security.py -q -x` | Plan 01 final combined 133 passed, 4 warnings |
| 17-02-01 | 2 | HYB-02 | T-17-04/05 | Ciphertext, idempotency, batch rollback | `.venv/Scripts/python.exe -m pytest tests/test_config.py tests/test_db.py -q -x` | Plan 02 recorded 21 passed |
| 17-02-02 | 2 | HYB-02/06 | T-17-04/06 | All old/new credential routes isolated | `.venv/Scripts/python.exe -m pytest tests/test_auth_security.py tests/test_cv_parser.py -q -x` | Plan 02 recorded 38 passed before Task 3 |
| 17-02-03 | 2 | HYB-01/06 | T-17-05 | Six assignment fields atomic, keys untouched | `.venv/Scripts/python.exe -m pytest tests/test_auth_security.py tests/test_db.py -q -x` | Plan 02 recorded 65 passed; final five-module combined 232 passed |
| 17-03-01 | 3 | HYB-01/05 | T-17-07/09 | Worker owner/stage, no synthetic success | `.venv/Scripts/python.exe -m pytest tests/test_ai_scraping.py tests/test_parallel_execution.py tests/test_task_queue.py -q -x` | Plan 03 recorded 31 passed; Plan 05 full-suite fixture limitation below |
| 17-03-02 | 3 | HYB-04/05 | T-17-08/09 | Four vector paths local, mismatch non-destructive | `.venv/Scripts/python.exe -m pytest tests/test_embeddings.py tests/test_feedback.py tests/test_evaluator.py -q -x` | Plan 03 recorded 30 passed |
| 17-03-03 | 3 | HYB-01/05 | T-17-07/09 | Applying/profile owner and no false saves | `.venv/Scripts/python.exe -m pytest tests/test_application_generator.py tests/test_profile_and_linkedin.py -q -x` | Plan 03 recorded 28 passed; combined 89 passed |
| 17-04-01 | 4 | HYB-02/06 | T-17-10 | Eight owner-safe forms/targets | `.venv/Scripts/python.exe -m pytest tests/test_web_routes.py tests/test_auth_security.py -q -x` | Included in Plan 04 six-module 135-pass result |
| 17-04-02 | 4 | HYB-04/06 | T-17-10/11 | Persisted controls and visible 422 | `.venv/Scripts/python.exe -m pytest tests/test_web_routes.py tests/test_auth_security.py -q -x` | Included in Plan 04 135 tests and 11 browser groups |
| 17-04-03 | 4 | HYB-05/06 | T-17-11/12 | Escaped errors, separate owned retry | `.venv/Scripts/python.exe -m pytest tests/test_web_routes.py tests/test_htmx_views.py tests/test_profile_and_linkedin.py -q -x` | Included in Plan 04 135-pass result; cloud timeout status refined in Plan 05 |
| 17-05-01 | 5 | HYB-02/03 | T-17-01/04/14 | Adversarial credential/adapter matrix | `.venv/Scripts/python.exe tests/run_phase17.py tests/test_ai_client.py tests/test_auth_security.py -q -x --tb=short` | 272 passed, 4 warnings, 20.92s |
| 17-05-02 | 5 | HYB-01..06 | T-17-07/08/09/13 | Authenticated 3-stage workflow and full regressions | `.venv/Scripts/python.exe tests/run_phase17.py tests/test_e2e_workflow.py tests/test_parallel_execution.py -q -x --tb=short` then `.venv/Scripts/python.exe tests/run_phase17.py tests -q --tb=line` | Focused 24 passed, 2 warnings, 9.14s; full 474 passed, 4 failed, 4 warnings, 60.13s; gate failing |
| 17-05-03 | 5 | HYB-06 | T-17-14 | Accurate non-secret operator docs | `git diff --check -- README.md docs/USER_MANUAL.md docs/CONTRIBUTING.md` | Exit 0; exact fields/presets/limits checked against source |

HYB abbreviations above refer to REQ-HYB IDs. T-17-SC applies to every plan: no new installs. Tests reuse actual registration/session fixtures; no fake runtime production services or paid calls.

## Wave 0 Requirements

- [x] Interpreter, unique temp storage and disabled background loops established before every pytest import via tests/run_phase17.py.
- [ ] A separate pre-edit Plan 05 collection/baseline run was not captured; prior summary results and actual initial/final regressions are attributed below instead.
- [x] New assertions cover built behavior; the only production change followed a failing cloud-timeout assertion and immediate focused validation.
- [x] Cloud generation and local Ollama vectors have independent transport observations; both SDK HTTP backends intercepted.
- [x] Distinct authenticated cookie jars, owner endpoints and fake credentials exercised; prior conftest changes preserved.
- [x] Existing interpreter/dependencies used, with no installs or dependency edits.

## Plan 05 Actual Evidence

All commands used `.venv/Scripts/python.exe tests/run_phase17.py`, which sets disposable paths before imports and invokes pytest with `-o addopts=`. Service socket connections were guarded throughout, including local Ollama; no repeat of the Plan 02 escaped fake-key health GET occurred. A default Chroma model-download attempt in an old vector test was blocked before connection, not allowed or installed.

- Final combined touched-module command: `.venv/Scripts/python.exe tests/run_phase17.py tests/test_ai_client.py tests/test_auth_security.py tests/test_e2e_workflow.py tests/test_parallel_execution.py tests/test_web_routes.py -q -x --tb=short`: **322 passed, 4 warnings in 34.46s**, exit 0. Disposable root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-wmzkabsh`.
- New cross-boundary cases alone: 13 passed, 2 deselected, 2 warnings in 7.25s. Covers saved Anthropic scraping, Groq scoring, Gemini web/REST applying and all four populated owner-local vector paths, timeout/dimension preservation, 429/402/timeout safe failures, and explicit local switch followed by separate owned retry. Another parallel test proves a second owner completes while its neighbor fails without changing concurrency settings; it is not a production load or semaphore-bound certification.
- Source RED: cloud web timeout returned 503 while REST returned 502. Repaired only the web status mapper; the immediate rerun passed the original timeout case before exposing a test-only Chroma resource issue. Reusing one module-owned disposable Chroma client resolved that fixture issue; no production collection/cache changes.
- Existing E2E/batch tests received explicit local embedding mocks and isolated E2E vectors, not generation-as-embedding fallback. Existing web assertions now separately cover cloud 502 and Ollama 503. Focused web/recovery matrix: 16 passed, 25 deselected, 2 warnings in 4.91s.
- Initial full command with `--tb=short`: **466 passed, 6 failed, 4 warnings in 62.01s**. Two cloud-timeout expectation failures were repaired; six local-status cases were added. Final full command with `--tb=line`: **474 passed, 4 failed, 4 warnings in 60.13s**, exit 1, 478 collected. Disposable root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-lpvhnk5j`.
- No editor errors in the seven touched Python files. Required documentation whitespace check exited 0. A wider tracked-scope git diff --check exited 1 for pre-existing trailing whitespace at app/web/routes.py:608, outside this plan's one-line status change; preserved rather than cleaned up. Overall token/duration cost was not captured reliably in the pre-existing dirty tree.

### Remaining Full-Suite Failures

These unchanged legacy fixture limitations are not silently accepted as a passing gate:

| Test | Actual failure / evidence | Disposition |
|---|---|---|
| `tests/test_linkedin_auth.py::test_linkedin_sync_api_endpoint` | Expects 200 but gets 503; raw-text override does not mock required AI/local-vector work | Deferred fixture update; no runtime synthetic success added |
| `tests/test_scheduler.py::test_scraper_pipeline_full_run` | Unmocked local embeddings when earlier tests have populated the shared vector singleton | Deferred fixture isolation; independently passes with fresh empty vectors |
| `tests/test_task_queue.py::test_queue_worker_task_execution` | Expected score 92 remains None after local embedding failure in full-suite state | Deferred fixture isolation; independently passes with fresh empty vectors |
| `tests/test_vector.py::test_upsert_query_and_delete` | Omits embeddings/query vectors and triggers default ONNX model download; socket guard blocks it | Deferred offline fixture update, no download/install authorized |

Independent diagnostic command: `.venv/Scripts/python.exe tests/run_phase17.py tests/test_scheduler.py::test_scraper_pipeline_full_run tests/test_task_queue.py::test_queue_worker_task_execution -q --tb=short`: **2 passed, 2 warnings in 0.98s**, exit 0. The optional `.planning/WINDOWS.md` ledger is absent; failures are retained here and in 17-05-SUMMARY rather than creating an unrelated register.

## Browser and Manual Evidence

Plan 04 execution uses existing Python Playwright, a disposable test instance (JOBOT_TESTING=1), and mocked provider responses. Exercise Settings through the real nav at 375x812 and 1440x900. Verify eight cards, long errors/model names, loading, missing credentials, Saved state, partial configuration, 422 feedback swaps, separate switch/retry and no reflected secrets. Assert scrollWidth <= clientWidth, no missing HTMX targets and keyboard labels/focus; capture screenshots outside tracked source. Template/API tests alone do not prove responsive UI.

Live cloud credential/model entitlement validation is not automated or authorized here. Operator may later test their own key in Settings; non-generating health is reachability/auth evidence only. No subjective cover-letter quality, economic savings or human approval claim is made by this phase's routing checks.

Prior evidence from **17-04-SUMMARY.md**, not rerun in Plan 05: **135 passing tests, eleven passing automated interaction groups, eight screenshots**, at 375x812 and 1440x900, zero page errors. Recorded artifacts: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-browser-ysyuzhtt/` (settings/routing/failure/queue pairs and evidence.json). That summary records automated visual inspection/overflow/focus/HTMX checks, not human acceptance or an independent accessibility audit. Preview availability was not rechecked here.

## Validation Sign-Off

- [x] All 15 tasks have automated commands and failure signals.
- [x] All test target paths map to existing modules; no deferred test-only last wave.
- [x] No watch flags or package installs required.
- [x] New focused behavioral assertions implemented and passing (322-test combined target).
- [x] Disposable environment and observed focused timings recorded; no claim of an independently captured pre-edit collection baseline.
- [x] Prior browser evidence attributed and actual full regression failures recorded, not passed.
- [ ] Independent gsd-plan-checker review obtained.

Validation audit (2026-10-28): all 15 task rows map to existing automated test targets. Follow-up fixes for CR-05/06 and WR-01/02 add focused regressions for Python-compatible timeout handling, profile-vector preservation after failed upsert, owner-scoped feedback existence checks and fixed OpenAI endpoint selection. The final pagination follow-up rejects malformed Anthropic/Gemini cursors and includes explicit tests for malformed metadata and valid completion. Final isolated full suite: 690 passed, 4 existing deprecation warnings on Python 3.14.7. Python 3.10 itself was not available for execution. No behavioral coverage gaps were identified. The pre-edit Plan 05 baseline was not captured and cannot be reconstructed; independent plan-checker review remains outstanding. These remain process/evidence limitations, not evidence that planned behaviors lack tests. This audit does not certify full REQ-QUAL-01 comment coverage or refresh the phase verification report.

## Validation Audit 2026-10-28

| Metric | Count |
|---|---|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 2 |
