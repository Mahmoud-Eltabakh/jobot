---
phase: 17-multi-provider-and-hybrid-local-cloud-ai-routing
plan: "04"
subsystem: web-ui
status: complete
tags: [htmx, provider-vault, owner-routing, local-vectors, safe-recovery]
requires:
  - phase: 17-01
    provides: Provider adapters, safe errors and owner-aware factories
  - phase: 17-02
    provides: Encrypted vault, validated settings and exact preset mappings
  - phase: 17-03
    provides: Owner pipeline dispatch and independent local vector helpers
provides:
  - Eight independent write-only provider forms and explicit model suggestions
  - Persisted task selectors, exact presets and visible rejected-preset feedback
  - Escaped provider failure panels with separate local switch and owned retry
  - Owner-scoped profile, LinkedIn, bio and local-vector boundaries
affects: [17-05]
tech-stack:
  added: []
  patterns: [provider-local HTMX targets, persisted Jinja block rendering, explicit local recovery]
key-files:
  created: [tests/run_phase17.py, tests/phase17_browser.py, .planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-04-SUMMARY.md]
  modified: [app/web/routes.py, app/api/settings.py, app/api/profile.py, app/ai/linkedin_analyzer.py, app/ai/profile_extractor.py, templates/base.html, templates/components/settings.html, templates/components/job_inspector.html, templates/components/queue_view.html, tests/test_web_routes.py, tests/test_auth_security.py, tests/test_profile_and_linkedin.py, .planning/STATE.md]
key-decisions:
  - Render presets from the existing settings template's reusable ai_routing block.
  - Keep model inputs editable and populate escaped datalists only after explicit tests.
  - Return partial status when an ordinary profile save succeeds but local vectors fail.
  - Require CV and LinkedIn vector preparation before persisting their imported profile.
  - Keep routing changes and generation/queue retry separate and owner-checked.
requirements-covered: [REQ-HYB-05, REQ-HYB-06, REQ-UI-01, REQ-QUAL-01]
requirements-completed: []
actuals:
  tokens: null
  tasks: 3
  commits: 0
actuals-basis: No isolated initial shared-tree snapshot was captured; token cost is unmeasured rather than attributing prior dirty changes to this plan.
duration: Not measured; observed focused test timings are recorded below
completed: 2026-10-28
---

# Phase 17 Plan 04: Provider Settings and Manual Recovery Summary

Eight owner-isolated provider forms, persisted hybrid routing, explicit local recovery, and truthful profile/vector failure handling with real HTMX browser evidence.

## Completed Tasks

1. Provider credentials UI: Ollama, OpenAI, Anthropic, Gemini, Groq, DeepSeek, OpenRouter and Custom have unique forms, labels, blank password values, independent Saved/Not configured metadata, own live status and own test target. Submitted secrets clear only after their successful save. Opening Settings performs no provider/model checks. Explicit tests send only provider/api_key/base_url/model, disable their own initiating button and populate escaped zero/one/many suggestions without changing the editable model. Provider models persist independently; matching-owner legacy custom-model compatibility remains. Remote-access, concurrency, scraper and blacklist settings remain in place.
2. Routing: three independent provider/model pairs persist and are re-rendered from the existing Jinja block. Exact labels remain 100% Free / Local, Cost-Optimized Hybrid and Max Quality Cloud. Mappings remain Plan 02's six-field tuples. Missing OpenAI credentials return visible 422 feedback without assignment writes or cleared inputs. Successful routing swaps preserve unrelated credential entries and command focus. Embeddings display Ollama / nomic-embed-text / Local / zero-token cost; initial state is Unchecked and an explicit authenticated local model-presence check returns Connected or Unavailable. This is not a paid generation or embedding-quality certification.
3. Recovery and profile boundaries: both web application generators inject the owner's applying client and escape generated textareas. Bounded escaped provider/model/category/status diagnostics expose auth/quota/rate-limit/timeout guidance. The inspector reads the latest matching owner failed evaluation task; queue errors retain their existing source. Switch to Local Ollama changes assignments only and explicitly reports all three changed; generation and owned queue Retry remain separate commands. Foreign job generation and queue retry return 404 before resolution. Bio/LinkedIn/CV parsing no longer fabricates success after provider failures; empty JSON profiles are rejected. Web/API bios use owner scraping, rescore uses owner scoring, and every changed vector boundary supplies the owner/session and separate fixed-local embedding client. An ordinary saved profile reports partial when vectors fail. CV/LinkedIn import vectors are prepared before profile persistence; failed local vectors preserve the prior profile. Explicit non-AI parsing stays offline.

