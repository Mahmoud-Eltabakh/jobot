---
phase: 17-multi-provider-and-hybrid-local-cloud-ai-routing
plan: "05"
subsystem: testing-and-documentation
status: complete
verification-status: pending-independent-verifier-review
tags: [pytest, transport-isolation, owner-routing, local-vectors, documentation]
requires:
  - phase: 17-01
    provides: Eight-provider adapters and owner-aware resolution
  - phase: 17-02
    provides: Encrypted vault and atomic settings/presets
  - phase: 17-03
    provides: Stage dispatch and separate local vector helpers
  - phase: 17-04
    provides: Settings/recovery UI and automated browser evidence
provides:
  - Eight-provider real-transport generation and safe-failure regressions
  - Intermediate-flush preset rollback assertions for both owners
  - Authenticated saved-route workflow across scraping, scoring and web/REST applying
  - Four owner-local vector paths with failure preservation and separate switch/retry
  - Source-matched README, user manual and contributor guide
affects: [independent-phase-17-verification, phase-17-review]
tech-stack:
  added: []
  patterns: [dual-HTTP-backend interception, disposable storage before imports, manual-only recovery]
key-files:
  created: [.planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-05-SUMMARY.md]
  modified: [tests/conftest.py, tests/test_ai_client.py, tests/test_auth_security.py, tests/test_e2e_workflow.py, tests/test_parallel_execution.py, tests/test_web_routes.py, app/web/routes.py, README.md, docs/USER_MANUAL.md, docs/CONTRIBUTING.md, .planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-VALIDATION.md, .planning/STATE.md]
key-decisions:
  - Mock native httpx and the installed SDK's actual httpx2 backend before constructing adapters.
  - Keep all four unrelated full-suite fixture failures visible instead of broad fixes.
  - Use cloud 502 and local Ollama 503 web fragments consistently with the phase error contract.
  - Preserve milestone v7.0 and leave phase verification and independent review pending.
requirements-covered: [REQ-HYB-01, REQ-HYB-02, REQ-HYB-03, REQ-HYB-04, REQ-HYB-05, REQ-HYB-06]
requirements-completed: []
actuals:
  tokens: null
  tasks: 3
  commits: 0
actuals-basis: No isolated pre-edit content snapshot was captured; existing shared-tree diffs cannot be attributed to this plan. No invented token total or commit ledger.
duration: Not measured; observed command timings recorded below
completed: 2026-10-28
---

# Phase 17 Plan 05: Cross-Boundary Regression and Operator Documentation Summary

Real-adapter transport checks, owner-scoped three-stage execution, fixed-local vector failure preservation, and accurate manual recovery documentation.

## Remaining CR-02 Follow-up Addendum (2026-10-28)

The updated independent review retained one provider-default mismatch. This follow-up adds shared non-secret provider fallback for factory, Settings API/rendered routing, sparse/provider-only saves and legacy probes. Legacy-secret eligibility remains separate: only an owner's matching saved provider can authorize that owner's old key; global/environment and orphan legacy keys are excluded. Explicit local selection and exact preset defaults are unchanged. Only `app/ai/client.py`, `app/api/settings.py` and existing `tests/test_web_routes.py` source/test files changed; CR-01/03/04 were not modified.

Two OpenAI/custom regressions cover absent owner routing, displayed provider/model parity with real factory resolution, actionable missing-key behavior, fake installation/environment/orphan-key exclusion, saved owner-vault probes, model-only saves before provider records, unchanged provider-only/full routing saves and exact local/hybrid/cloud presets. The red run stopped at unexpectedly accepted orphan owner legacy keys; the original UI mismatch remains independently reproduced in REVIEW.

Every command used `.venv\Scripts\python.exe tests/run_phase17.py` in the **main shared checkout**, with disposable storage and guarded service sockets before imports:

| Arguments | Exact result | Temp root suffix (`C:/Users/melta/AppData/Local/Temp/`) |
|---|---|---|
| `tests/test_web_routes.py::test_installation_provider_defaults_match_owner_routing -q --tb=short` before source fix | **2 failed, 2 warnings, 1.09s**, exit 1 | `jobot-17-04-tests-ggs4wf5k` |
| Identical command immediately after first source edit | **2 passed, 2 warnings, 2.63s**, exit 0 | `jobot-17-04-tests-x6u4vey2` |
| Identical command after sparse-save refinement | **2 passed, 2 warnings, 1.54s**, exit 0 | `jobot-17-04-tests-7x40ph9b` |
| `tests/test_ai_client.py tests/test_auth_security.py tests/test_web_routes.py -q --tb=short` | **309 passed, 4 warnings, 32.46s**, exit 0 | `jobot-17-04-tests-ruqpgl87` |
| `tests -q --tb=short` (one full run) | **490 passed, 4 warnings, 67.25s**, exit 0 | `jobot-17-04-tests-i5ex56wu` |

