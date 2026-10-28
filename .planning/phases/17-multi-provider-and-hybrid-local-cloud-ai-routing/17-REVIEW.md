---
phase: 17-multi-provider-and-hybrid-local-cloud-ai-routing
reviewed: 2026-10-28T04:56:50Z
depth: deep
files_reviewed: 9
files_reviewed_list:
  - app/ai/client.py
  - app/ai/embeddings.py
  - app/ai/feedback.py
  - app/api/settings.py
  - pyproject.toml
  - tests/test_ai_client.py
  - tests/test_auth_security.py
  - tests/test_embeddings.py
  - tests/test_feedback.py
  - tests/test_web_routes.py
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
resolution_status: fresh_review_all_four_resolved
open_findings: []
resolved_findings: [CR-05, CR-06, WR-01, WR-02]
previous_reviewed: 2026-10-28T04:42:16Z
previous_files_reviewed: 10
previous_findings: {critical: 1, warning: 0, info: 0, total: 1}
original_reviewed: 2026-10-27T23:56:37Z
original_files_reviewed: 44
original_findings: {critical: 4, warning: 0, info: 0, total: 4}
resolution_date: 2026-10-28
---

# Phase 17: Code Review Report

**Reviewed:** 2026-10-28T04:56:50Z  
**Depth:** Deep focused follow-up of CR-05, CR-06, WR-01 and WR-02 against current source and regression tests.  
**Files Reviewed:** 9  
**Status:** clean

## Summary

All four requested findings are resolved in the current source. A workspace-wide search of application Python files found no `asyncio.timeout` uses. Provider operation deadlines use `_with_timeout` backed by `asyncio.wait_for`; native REST requests and the Settings health wrapper also use `asyncio.wait_for`. Profile replacement is upserted before stale vector deletion, feedback count and retrieval share one owner filter, and fixed OpenAI routing is canonical while explicitly configured Custom endpoints remain supported.

The recorded full-suite result is **673 passed on Python 3.14.7** (provided result; not rerun during this read-only review). The timeout tests exercise the native request deadline and Settings health deadline, but there is no static test forbidding `asyncio.timeout`; the source-wide search is the evidence for its current absence. Python 3.10 was not executed, so no runtime result for Python 3.10 is claimed. No live provider calls or network/accessibility verification are claimed. Source and test files were not edited.

## Narrative Findings (AI reviewer)

### CR-05: Python 3.11-only timeout contexts in application paths (resolved)