## Verification

Every pytest process used tests/run_phase17.py with a fresh temporary DATABASE_URL, CHROMA_DIR and ENCRYPTION_KEY_FILE set before application imports, JOBOT_TESTING=1, ENV=testing and disabled telemetry. Parent environment is unchanged. The existing .venv/Scripts/python.exe was used without installs. New generation/model operations use independent mocks; a socket guard blocks service connections, allowing only Windows asyncio's internal socket pair. Legacy web probes now have explicit mocks as well. No production storage, real credentials or paid generation was used.

- Settings RED: opening Settings called forbidden Ollama discovery. GREEN proved eight unique forms, empty secret values, preserved unrelated sections and no discovery.
- Routing RED: presets returned only a span instead of saved selectors. GREEN proved reusable persisted fragments and 422 feedback retargeting with unchanged settings.
- Profile RED: quota produced a fallback bio; vector failure returned status ok. LinkedIn also swallowed quota. GREEN proved propagation, truthful partial status and owner-local dispatch. Empty-object profile outputs separately failed DID NOT RAISE before parser guards were added.
- Web RED/GREEN: missing explicit applying resolution and raw textarea output were covered by 429/402/timeout tests and malicious generated text. Six failure cases plus escaping passed after repair.
- Recovery RED: inspector lacked local-switch controls. Later ownership RED exposed a foreign queue retry returning a success-shaped 200; it now returns 404 before retry.
- Source slices were followed immediately by their focused checks. Local repairs included the verified task_type factory keyword, typed-error preservation for metadata-free injected mocks, matching legacy custom-model fallback and retaining offline parsing when no client is supplied.
- Final command: `.venv/Scripts/python.exe tests/run_phase17.py tests/test_web_routes.py tests/test_auth_security.py tests/test_htmx_views.py tests/test_profile_and_linkedin.py tests/test_cv_parser.py -q -x --tb=short`.
- Final result: **135 passed, 4 warnings in 22.33s**. Warnings are Starlette/AnyIO, Chroma asyncio introspection and existing per-request test-cookie deprecations.
- Editor diagnostics: no errors in all ten touched Python files.
- Authenticated API/web factory-call scan shows owner/session at every call. No TODO/FIXME/coming-soon markers were found in the touched production surfaces.

## Browser Evidence

Final command used the existing webapp-testing with_server.py helper to start tests/phase17_browser.py serve on unused localhost port 18765 and run its browse mode. The server used newly generated disposable DB/vector/key paths before imports, disabled scheduler/worker loops and mocked every AI adapter's health/generation/embedding methods. Tests used fake credentials only. Existing user uvicorn was not touched.