No editor errors in changed Python files; no source/test edits after the full run. No Git commands/mutations, installs, live provider requests or production storage use. REVIEW resolution status now records the CR-02 follow-up as applied pending independent re-review, preserving the independent `issues_found` verdict/history. VALIDATION contains exact evidence. Older full-suite counts below are historical. No browser rerun, independent clean finding, phase/milestone completion, live entitlement/output-quality validation or human acceptance is asserted.

## Completed Tasks

1. **Task 5-1: adapters/vault/security.** Added a shared transport fixture that intercepts both native HTTPX and the installed OpenAI SDK's actual backend. All eight provider IDs exercise JSON/text generation with system/user separation, selected models and owner headers, plus 401/403/402/429/503 and malformed-success failures with exactly one request and no secret/body reflection. Existing tests retain unknown IDs/tasks, missing/global/foreign credentials, native blocked/empty output, timeouts, optional Ollama tokens, owner legacy migration, encrypted blank-key retention, model discovery and HTML/JSON/log non-reflection. New preset tests fail after three intermediate flushed writes and prove rollback preserves both owners' fields/ciphertext.
2. **Task 5-2: integration/regression.** Saved real authenticated assignments dispatch discovery to Anthropic, scoring to Groq and both web/REST materials to Gemini through mocked transports, not factory stubs. Real temporary Chroma collections prove profile writes, job similarity and feedback write/query use only the owner's Ollama endpoint and nomic-embed-text. Injected 429, 402, timeout and dimension failures retain safe queue diagnostics, previous scores/materials/vectors and provider settings. A local preset changes exactly six assignments without I/O/retry; a separate owned retry resolves local. Foreign retries/generation are rejected. Concurrent independent task sessions prove another owner completes after its neighbor's 429 without changed concurrency settings, not a production load/bounds certification. Full suite executed and remaining failures recorded below.
3. **Task 5-3: docs sync.** Loaded the required jobot-docs-sync skill and synchronized README, USER_MANUAL and CONTRIBUTING against source. Documents all eight IDs/default hints, exact six field names and preset tuples, encrypted write-only owner keys/blank retention, legacy boundaries without global credential inheritance, explicit probe/error limits, independent local vectors and manual recovery/re-index precautions. Replaced dangerous bare-pytest/in-memory-fixture claims. No live entitlement, output-quality, savings, auto-failover or employer-submission claim was added. Skill commit instruction was not followed because the user forbade Git mutations.

## Verification

Every pytest process used the existing `.venv/Scripts/python.exe tests/run_phase17.py` runner. It creates unique temporary DATABASE_URL, CHROMA_DIR and ENCRYPTION_KEY_FILE before importing pytest/application code, sets JOBOT_TESTING=1, ENV=testing and disabled telemetry, then invokes pytest with `-o addopts=`. Parent environment remains unchanged. Background scheduler/worker loops never start. Tests use fake keys and HTTP/SDK mocks. The socket guard blocks service connections, including local Ollama; only Windows asyncio's internal socket pair is allowed. No production database, Chroma store or key file was used; no real outbound provider request or paid/live generation occurred.

