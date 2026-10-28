---
phase: 17-multi-provider-and-hybrid-local-cloud-ai-routing
plan: "03"
subsystem: ai-pipeline
status: complete
tags: [owner-routing, local-embeddings, safe-errors, non-destructive-vectors]
requires:
  - phase: 17-01
    provides: Provider adapters, safe errors and owner-aware generation/local factories
  - phase: 17-02
    provides: Encrypted owner vault and saved task assignments
provides:
  - Owner-aware scraping, queued scoring and REST applying dispatch
  - Separate fixed-local profile/job/feedback embedding paths
  - Explicit safe provider failures without heuristic, baseline or template success
  - Non-destructive finite-vector and collection-dimension validation
affects: [17-04, 17-05]
tech-stack:
  added: []
  patterns: [independent embedding injection, validate-before-write, explicit provider retry]
key-files:
  created: [.planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-03-SUMMARY.md]
  modified: [app/scrapers/ai_extractor.py, app/scrapers/query_strategist.py, app/scrapers/scheduler.py, app/queue/worker.py, app/ai/evaluator.py, app/ai/embeddings.py, app/ai/feedback.py, app/ai/application_generator.py, app/api/applications.py, tests/test_ai_scraping.py, tests/test_embeddings.py, tests/test_feedback.py, tests/test_evaluator.py, tests/test_application_generator.py, tests/test_profile_and_linkedin.py, .planning/STATE.md]
key-decisions:
  - Keep old positional arguments; use a separate keyword-only embedding_client override.
  - Resolve stage clients per owner and invocation rather than sharing account clients.
  - Provider failures remain failed until explicit existing queue retry; ordinary retry behavior is retained.
  - Validate a complete profile vector batch before any upsert and never reset incompatible collections.
  - Defer profile/LinkedIn API generation, owner-context wiring and UI work to Plan 04 as constrained.
requirements-covered: [REQ-HYB-01, REQ-HYB-04, REQ-HYB-05]
requirements-completed: []
actuals:
  tokens: null
  tasks: 3
  commits: 0
actuals-basis: No isolated initial shared-tree snapshot was captured; token cost is unmeasured rather than conflating earlier edits with this execution.
duration: Not measured; focused command durations recorded below
completed: 2026-10-27
---

# Phase 17 Plan 03: Pipeline Dispatch and Local Vectors Summary

Owner-scoped scraping/scoring/applying, independent local nomic-embed-text vector paths, and explicit non-destructive provider failures.

## Completed Tasks

1. Scraping and worker dispatch: extractor/strategist resolve scraping with owner context; query generation accepts the object envelope required by object-mode providers and legacy injected arrays. Invalid job/query output is an explicit safe error. Worker discovery uses scraping; owned queued evaluations use scoring. Two-account tests use actual saved Anthropic/Gemini scraping and OpenAI/Groq scoring assignments with independently mocked generation. Foreign-owned jobs do not reach resolution. Scheduler resolves distinct stage clients and clears its running flag on errors/cancellation. Typed failures propagate through nested website catches and gather results without success stats or replacement jobs.
2. Local vectors and scoring: profile writes, job similarity, feedback writes and feedback retrieval use get_embedding_client independently of generation. Existing positional generation arguments remain accepted but are not embedding overrides. Explicit embedding_client injection is separate. Evaluator carries owner/session/local client into both retrieval paths; feedback derives owner from the loaded job and rejects contradictory supplied ownership. Finite, nonempty, batch-consistent vectors must match existing dimensions before writes/queries. Mismatch requires an explicit backed-up re-index; no collection reset occurs. Provider and malformed-response errors bypass baseline evaluation and the outer rescore catch/purge. Failed operations preserve prior job/vector content.
3. Applications: both REST generation endpoints resolve the authenticated owner's applying client and inject it explicitly. Generator fallback resolution uses the record owner and rejects contradictory job/profile ownership before generation, even with injection. Existing tone/custom-instruction/prompt limits and positional arguments remain. Empty output and provider errors propagate without fabricated letters or achievements. REST returns bounded provider/model/category/status/message diagnostics with 502, or 503 for local unavailability/timeouts. Existing materials are neither created nor overwritten after failure.

## Verification

Every pytest process used a newly generated temporary directory for DATABASE_URL, CHROMA_DIR and ENCRYPTION_KEY_FILE before application imports, JOBOT_TESTING=1, ENV=testing and disabled telemetry. The PowerShell wrapper restored previous process environment afterward. The existing .venv/Scripts/python.exe ran pytest.main with the listed arguments; no installation/dependency changes occurred. Generation and embedding operations used independent mocks/spies. A socket guard blocked service connections, including local services; the only allowed socket.connect path was Windows' internal _fallback_socketpair for asyncio.