Final artifacts: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-browser-ysyuzhtt/`.

| Artifact | Exact viewport | Evidence |
| --- | --- | --- |
| settings-375.png / settings-1440.png | 375x812 / 1440x900 | Real Settings navigation, eight providers, partial configuration, blank saved password, long model input and independent status |
| routing-375.png / routing-1440.png | 375x812 / 1440x900 | Persisted three-stage routing and local embeddings controls |
| failure-375.png / failure-1440.png | 375x812 / 1440x900 | Long escaped provider/model diagnostics, manual local switch feedback and independent Retry |
| queue-375.png / queue-1440.png | 375x812 / 1440x900 | Owned queue after the separate explicit retry |
| evidence.json | Both viewports | Eleven passing interaction groups, exact layout numbers and zero page errors |

Automated browser checks passed: real nav/HTMX, zero automatic provider checks, all eight provider-only POSTs, independent targets, disabled loading button, zero/one/many suggestions without automatic selection, credential non-reflection, saved secret clearing, all three presets including visible missing-key 422, six-field persistence after navigation, preserved credential inputs/focus, explicit local embedding status, keyboard Tab navigation, 429 inspector failure, switch without generation or retry, separate local generation with escaped malicious textarea text, queue switch retaining failed status, separate queue Retry to pending, and visible profile bio provider failure.

At 375px, document scrollWidth=375 and provider section scrollWidth/clientWidth=293/293. At 1440px, document scrollWidth=1440 and provider section=1166/1166. Failure and queue views also passed document overflow checks. Final screenshots were visually inspected; long diagnostics wrap and recovery controls remain reachable by scrolling. Page errors: **0**.

Browser-discovered repairs: provider Test Connection needed its own disabled selector; the pre-existing fixed-height mobile header overflowed to 893px and now wraps below 640px; queue switch feedback inherited outerHTML and now uses preserved innerHTML feedback; separate queue retry inherited outerHTML and removed the shared navigation target, now explicitly retained; profile non-2xx HTML required a narrow beforeSwap handler. A Windows helper cleanup issue initially left one test-created child process; its command line was verified before stopping it. The harness now explicitly requests its own server shutdown even on failure. Final acceptance server 18765 was stopped and no listener remained.

## Persistent Disposable Demo

Fresh preview remains running at **http://127.0.0.1:18764/__preview**. This demo URL creates only the disposable demo session. Terminal ID: ffd491cf-11ab-4617-9da5-0b844304f2f7. Storage: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-preview-_6pc7dx0/`. It is localhost-only, has disabled workers and mocked providers; do not enter real credentials. It is not the existing production/development uvicorn instance. Test-only preview login/state/shutdown routes exist only when running the harness, not normal app startup.

## Preservation and Deviations

No staging, commits, branches, stash, reverts, installs or dependency changes. Commits: **0**. No Git ledger, hashes, isolated token count or strict committed GSD TDD verdict is invented. Prior/user changes were preserved. Only this plan's source/test surfaces, this summary and STATE's Phase 17 progress line were changed. Milestone v7.0 remains; Phase 17 is unchecked with 4/5 plans. Plan 17-05 was not executed, no phase-wide requirements were marked complete, and ROADMAP/REQUIREMENTS/operator manuals were not updated by this run.

Adjacent necessary additions: profile_extractor.py removes the inner bio/parser synthetic-success catches; base.html handles demonstrated mobile header overflow and profile error swapping; the two new test harness scripts enforce disposable testing and repeatable browser evidence. These are required integration/safety repairs, not a frontend stack or architecture change. Documentation-suite synchronization remains the explicit Plan 17-05 task.

## Remaining Acceptance Limits

- No live provider/Ollama entitlement, credential acceptance, paid generation, subjective application quality or measured cost savings were tested or claimed.
- Full-suite regression, operator documentation, independent review and phase completion remain Plan 17-05 work. No human acceptance is claimed.
- Meaningful docstrings explain changed boundaries, but repository-wide approximate 20-30% comment/docstring coverage was not certified; REQ-QUAL-01 is not marked fully accepted.
- Existing global vector collection IDs/visibility and cross-store atomicity were not redesigned. Successful earlier vector work is not rolled back if a later unrelated database operation fails. No destructive re-index or collection reset occurred.
- The UI uses the existing Tailwind/HTMX CDNs. Browser evidence is automated Chromium evidence, not an exhaustive assistive-technology/device audit. No required browser check in this plan remains unrun.

## Known Stubs

None preventing the plan's goal. Mock adapters and preview-only routes are confined to the explicitly disposable test harness, not production fallbacks.

## Threat Flags

| Flag | File | Description |
| --- | --- | --- |
| threat_flag: endpoint | app/api/settings.py | New explicit authenticated local embedding model-presence check; fixed local resolver, no paid generation, no credential output. |

## Self-Check: PASSED

Executable Node assertions verified all 14 implementation/test artifacts, the exact 135-pass result, eleven browser check groups, eight PNG headers with exact 375x812/1440x900 dimensions, zero page errors, milestone v7.0, unchecked Phase 17 at 4/5 and no Plan 17-05 summary. The persistent disposable preview's GET /health returned status ok. No commit-existence check applies because Git mutations were forbidden.