| Check | Exact command arguments after the runner | Actual outcome |
|---|---|---|
| Task 5-1 | `tests/test_ai_client.py tests/test_auth_security.py -q -x --tb=short` | **272 passed, 4 warnings, 20.92s**, exit 0 |
| New cross-boundary cases | `tests/test_e2e_workflow.py -k 'saved_three_stage or failure_preservation or all_local_vector' -q -x --tb=short` | **13 passed, 2 deselected, 2 warnings, 7.25s**, exit 0 |
| Task 5-2 focused | `tests/test_e2e_workflow.py tests/test_parallel_execution.py -q -x --tb=short` | **24 passed, 2 warnings, 9.14s**, exit 0 |
| Web/recovery status regression | `tests/test_web_routes.py tests/test_e2e_workflow.py -k 'web_generation_safe_failure or failure_preservation' -q -x --tb=short` | **16 passed, 25 deselected, 2 warnings, 4.91s**, exit 0 |
| Initial full regression | `tests -q --tb=short` | **466 passed, 6 failed, 4 warnings, 62.01s**, exit 1 |
| Final full regression | `tests -q --tb=line` | **474 passed, 4 failed, 4 warnings, 60.13s**, exit 1; **478 collected** |
| Independent old scheduler/queue diagnostic | `tests/test_scheduler.py::test_scraper_pipeline_full_run tests/test_task_queue.py::test_queue_worker_task_execution -q --tb=short` | **2 passed, 2 warnings, 0.98s**, exit 0 |
| Final combined touched modules | `tests/test_ai_client.py tests/test_auth_security.py tests/test_e2e_workflow.py tests/test_parallel_execution.py tests/test_web_routes.py -q -x --tb=short` | **322 passed, 4 warnings, 34.46s**, exit 0 |

Final full root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-lpvhnk5j`. Final focused root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-wmzkabsh`. Runner prefixes retain the historical 17-04 name but each invocation creates unique new storage. Warning classes are existing Starlette/AnyIO, Chroma asyncio introspection and per-request test-cookie deprecations. No separate pre-edit Plan 05 baseline collection was captured; prior plan evidence and the actual initial/full/focused results are not mislabeled as one.

`git diff --check -- README.md docs/USER_MANUAL.md docs/CONTRIBUTING.md` exited 0. Editor diagnostics found no errors in all seven touched Python files. The final change after the full run removed only two unused test imports; the 322-test focused run followed immediately. No production change occurred after the full run.

A wider tracked-scope whitespace check exited 1 for pre-existing trailing whitespace at app/web/routes.py:608. That line is outside the one-line status mapper change and was preserved under the dirty-tree constraint; no unrelated formatting repair was made.

## Deviations from Plan

### Auto-fixed Phase 17 Defect

**[Rule 1 - Bug] Cloud timeout web status differed from the upstream-error contract.**
- Found by the new real-transport failure/recovery test: cloud Gemini REST failures returned 502, but web timeout fragments returned 503.
- First new-case run: 1 failed, 3 passed, 2 deselected. Inspected the controlling provider_failure mapper only, then removed the unconditional timeout-to-503 branch. Cloud fragments now use 502; Ollama fragments retain 503.
- Immediately reran the same focused command. The timeout repro passed before a separate test-only Chroma cache/resource error occurred. Final new-case set passed all 13 cases after its fixture correction.
- Existing web tests initially encoded the old cloud-timeout status. Updated that expectation and added six explicit local-provider cases; final web/recovery matrix passed 16 tests. No other production logic changed.
- Files: app/web/routes.py, tests/test_web_routes.py; no commit, per user constraint.

### Necessary Test Harness Adjustments

- Reused one module-owned disposable Chroma client instead of creating one for every parametrized case after an existing process-wide segment-cache read failed with "Nothing found on disk". Only fixture-owned test records are cleared during setup; failure checks still compare IDs/documents/metadata/embedding values and never reset a production collection.
- Existing E2E and parallel batch tests relied on generation mocks also controlling embeddings. Added explicit local embedding mocks and isolated the legacy E2E vector store; no runtime generation-as-embedding fallback was restored. Their failures were observed before each immediate focused repair/run.
- tests/conftest.py gained only the dual-backend transport fixture, preserving the user's existing autouse cleanup/auth fixtures. tests/test_web_routes.py is an adjacent necessary regression update, not an unrelated UI rewrite. No new test framework or source file was introduced.

## Deferred Issues: Full Regression Gate Failing

| Unchanged legacy test | Remaining failure | Evidence / risk |
|---|---|---|
| tests/test_linkedin_auth.py::test_linkedin_sync_api_endpoint | Expected 200, actual 503 | Raw-text override still requires unmocked AI/local vectors; do not restore fabricated success to satisfy it |
| tests/test_scheduler.py::test_scraper_pipeline_full_run | Local embedding provider unavailable in full suite | Earlier tests populate a shared vector singleton while this test mocks generation only; passes independently in fresh storage |
| tests/test_task_queue.py::test_queue_worker_task_execution | Expected score 92, actual None after local embedding failure | Same missing local-vector fixture isolation; independently passes with fresh empty collections |
| tests/test_vector.py::test_upsert_query_and_delete | Default ONNX model download blocked by socket guard | Test omits supplied embeddings/query vectors; no model download/install or real service connection was permitted |