**Previous classification:** BLOCKER  
**Current status:** RESOLVED. Workspace search over `**/*.py` found no `asyncio.timeout` occurrences in application code. `_with_timeout` delegates to `asyncio.wait_for` ([app/ai/client.py](app/ai/client.py#L35)); native `_request` wraps the full request with `asyncio.wait_for` ([app/ai/client.py](app/ai/client.py#L352)). The current adapter list, generation, embedding and health paths call `_with_timeout` ([app/ai/client.py](app/ai/client.py#L366), [app/ai/client.py](app/ai/client.py#L408), [app/ai/client.py](app/ai/client.py#L469), [app/ai/client.py](app/ai/client.py#L560), [app/ai/client.py](app/ai/client.py#L575), [app/ai/client.py](app/ai/client.py#L595), [app/ai/client.py](app/ai/client.py#L630), [app/ai/client.py](app/ai/client.py#L645), [app/ai/client.py](app/ai/client.py#L717), [app/ai/client.py](app/ai/client.py#L733), [app/ai/client.py](app/ai/client.py#L744), [app/ai/client.py](app/ai/client.py#L788)); Settings health applies its own `asyncio.wait_for` deadline ([app/api/settings.py](app/api/settings.py#L203)). `test_native_has_whole_request_deadline` and `test_settings_health_check_has_python310_compatible_deadline` assert those wait-for deadlines ([tests/test_ai_client.py](tests/test_ai_client.py#L444), [tests/test_ai_client.py](tests/test_ai_client.py#L463)). These are focused behavioral controls, not Python 3.10 execution or a static ban test.

### CR-06: Profile refresh deletes stale vectors before replacement succeeds (resolved)

**Previous classification:** BLOCKER  
**Current status:** RESOLVED. `embed_and_store_profile` writes replacement vectors before calculating/deleting stale owner IDs ([app/ai/embeddings.py](app/ai/embeddings.py#L227), [app/ai/embeddings.py](app/ai/embeddings.py#L237)). `test_profile_upsert_failure_preserves_stale_owner_vectors` injects an upsert failure and asserts the prior IDs, documents, metadata and embeddings remain unchanged ([tests/test_embeddings.py](tests/test_embeddings.py#L181)). This verifies the reported ordering/failure case, not arbitrary partial writes inside Chroma.

### WR-01: Feedback existence check is not owner-scoped (resolved)

**Previous classification:** WARNING  
**Current status:** RESOLVED. One `owner_filter` is passed to both collection count and similarity query ([app/ai/feedback.py](app/ai/feedback.py#L176), [app/ai/feedback.py](app/ai/feedback.py#L177), [app/ai/feedback.py](app/ai/feedback.py#L182), [app/ai/feedback.py](app/ai/feedback.py#L186)). `test_other_owners_feedback_does_not_trigger_embedding` leaves only another owner's vector in the collection and asserts neutral output without an embedding call ([tests/test_feedback.py](tests/test_feedback.py#L165)).

### WR-02: Legacy OpenAI and provider probes use different endpoints (resolved)

**Previous classification:** WARNING  
**Current status:** RESOLVED. OpenAI factory defaults use the canonical fixed host, and a noncanonical legacy OpenAI endpoint is rejected before credential resolution ([app/ai/client.py](app/ai/client.py#L930), [app/ai/client.py](app/ai/client.py#L942)). Settings probes keep fixed-provider hosts canonical while allowing owner-configured Custom endpoints ([app/api/settings.py](app/api/settings.py#L148), [app/api/settings.py](app/api/settings.py#L174)). `test_legacy_cloud_probe_uses_matching_owner_configuration` asserts canonical OpenAI and owner-specific Custom probe endpoints with owner credentials ([tests/test_auth_security.py](tests/test_auth_security.py#L675)); factory tests cover rejection of a legacy OpenAI URL and retention of an explicit Custom URL ([tests/test_ai_client.py](tests/test_ai_client.py#L350), [tests/test_ai_client.py](tests/test_ai_client.py#L431)). A mocked custom LAN model-discovery regression also verifies explicit Custom endpoint support ([tests/test_web_routes.py](tests/test_web_routes.py#L571)).

---

_Reviewed: 2026-10-28T04:56:50Z_  
_Reviewer: GitHub Copilot (gsd-code-reviewer)_  
_Depth: deep_
| Arguments after guarded runner | Exact result | Disposable root suffix (`C:/Users/melta/AppData/Local/Temp/`) |
|---|---|---|
| `tests/test_web_routes.py::test_installation_provider_defaults_match_owner_routing -q --tb=short` before source edit | **2 failed, 2 warnings, 1.09s**, exit 1; factory unexpectedly accepted orphan legacy keys | `jobot-17-04-tests-ggs4wf5k` |
| Same command immediately after first source edit, before further reads/patches | **2 passed, 2 warnings, 2.63s**, exit 0 | `jobot-17-04-tests-x6u4vey2` |
| Same command after strengthening sparse/provider-only saves | **2 passed, 2 warnings, 1.54s**, exit 0 | `jobot-17-04-tests-7x40ph9b` |
| `tests/test_ai_client.py tests/test_auth_security.py tests/test_web_routes.py -q --tb=short` | **309 passed, 4 warnings, 32.46s**, exit 0 | `jobot-17-04-tests-ruqpgl87` |
| `tests -q --tb=short` (one full run) | **490 passed, 4 warnings, 67.25s**, exit 0 | `jobot-17-04-tests-i5ex56wu` |

The initial red run stopped at the credential-provenance assertion, not the later UI assertion; the independently reproduced UI mismatch is documented below. Changed Python files have no editor errors. No source/test changes followed the full run. Browser interaction, live entitlement/output quality and human acceptance were not rerun or established by this follow-up.

### Remaining BLOCKER: CR-02 - Installation provider defaults still disagree with Settings

**Classification:** BLOCKER
**Priority:** P1
**Confidence:** High
**File:** [app/api/settings.py](app/api/settings.py#L441), `_routing_settings`; also [app/api/settings.py](app/api/settings.py#L404), `get_all_settings`.
**Supporting control flow:** [app/ai/client.py](app/ai/client.py#L664), `get_ai_client`; [app/ai/client.py](app/ai/client.py#L609), `get_provider_defaults`; [app/web/routes.py](app/web/routes.py#L607), Settings rendering consumes `get_all_settings` for task assignments.

**Issue:** Sharing endpoint/model defaults fixed the reported non-default Ollama host/model case, but not the controlling provider fallback. With no owner `ai_provider` or task assignment, the factory inherits installation `ai_provider`, while Settings uses literal `ollama`. On a supported OpenAI-default installation, Settings therefore advertises local routing while scoring actually selects OpenAI and fails for missing owner credentials, or uses the owner's saved OpenAI key if present. Saving the displayed task assignments can silently switch execution to local routing. Registration does not seed owner routing records, so this is reachable without corrupt or malformed settings. This is the same settings-versus-execution contract as CR-02, not an audit of excluded architecture.

**Independent reproduction:** Ran the existing `test_installation_local_defaults_match_settings_probe_save_and_presets[False]` through the guarded runner with `--trace`, after its real authenticated fixtures initialized. An in-memory debugger diagnostic changed only the disposable installation `ai_provider` to `openai`, then called the real authenticated Settings API and real owner factory. Observed `task_scoring_provider=ollama`, `task_scoring_model=llama3.1:8b`, but factory `AIProviderError(provider=openai, model=gpt-4o-mini, category=configuration)`. An explicit assertion confirmed the provider mismatch. The diagnostic restored the installation setting in `finally`; continuing the original test passed. No source/test file or persistent application data was changed, and no provider request was attempted.

**Fix:** Share effective non-secret provider selection as well as endpoint/model defaults across the factory, Settings JSON/rendered assignments and provider-only save fallback. Preserve precedence of owner task assignment, owner legacy provider, then installation provider, and keep credential lookup strictly owner-only. Add absent-owner-routing cases with installation `ai_provider=openai` (and another supported non-Ollama provider), comparing displayed provider/model with actual resolution. Include missing owner credentials, a fake saved owner key, and a no-op routing save. Do not repair this by borrowing installation credentials or silently forcing the factory to Ollama.

### Resolution Evidence

| Finding | Independent assessment | Regression coverage and limits |
|---|---|---|
| CR-01 | Resolved | `terminal=True` reaches one `mark_failed` commit. The real second-session claim regression observes no claimable intermediate state, one commit, preserved retry limit and explicit retry; ordinary retry lifecycle also passes. Anchors: [task_queue.py](app/queue/task_queue.py#L149), [worker.py](app/queue/worker.py#L145), [test_task_queue.py](tests/test_task_queue.py#L197). |
| CR-02 | Partially resolved; BLOCKER above remains | Two installation host/model cases cover absent settings and no-op provider save, probes without installation tokens, local embeddings and local/hybrid presets. Custom model precedence is covered. Neither new case changes installation provider away from Ollama. Anchors: [client.py](app/ai/client.py#L599), [test_web_routes.py](tests/test_web_routes.py#L63), [test_web_routes.py](tests/test_web_routes.py#L248). |
| CR-03 | Resolved | Real missing-key resolution plus injected scoring 429 and local embedding outage return bounded escaped failure fragments without altering the failing job's prior score/summary/evidence. Local switch does not rescore. The template permits HTML error swaps only for the exact rescore endpoint/target pair. Earlier successful jobs retain the existing per-job commit policy, not batch atomicity. Anchors: [settings.py](app/api/settings.py#L851), [base.html](templates/base.html#L166), [test_web_routes.py](tests/test_web_routes.py#L281). |
| CR-04 | Resolved | Retry includes the surviving job-specific options form. Three non-default tones and literal instructions survive the test's manually reconstructed retry, old material stays stored until success, and switching does not generate. The unit test does not execute HTMX serialization; request-body equality in the inspected browser harness supports the fix but its run remains attributed evidence. Anchors: [routes.py](app/web/routes.py#L747), [job_inspector.html](templates/components/job_inspector.html#L174), [test_web_routes.py](tests/test_web_routes.py#L155), [phase17_browser.py](tests/phase17_browser.py#L277). |

### Independent Checks (2026-10-28)

Every executable invocation used `.venv\Scripts\python.exe tests/run_phase17.py`, which established disposable database/vector/key paths and its socket guard before application imports. No bare pytest, installs, real network requests, Git commands/mutations, source/test edits or completion-state changes were performed.

| Invocation suffix after the guarded runner | This reviewer's result |
|---|---|
| `tests/test_task_queue.py tests/test_web_routes.py -q --tb=short` | **42 passed, 2 deprecation warnings, 9.46s**, exit 0. Disposable root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-hszs140l`. |
| `tests/test_web_routes.py::test_installation_local_defaults_match_settings_probe_save_and_presets[False] -q --tb=short --trace` | In-memory diagnostic asserted the CR-02 mismatch above; continued original item: **1 passed, 2 warnings**, exit 0. The pass is not coverage of corrected provider fallback. Disposable root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-xujjbuki`. |
| `tests/test_ai_client.py tests/test_auth_security.py -q --tb=short` | **272 passed, 4 deprecation warnings, 32.16s**, exit 0. Disposable root: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-nkap2vvo`. |

The 15-file list records the focused implementation/test surfaces inspected in this re-review. Supporting reads of registration, ownership migration, database settings helpers and configuration established reachability and provenance; authentication tests were also executed. The original 44-file scope is preserved separately in frontmatter. No full-suite or browser rerun was performed by this reviewer. The main verifier, real provider entitlements/output quality and human acceptance remain pending. Existing encrypted-profile ordering, vector account partitioning, cross-store transactions and unrelated concurrency architecture remain excluded.

## Original Review History

The following narrative and four findings preserve the original review and the fixer's resolution claims. Historical BLOCKER labels do not imply currently open findings; the current frontmatter and fresh assessment above record one remaining blocker (CR-05), with CR-06, WR-01 and WR-02 resolved.

Scope is the union of key-files from all five 17-0N-SUMMARY frontmatters plus the four explicitly requested fixture files. Planning artifacts were excluded; all 44 listed files exist and none are Git-ignored. Supporting dependencies were read only to establish control flow. No structural pre-pass or external reviewer evidence was supplied.

Findings concern Phase 17 routing/recovery behavior, not all dirty-tree changes. Existing encrypted-profile ordering, vector account partitioning, cross-store transactions, and unrelated concurrency architecture are not reported as Phase 17 defects.

## Historical Critical Issues

### CR-01: Provider failure is committed as automatically retryable before becoming terminal

**Classification:** BLOCKER
**Priority:** P1
**Confidence:** High
**File:** [app/queue/worker.py](app/queue/worker.py#L146), lines 146-149, QueueWorker._process_task.
**Supporting control flow:** [app/queue/task_queue.py](app/queue/task_queue.py#L149), TaskQueue.mark_failed; [app/queue/task_queue.py](app/queue/task_queue.py#L97), claim_next_task.

**Issue:** The new AIProviderError handler calls mark_failed, which sets status to pending while retries remain and commits that status. Only afterward does the worker set failed and commit again. A different queue consumer can claim the durable pending task between these commits, without an owner Retry action. The absence of an await does not protect a database from another process/session. Failure or process termination before the second commit also leaves the task automatically retryable. This violates the phase's explicit manual-only provider recovery contract and can repeat a cloud operation or race task outcomes.

**Independent reproduction:** Injected a 429 through the owned scoring factory and interleaved another Session's real claim_next_task immediately after the real mark_failed returned. That session successfully claimed the same task before the worker's final failed update. No generation request, manual retry, or model change occurred. The existing final-status assertions do not examine this intermediate durable state.

**Minimal fix:** Persist the provider diagnostic, retry bookkeeping and terminal failed status in one transaction. Give mark_failed a terminal/no-auto-requeue option, or write this transition directly without calling its committing pending path. Preserve the ordinary-error retry policy. Add a regression asserting the provider-failure transition never exposes a committed pending task to another session.

**Resolution:** [app/queue/task_queue.py](app/queue/task_queue.py) adds keyword-only `terminal=False`; [app/queue/worker.py](app/queue/worker.py) passes `terminal=True` for provider errors instead of committing a second status update. Diagnostic, retry count and failed status persist once. `test_provider_failure_never_commits_claimable_task` in [tests/test_task_queue.py](tests/test_task_queue.py) reproduced a real second-session claim before the fix; now it observes no claim and exactly one commit, retains retry limits and allows explicit retry. The ordinary-error lifecycle control also passes.

### CR-02: Settings and presets resolve different effective defaults from the execution factory

**Classification:** BLOCKER
**Priority:** P1
**Confidence:** High
**File:** [app/api/settings.py](app/api/settings.py#L149), _owner_endpoint; [app/api/settings.py](app/api/settings.py#L132), _owner_model; [app/api/settings.py](app/api/settings.py#L453), _routing_settings.
**Supporting control flow:** [app/ai/client.py](app/ai/client.py#L611), get_embedding_client; [app/ai/client.py](app/ai/client.py#L651), get_ai_client model resolution; [app/api/settings.py](app/api/settings.py#L601), apply_ai_preset.

**Issue:** For an owner without explicit Ollama settings, the execution factory inherits the installation's non-secret endpoint/model, but the new settings/probe/preset helpers substitute hard-coded PROVIDER_DEFAULTS. The UI can display and test localhost and llama3.1:8b while execution actually uses a configured installation host/model. Saving the otherwise unchanged provider form then creates owner overrides for the displayed defaults, redirecting both generation and embeddings to localhost. Local/hybrid presets similarly replace the effective model with the hard-coded hint. This breaks configured container/host-Ollama installations and makes connection feedback describe a different configuration from execution.

**Independent reproduction:** Set installation endpoint to http://installation-local.invalid:11434 and model to installed-local-model, leaving owner settings absent. The real factory selected these values; GET /api/settings returned localhost and a different task model. Posting the returned Ollama form values succeeded and changed the real owner embedding client's endpoint to localhost. No network connection was attempted.

**Minimal fix:** Share effective non-secret default resolution between settings/probes/presets and the factory. Continue reading keys strictly from the owner vault or matching owner legacy configuration; aligning endpoint/model defaults must not import global credentials. Cover an owner with no overrides and a non-default installation host/model, including no-op form saves and local/hybrid presets.

**Resolution:** `get_provider_defaults` in [app/ai/client.py](app/ai/client.py) shares only non-secret endpoint/model resolution with [app/api/settings.py](app/api/settings.py). Generation, local embeddings, displayed Ollama settings, probes and local/hybrid presets inherit the configured installation host/model until owner overrides exist. Key paths remain owner-only; fixed-cloud probe hosts are unchanged. The two `test_installation_local_defaults_match_settings_probe_save_and_presets` cases in [tests/test_web_routes.py](tests/test_web_routes.py) cover presets both with absent owner settings and after a no-op save, plus mocked probes and exclusion of installation tokens. A custom-model precedence compatibility regression also passes. An intermediate fixed-cloud probe compatibility failure was repaired before proceeding; its affected matrix passed **299 tests**.

### CR-03: Settings rescoring bypasses the safe provider-error and HTMX feedback paths

**Classification:** BLOCKER
**Priority:** P2
**Confidence:** High
**File:** [app/api/settings.py](app/api/settings.py#L859), lines 859-862, rescore_all_jobs_endpoint.
**Supporting control flow:** [templates/components/settings.html](templates/components/settings.html#L440), the Rescore All Stored Jobs command; [app/ai/evaluator.py](app/ai/evaluator.py#L846), propagation from rescore_all_jobs; [templates/base.html](templates/base.html#L162), narrowly scoped beforeSwap handler.

**Issue:** This active Settings command resolves the scoring client and awaits rescore_all_jobs without catching AIProviderError. Phase 17 now deliberately propagates missing-key, provider and embedding failures, so they escape as unhandled 500 responses instead of bounded provider/category diagnostics. The target is scales-save-feedback, outside ai-providers; the global profile error handler also excludes this endpoint. Consequently the ordinary Settings workflow displays no actionable provider failure or manual recovery feedback, although the separate profile rescoring route handles the same error.

**Independent reproduction:** Authenticated POST /api/settings/rescore-all with an injected scoring-factory rate_limit/429 error returned HTTP 500 under TestClient(raise_server_exceptions=False), with neither the safe category nor local-recovery controls. This also fails before any job/provider I/O, so a missing credential alone is sufficient.

**Minimal fix:** Catch AIProviderError around both resolution and rescoring and return the shared safe failure fragment/status. Enable non-2xx HTML swapping specifically for this command/feedback target. Add failure cases for factory configuration errors, scoring 429 and local embedding outage; retain preservation of previously stored scores.

**Resolution:** [app/api/settings.py](app/api/settings.py) catches `AIProviderError` around both client resolution and `rescore_all_jobs`, returning the shared bounded escaped fragment with a separate local-switch action and rescore Retry. [templates/base.html](templates/base.html) permits non-2xx HTML swapping only for this exact endpoint/feedback-target pair alongside existing profile rules. The three `test_settings_rescore_safe_failure_preserves_scores` cases in [tests/test_web_routes.py](tests/test_web_routes.py) first reproduced HTTP 500 and now pass for real missing-key resolution, scoring 429 and local embedding outage, retaining prior score/summary/evidence. The browser independently exercises visible HTMX swaps and separate switch/retry requests with controlled preview failures.

### CR-04: The new cover-letter Retry action silently drops generation options

**Classification:** BLOCKER
**Priority:** P2
**Confidence:** High
**File:** [app/web/routes.py](app/web/routes.py#L54), provider_failure Retry markup; [app/web/routes.py](app/web/routes.py#L747), generate_cover_letter_view failure return.
**Supporting control flow:** [templates/components/job_inspector.html](templates/components/job_inspector.html#L174), original options form; [app/web/routes.py](app/web/routes.py#L729), tone/instructions defaults.

**Issue:** The Retry button is rendered inside cover-letter-container, outside the original generation-options form. It has only hx-post/hx-target, with no hx-include or preserved values. Clicking it sends no tone or custom_instructions. A direct, enthusiastic or conversational request therefore retries as professional; submitted instructions disappear as well. If it succeeds, the route automatically saves that differently configured result over the existing material. The separate retry action is explicit, but it does not retry the user's requested operation faithfully.

**Independent reproduction:** First POST used tone=direct and custom instructions and returned a mocked 429. Parsed Retry markup had no parent form or value/include attributes. Replaying its empty POST reached the generator with tone=professional and custom_instructions=None and saved the successful result. This matches the HTMX form placement in the actual inspector template. The prior browser test uses the default tone, so it cannot distinguish the two operations.

**Minimal fix:** Give the original options form a stable ID and include its relevant fields in this Retry action, or safely preserve the original options in the failure response. Keep local switching and generation as separate requests. Test a non-default tone and submitted instructions through failure, switch and retry.

**Resolution:** [templates/components/job_inspector.html](templates/components/job_inspector.html) gives the original options form a job-specific stable ID and exposes its custom-instructions field. [app/web/routes.py](app/web/routes.py) includes that form on cover-letter Retry through an escaped optional selector; submitted instructions are not reflected into error markup. The three `test_cover_letter_retry_preserves_original_options` cases in [tests/test_web_routes.py](tests/test_web_routes.py) first failed on absent inclusion and now preserve direct/enthusiastic/conversational tone and literal instructions through failure, local switch and explicit retry, retaining old material until success. Browser request-body assertions additionally verify identical nondefault tone/instruction values on the original and retried requests.

## Fixer-Reported Resolution Verification (2026-10-28)

This section retains the fixer's evidence, not executions by this independent reviewer. All pytest commands used `.venv/Scripts/python.exe tests/run_phase17.py` with disposable database/vector/key paths and the runner's socket blocker before application imports. Verification ran in the existing **main shared checkout**, not a separate worktree. No real credentials, provider service calls, installs, dependency changes or Git mutations occurred. Ten new parametrized regression cases were added to existing test modules.

| Check | Actual result |
|---|---|
| CR-01 repro/control, then immediate fix validation | 1 failed / 1 passed before; 2 passed after |
| CR-02 custom installation repro, then immediate fix validation | 1 failed before; 1 passed after; strengthened absent-owner/no-op cases both pass |
| CR-03 endpoint repro, then immediate fix validation | 3 HTTP-500 failures before; 3 passed after (an earlier missing-location test-fixture error was corrected first) |
| CR-04 options repro, then immediate fix validation | 3 failed before; 3 passed after |
| Final targeted: `tests/test_task_queue.py tests/test_web_routes.py -q --tb=short` | **42 passed, 2 warnings, 8.12s**, exit 0 |
| Final full: `tests -q --tb=short` | **488 passed, 4 warnings, 67.74s**, exit 0 |
| Isolated browser: `tests/phase17_browser.py serve/browse --port 18793` | **12 interaction groups passed**, zero page errors; 10 screenshots at 375x812 / 1440x900 |

Final targeted storage: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-1474agdu`; full storage: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-nkdbps0c`. Browser evidence: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-browser-zj7gay5l/evidence.json`; preview storage: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-preview-c17lma52`. The initial browser attempt stopped on a preview-only detached ORM instance; capturing its scalar ID fixed the harness, and the fresh run passed. The dedicated preview was shut down; existing servers were not changed. Four recovery screenshots were inspected; automated overflow/focus checks ran at both sizes. Live model entitlement, output quality, human acceptance and independent re-review remain unverified. No phase/milestone completion is asserted.

## Original Evidence and Limits

The following is retained original-review evidence, not the later fix pass above.

- Independent diagnostics ran as four in-memory pytest items using an ephemeral plugin. The plugin was supplied to pytest.main from tests/run_phase17.py after that runner established disposable storage and its socket blocker, before pytest/application imports. No test file was created or modified.
- Invocation used the existing .venv/Scripts/python.exe with an in-memory launcher loading tests/run_phase17.py and selecting tests/test_web_routes.py as fixture context. Result: **4 passed, 2 deprecation warnings, 1.18s**. These assertions confirm the four defective current behaviors, not feature acceptance.
- Disposable root: C:/Users/melta/AppData/Local/Temp/jobot-17-04-tests-43t8yo3l. All credentials/content were test-only; generation was mocked and no service requests were made.
- The main orchestrator's **478 passed, 4 warnings, 56.79s** full-suite result is attributed evidence from the request and 17-05-SUMMARY addendum, not an independent rerun by this reviewer. The resolved legacy fixture failures are not outstanding findings.
- The eleven browser groups and eight 375/1440 screenshots are prior Plan 04 evidence. This review read the harness but did not rerun browsers, inspect screenshots, contact live providers, validate real credentials/entitlements, or establish human acceptance, output quality or savings.
- Cross-file inspection covered owner/global credential provenance, legacy probes, native/cloud JSON/text boundaries, stage dispatch, local-only vector resolution, validation-before-upsert, atomic preset/blank-key behavior and recovery paths. No additional confirmed in-scope credential disclosure, automatic provider substitution or provider-failure partial-vector overwrite was found. This is not a security certification or approval of excluded architecture.
- Source files, existing tests, completion state and Git were not modified. Only this review artifact was written; recommendations above have not been applied.

---

_Reviewer: GitHub Copilot, gsd-code-reviewer. Review only; phase completion is not asserted._