- Harness correction: the initial socket guard blocked asyncio's internal socket pair and failed fixture setup before assertions. The guard was narrowed to permit only that internal caller. This was not counted as behavioral RED evidence and made no provider request.
- Initial fixture corrections: new ownership tests required real registered accounts and a non-null job location. Those setup errors were repaired without weakening feature assertions.
- Scraping RED: forced 429 failed DID NOT RAISE because heuristic extraction succeeded. Worker RED: discovery selected scoring. Additional RED: empty JSON was accepted as a job. These assertions now pass, including nested website provider-error propagation.
- Vector RED: generation spy received three private profile embedding calls; feedback generation spy received one. GREEN separately proved zero cloud embeds in all four vector paths, owner derivation, invalid finite/empty vectors, existing-dimension mismatches, mixed batch dimensions and partial embedding outages with no destructive writes.
- Scoring RED: provider 429 failed DID NOT RAISE because deterministic fallback ran; stored-job/rescore preservation tests now pass. Malformed-output tests cover {}, arrays and invalid JSON.
- Applying RED: 429 returned a template; after generator repair, REST failure returned unhandled 500 instead of 502. GREEN covers both material types with 429, 402, invalid response and local outage, preserved old materials, owner conflict, prompt/tone behavior and empty responses.
- Final Task 1 target: tests/test_ai_scraping.py tests/test_parallel_execution.py tests/test_task_queue.py; **31 passed, 2 warnings in 8.29s** after documentation edits.
- Final Task 2 target: tests/test_embeddings.py tests/test_feedback.py tests/test_evaluator.py; **30 passed, 2 warnings in 3.87s** after documentation/fixture edits.
- Final Task 3 target: tests/test_application_generator.py tests/test_profile_and_linkedin.py; **28 passed, 2 warnings in 4.37s** after documentation edits.
- Final combined invocation: Invoke-JobotTests -TestArgs @('tests/test_ai_scraping.py','tests/test_parallel_execution.py','tests/test_task_queue.py','tests/test_embeddings.py','tests/test_feedback.py','tests/test_evaluator.py','tests/test_application_generator.py','tests/test_profile_and_linkedin.py','-q','-x','--tb=short','-o','addopts=').
- Final combined result: **89 passed, 2 warnings in 13.77s**. Warnings are Starlette/AnyIO and Chroma asyncio introspection deprecations.
- Editor diagnostics: no errors in all 15 touched Python files.
- Stub scan of the changed AI modules found only the existing prompt instruction prohibiting placeholder tokens, not a runtime stub. The deterministic HTML parser remains available for explicitly non-AI parsing, not provider-error recovery.

## Documentation Coverage

AST/token-based comment/docstring lines over nonblank production lines: extractor 31/169 (18.3%), strategist 25/135 (18.5%), scheduler 59/297 (19.9%), worker 58/324 (17.9%), evaluator 142/757 (18.8%), embeddings 34/166 (20.5%), feedback 33/164 (20.1%), generator 39/199 (19.6%), application API 34/188 (18.1%). Documentation explains the changed boundaries; several modules remain below the approximate 20-30% target. Full REQ-QUAL-01 acceptance is not claimed, and unrelated comment-only padding was avoided.

## Preservation and Deviations

No git staging, commits, branches, stash, reverts, installs or dependency edits. Commits: 0. No commit ledger, hashes, measured HEAD range or machine RED-evidence verdict is invented. The user's explicit dirty-shared-tree/no-git constraints override normal executor commit machinery. Tests supplied actual failing behavior assertions and focused GREEN results; strict committed/machine-classified GSD TDD compliance is not claimed.

The plan lists 13 Python files. Two existing adjacent test files were also updated under the user's explicit test-contract authorization: evaluator tests now use valid successful payloads instead of relying on malformed-output fallback and independently mock local vectors; profile/LinkedIn tests independently mock local generation and embeddings rather than contacting Ollama. Total changed Python files: 15 (nine production, six tests), plus this summary and the single STATE progress line. No source edits were made to app/api/profile.py, app/ai/linkedin_analyzer.py, app/api/settings.py, app/web/routes.py, adapters, vault, fixtures/conftest, manifests or templates.

The real worker dispatch boundary is _process_task, not the plan's obsolete _process_single_task name. Queue provider errors call existing mark_failed bookkeeping and then persist failed status without changing max_retries or model settings; the existing explicit retry action resets the task. Ordinary queue failure/retry semantics and existing loops/semaphores remain.

Provider failure is not a transaction spanning an entire discovery/rescore batch. Already successful earlier job/material/vector operations are left intact; a failed individual operation does not manufacture replacement content or delete/reset its stored data.

## Remaining Work and Risks

- Profile/LinkedIn API generation, inner bio/parser fallback removal, truthful partial-save/sync responses and web/UI diagnostics remain Plan 04 work under the explicit Execution Constraints. Their existing broad catches must not be mistaken for completed failure transparency.
- Shared vector helpers enforce local fixed-model resolution even for legacy callers, but legacy profile/LinkedIn/web callers still omit owner context. CV upload in app/api/settings.py passes its separately resolved owner-local client positionally; the new contract deliberately ignores positional generation overrides, so that call also needs explicit embedding_client/session/user_id wiring. Until that follow-up, those callers use the installation-local endpoint/token context, not necessarily the owner's local endpoint. This limitation was not hidden by changing out-of-scope call sites or accepting cloud generation as an embedding override.
- Existing global vector collection IDs/visibility and scheduler concurrent-session architecture were preserved as required; this plan does not certify vector account partitioning or redesign concurrency. The existing parallel/queue regression targets pass, but do not constitute a new production load test.
- Whole-phase requirements remain incomplete. No full-suite gate, browser acceptance, live provider/Ollama validation, credential entitlement, subjective application quality or cost savings were tested/claimed. Plans 04/05 own the remaining integration/UI/full-regression work.
- Operator documentation synchronization remains the explicit Plan 05 documentation task; this plan does not advertise an end-to-end shipped UI.
- Token cost and overall duration were not reliably measured. Per-command results above are actual observed outputs.

## Self-Check: PASSED

All 15 Python files and the three completed-plan summaries exist. The on-disk summary records the exact final 89-pass result, zero commits and outstanding acceptance limits. STATE preserves milestone v7.0 and an unchecked Phase 17 at 3/5 plans; no Plan 04/05 summary was created. No commit-existence check applies because commits were prohibited.