These are baseline fixture limitations outside the touched behavior, not a passing regression gate. No broad fixes, skips, xfails, loosened assertions or provider requests were introduced to hide them. The optional .planning/WINDOWS.md ledger was absent; issues remain visible in this summary and VALIDATION instead of creating an unrelated register.

## Prior Browser Evidence and Manual Gaps

17-04-SUMMARY records **135 passing tests, eleven passing automated browser interaction groups and eight screenshots**, with zero page errors at 375x812 and 1440x900. Recorded artifact directory: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-browser-ysyuzhtt/`; settings, routing, failure and queue screenshot pairs plus evidence.json. This is attributed prior automated evidence, not a new browser run, independent UI/accessibility review or human acceptance. The old preview's availability was not rechecked and no user server was touched.

Independent verifier/review, human visual/content acceptance, exhaustive accessibility/device coverage, live provider/Ollama credentials/model entitlement, output quality and measured economics remain unverified. Existing vector account partitioning, cross-store atomicity and full production concurrency/load bounds are not certified or redesigned. REQ-QUAL-01 module-wide comment/docstring coverage was not independently certified; this plan's production change is one line, with no comment-only churn.

## Preservation and Completion Boundary

Executed **only Plan 17-05**, in the shared dirty tree, with all prior/user changes preserved. No staging, commits, branches, stash, reverts, installs, dependency changes, destructive re-index, live provider checks or milestone audit/archive/completion. Commits: **0**. No Git ledger, invented hashes, measured HEAD range or strict committed GSD TDD claim. Token/overall effort totals were not captured reliably and remain unmeasured rather than charging earlier dirty-tree deltas to this plan.

STATE now records **5/5 plans implemented, pending independent verifier/review**, retains `milestone: v7.0`, and leaves Phase 17 unchecked. VALIDATION records actual focused/full/browser evidence and the failing full gate; nyquist_compliant remains false. ROADMAP and REQUIREMENTS were not changed or marked complete. Plan task execution is complete, but phase verification, the 100%-green full-suite criterion and milestone acceptance are not.

## Known Stubs

None introduced in production. Transport responses and temporary records are test-only fixtures, not runtime fallback data. No skipped required verify command or newly skipped test is hidden.

## Orchestrator Regression Gate Resolution

The four fixture failures above were reproduced and resolved after executor handoff.
LinkedIn sync now explicitly mocks generation and local embeddings with its own
temporary vector store. Scheduler and queue orchestration tests isolate similarity
from prior tests' shared vectors. The vector-store lifecycle test supplies explicit
vectors instead of invoking Chroma's model downloader. Original status, score,
ranking, persistence and deletion assertions remain; runtime code was unchanged.

- Immediate focused check: `.venv/Scripts/python.exe tests/run_phase17.py tests/test_linkedin_auth.py tests/test_vector.py tests/test_scheduler.py tests/test_task_queue.py -q --tb=short`: **13 passed**, 2 warnings, 12.96s.
- Final full check: `.venv/Scripts/python.exe tests/run_phase17.py tests -q --tb=short`: **478 passed**, 4 deprecation warnings, 56.79s.
- Final disposable root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-xwtarygg`.
- Editor diagnostics found no errors in the four adjusted modules.
- No production storage, real service calls, package installs or git mutations.

This addendum supersedes the deferred full-regression blocker above; independent
review and phase verification remain pending until their own reports are written.

## Threat Surface

No new production endpoint, auth path, schema or file-access boundary. Only an existing web error HTTP-status branch changed. Test transport/storage and documentation risks remain those in the plan's threat model.

## Self-Check: PASSED

Read-only executable Node assertions verified all 13 implementation/test/documentation/closeout artifacts exist, the exact 322-pass focused and 474-pass/4-failure full evidence, all four deferred test names in SUMMARY/VALIDATION, the prior four summaries, eight documented provider IDs, fixed local model, zero commits, unchanged milestone v7.0, unchecked Phase 17 at 5/5 implemented and pending independent verifier/review. This self-check verifies artifact/evidence consistency, not a passing full regression or phase acceptance. Required docs whitespace passed; the wider pre-existing whitespace finding is disclosed above. No commit-existence check applies because all Git mutations were prohibited.

## Confirmed Review Fix Addendum (2026-10-28)

Applied all four confirmed findings from `17-REVIEW.md`, sequentially in the existing dirty shared checkout. This addendum records implementation and regression evidence, not an independent re-review or phase/milestone completion.

- **CR-01:** `TaskQueue.mark_failed(..., terminal=True)` commits provider diagnostic, retry count and terminal failed status once. The worker no longer commits a claimable pending state. A real interleaved second-session claim regression and a one-commit assertion pass; default ordinary-error retry behavior and explicit retry remain intact.
- **CR-02:** `get_provider_defaults` shares effective non-secret installation/owner endpoint/model values across generation, local embeddings, Settings, probes and local/hybrid presets. Custom installation host/model tests cover absent owner overrides and no-op saves, probes, presets and exclusion of installation tokens. Fixed-cloud probe policy and explicit custom-model precedence were retained after focused compatibility failures were repaired.
- **CR-03:** Settings rescoring catches factory and runtime provider errors, returns bounded escaped diagnostics plus separate switch/Retry, and permits HTML error swapping only for its exact endpoint/feedback target. Missing-key, scoring-429 and local embedding-outage tests preserve existing scores, summaries and evidence.
- **CR-04:** Cover-letter Retry includes its stable original options form, now including custom instructions. Direct/enthusiastic/conversational cases preserve tone/instructions through failure, local switch and explicit retry, with old material untouched until successful replacement. No submitted instructions are reflected into error HTML.

Production files: `app/queue/task_queue.py`, `app/queue/worker.py`, `app/ai/client.py`, `app/api/settings.py`, `app/web/routes.py`, `templates/base.html`, `templates/components/job_inspector.html`. Existing test modules: `tests/test_task_queue.py`, `tests/test_web_routes.py` (**10 new parametrized cases**). Enhanced existing `tests/phase17_browser.py`; synchronized README, USER_MANUAL and CONTRIBUTING, plus REVIEW and VALIDATION. No new dependency or test framework/file was introduced.

### Actual Fix Verification

All pytest processes used `.venv/Scripts/python.exe tests/run_phase17.py`, disposable paths before imports and its socket blocker. Gates ran in the **main shared checkout**, not an isolated worktree. All four regressions failed on the reported behavior before their small production fixes and passed immediately after. An initial missing-location test fixture was corrected before the CR-03 behavior repro. Ordinary retry control passed. Affected client/auth/web compatibility run: **299 passed, 4 warnings, 39.73s**. Explicit custom-model precedence was subsequently checked separately, then included in the final full gate.

| Final check | Command | Result |
|---|---|---|
| Targeted modules | `.venv/Scripts/python.exe tests/run_phase17.py tests/test_task_queue.py tests/test_web_routes.py -q --tb=short` | **42 passed, 2 warnings, 8.12s**, exit 0 |
| Full regression | `.venv/Scripts/python.exe tests/run_phase17.py tests -q --tb=short` | **488 passed, 4 warnings, 67.74s**, exit 0 |
| Browser | `.venv/Scripts/python.exe tests/phase17_browser.py serve --port 18793`, then `browse --port 18793` | **12 interaction groups**, zero page errors; **10 screenshots** at 375x812 and 1440x900 |

Targeted root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-1474agdu`; full root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-nkdbps0c`. Browser artifacts: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-browser-zj7gay5l/`; disposable preview: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-preview-c17lma52`. Preview service sockets were also blocked, provider operations mocked, and background workers disabled. Browser rescore failures visibly swap HTML, preserve score 90, switch without rescore and retry separately. Original/retried cover-letter POST bodies contain identical direct tone and literal instructions; generated script-like text remains escaped. Four recovery screenshots were inspected; overflow/focus checks pass at both sizes. The first browser attempt exposed a preview-only expired ORM instance; capturing its scalar ID fixed it before the successful fresh run. The dedicated preview shut down cleanly; existing servers were unchanged.

No source changes followed the final full regression. Existing deprecation warnings remain. Editor diagnostics report no errors in touched Python/template files. Live credentials, model entitlements, output quality, human acceptance and independent re-review remain unverified. The original review remains `issues_found` with a separate fixes-applied/pending-independent-rereview resolution status; it is not relabeled clean. Phase 17 and milestone v7.0 remain uncompleted. No staging, commits, branches, stash, reverts, installs, dependency edits, real provider requests or production storage use; unrelated prior/user edits were preserved.