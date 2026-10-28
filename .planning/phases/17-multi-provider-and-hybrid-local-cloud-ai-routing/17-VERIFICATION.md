---
phase: 17-multi-provider-and-hybrid-local-cloud-ai-routing
verified: 2026-10-28T05:05:32Z
status: passed
score: 31/31 must-haves verified
verified_truths: 31
total_truths: 31
behavior_unverified: 0
overrides_applied: 0
code_goal_assessment: achieved
implementation_blockers: 0
commits: 0
decision_coverage:
  honored: 11
  total: 11
  not_honored: []
requirements_verified:
  - REQ-HYB-01
  - REQ-HYB-02
  - REQ-HYB-03
  - REQ-HYB-04
  - REQ-HYB-05
  - REQ-HYB-06
  - REQ-QUAL-01
  - REQ-QUAL-02
  - REQ-UI-01
covered_files:
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-01-PLAN.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-01-SUMMARY.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-02-PLAN.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-02-SUMMARY.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-03-PLAN.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-03-SUMMARY.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-04-PLAN.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-04-SUMMARY.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-05-PLAN.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-05-SUMMARY.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-REVIEW.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-SECURITY.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-UAT.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-UI-REVIEW.md"
  - ".planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-VALIDATION.md"
  - "README.md"
  - "app/ai/application_generator.py"
  - "app/ai/client.py"
  - "app/ai/embeddings.py"
  - "app/ai/evaluator.py"
  - "app/ai/feedback.py"
  - "app/ai/linkedin_analyzer.py"
  - "app/ai/profile_extractor.py"
  - "app/api/applications.py"
  - "app/api/profile.py"
  - "app/api/settings.py"
  - "app/core/config.py"
  - "app/db/database.py"
  - "app/queue/task_queue.py"
  - "app/queue/worker.py"
  - "app/scrapers/ai_extractor.py"
  - "app/scrapers/query_strategist.py"
  - "app/scrapers/scheduler.py"
  - "app/web/routes.py"
  - "docs/CONTRIBUTING.md"
  - "docs/USER_MANUAL.md"
  - "templates/base.html"
  - "templates/components/job_inspector.html"
  - "templates/components/queue_view.html"
  - "templates/components/settings.html"
  - "tests/conftest.py"
  - "tests/phase17_browser.py"
  - "tests/run_phase17.py"
  - "tests/test_ai_client.py"
  - "tests/test_ai_scraping.py"
  - "tests/test_application_generator.py"
  - "tests/test_auth_security.py"
  - "tests/test_config.py"
  - "tests/test_db.py"
  - "tests/test_e2e_workflow.py"
  - "tests/test_embeddings.py"
  - "tests/test_evaluator.py"
  - "tests/test_feedback.py"
  - "tests/test_linkedin_auth.py"
  - "tests/test_parallel_execution.py"
  - "tests/test_profile_and_linkedin.py"
  - "tests/test_scheduler.py"
  - "tests/test_task_queue.py"
  - "tests/test_vector.py"
  - "tests/test_web_routes.py"
covered_digest: "v3:sha256:71d69c680e71808f70f76dc56994ff4f3af817b12c4c78345f7e815cbb9c3767"
---

# Phase 17: Multi-Provider and Hybrid Routing Verification

**Phase Goal:** Decouple AI execution into task-based stages (Scraping, Scoring, Applying) with an encrypted multi-provider credential vault (Ollama, OpenAI, Anthropic, Gemini, Groq, DeepSeek, OpenRouter), local-pinned embeddings, explicit failure transparency, and 1-click cost-saving presets.
**Verified:** 2026-10-28T05:05:32Z
**Status:** passed
**Re-verification:** Fresh verification after the four findings resolved in the current `17-REVIEW.md`.

## Verdict and Scope

The Phase 17 goal is achieved. All 30 PLAN-frontmatter truths and the explicitly reviewed REQ-QUAL-01 criterion are verified. No confirmed implementation blocker remains. All six HYB requirements have concrete implementation and regression evidence. This does not certify production entitlement, subjective output quality, measured savings, or exhaustive accessibility.

All three checks in `17-UAT.md` are complete and passed, including human visual/keyboard acceptance, documentation assessment, and operator confirmation of endpoint/model testing. The UI review's P2 mobile rescore-layout advisory remains disclosed, but is not an outstanding acceptance task or a must-have failure.

The five PLAN/SUMMARY pairs, REQUIREMENTS, STATE, ROADMAP, UAT, VALIDATION, SECURITY, UI-REVIEW, and the fresh REVIEW were read. SUMMARYs and prior verifier prose were treated as claims, not proof. Current source and a fresh focused run corroborate the four newly resolved findings.

ROADMAP defines a goal and six requirements, but no separate success-criteria array. The contract below preserves all **30 PLAN-frontmatter truths**, including overlapping UI/test truths rather than reducing scope. T31 adds REQ-QUAL-01, accepted in UAT. No plan declares `must_haves.prohibitions`, `verification: backstop`, or MVP mode. No overrides were applied.

## Goal Achievement

### Observable Truths

`VERIFIED` below means the stated code/test behavior, not real provider availability or human approval. Test names are in the fingerprinted existing test modules. E1..E5 identify this verifier's independent executions below; E4 includes every active regression test named here.

| ID | Source | Observable Truth | Status | Evidence |
| --- | --- | --- | --- | --- |
| T01 | 17-01 | Base clients preserve JSON/text, health details and downstream domain validation. | VERIFIED | [client.py](app/ai/client.py#L117), native response parsing and `_validated_content`; `test_all_provider_generation_wire_contract`, native invalid-content and domain malformed-output tests pass in E4. |
| T02 | 17-01 | OpenAI, Groq, DeepSeek and OpenRouter use the existing compatible SDK and intended defaults. | VERIFIED | `PROVIDER_DEFAULTS`, `OpenAICompatibleClient`, endpoint and wire-contract assertions in [test_ai_client.py](tests/test_ai_client.py#L486); E4. |
| T03 | 17-01 | Anthropic and Gemini have direct lightweight HTTPX adapters. | VERIFIED | Native POST serialization, header authentication, system prompts, JSON mode and thought/refusal/truncation handling in [client.py](app/ai/client.py#L239); transport assertions, E4. No new SDK/framework needed. |
| T04 | 17-01 | Legacy factory calls survive; tasks resolve owner credentials; unknown IDs reject. | VERIFIED | [get_ai_client](app/ai/client.py#L650); owner/global/foreign-key, positional/user-id-only and task-precedence tests, E4. CR-02 provider-default cases also pass E3. |
| T05 | 17-02 | Provider keys are encrypted at rest, including optional Ollama tokens. | VERIFIED | `PROVIDER_SECRET_KEYS` forces owner encryption in [database.py](app/db/database.py#L210); `test_all_provider_credentials_save_encrypted_and_blank_preserves` asserts all eight ciphertext slots, E4. |
| T06 | 17-02 | Blank secrets preserve existing keys without HTML reflection. | VERIFIED | Blank secret early return, atomic save validation and write-only forms; ciphertext equality/non-reflection tests, E4. |
| T07 | 17-02 | Each provider has an independent connectivity-test endpoint. | VERIFIED | `/test-provider`, `_provider_client`, `_health_details`; eight-provider GET-only/header/redirect/deadline tests, E4. Reachability is explicitly not generation entitlement. |
| T08 | 17-02 | Task mappings and presets persist owner choices atomically. | VERIFIED | `_validated_ai_values`, `set_user_settings`, `/ai/preset`; exact tuples, commit rollback and mid-flush two-owner snapshots, E4/E5. |
| T09 | 17-03 | AI DOM extraction resolves the scraping assignment. | VERIFIED | [extract_from_html](app/scrapers/ai_extractor.py#L90) calls owner/task factory when not injected; `test_extractor_routes_owned_scraping` and error/no-heuristic tests, E4. This verifies the existing helper, not a new site-wide extraction integration. |
| T10 | 17-03 | Evaluator and queue evaluation resolve scoring independently. | VERIFIED | Owned job lookup precedes factory; [worker.py](app/queue/worker.py#L268), [evaluator.py](app/ai/evaluator.py#L593); actual saved-route transport workflow, E1. |
| T11 | 17-03 | Cover-letter and resume generation resolve applying. | VERIFIED | Both REST and web entry points inject owner applying; generator fallback derives/validates record owner; E1/E3/E4. |
| T12 | 17-03 | Application vectors stay on Ollama/nomic-embed-text with dimension guards. | VERIFIED | Independent [get_embedding_client](app/ai/client.py#L634), vector batch validation, four populated vector paths in E1 and timeout/dimension preservation in E2/E4. Zero cloud embedding requests; no claim of zero hardware/energy cost or compatible pre-existing collections. |
| T13 | 17-03 | Provider failures retain safe diagnostics without silent failover or synthetic success. | VERIFIED | Allowlisted `AIProviderError`, typed propagation before mutation/purge, one-commit terminal queue failure; E2/E3/E4. Prior score/material/vector snapshots survive tested provider failures. |
| T14 | 17-04 | Settings renders eight credential items with individual test controls. | VERIFIED | [settings.html](templates/components/settings.html#L98), safe `provider_configs`; API/template assertions E4 and inspected browser groups 1/6. |
| T15 | 17-04 | Scraping, Scoring and Applying have independent provider/model selectors. | VERIFIED | `ai_routing` Jinja block and owner `_routing_settings`; E1/E3/E4 plus browser group 4. |
| T16 | 17-04 | The three requested presets immediately refresh task controls. | VERIFIED | `/ai/preset` returns the persisted Jinja routing block; exact local/hybrid/cloud tuples in E4; browser group 3. Product labels are not quality/savings measurements. |
| T17 | 17-04 | The embedding display identifies fixed local, zero-token routing truthfully. | VERIFIED | Literal Ollama/nomic/local row, initial Unchecked and explicit model-list check; E4/browser group 7. Connected is a model-presence/reachability signal, not proof of embedding quality or economic savings. |
| T18 | 17-04 | Inspector and Queue show safe failures, local switch and separate retry. | VERIFIED | Owned failed-task query, escaped template diagnostics, assignment-only preset and owned retry routes; E2/E3/E4; browser groups 10/11. |
| T19 | 17-04 | A provider test updates its own live status without returning saved keys. | VERIFIED | Provider-local targets and four-field test POST; E4 and browser groups 5/6. |
| T20 | 17-04 | Stored password values are empty; saved state is metadata only. | VERIFIED | `value=""`, `has_key` and Saved/Not configured state; E4, browser groups 1/4. Unsaved fake values typed by the harness are distinct from reflected stored values. |
| T21 | 17-04 | Preset success refreshes all six persisted assignment values. | VERIFIED | Exact DB assertions in preset tests; reusable response block and browser navigation round-trip, E4/browser groups 3/4. |
| T22 | 17-04 | Partial credential configuration leaves all providers independently usable. | VERIFIED | Eight separate forms, transient submitted-key probes and per-owner key lookup; E4/browser groups 1/6. |
| T23 | 17-04 | Zero/one/many discovered models never silently replace the chosen model. | VERIFIED | Editable input with escaped datalist; `test_explicit_discovery_keeps_editable_model`, E4; browser group 5. |
| T24 | 17-04 | Missing-key presets show visible 422 feedback and preserve assignments. | VERIFIED | Validation before any write, HX-Retarget/HX-Reswap and explicit error swapping; E4/browser group 2. |
| T25 | 17-04 | Tested loading/empty/saved/error/partial UI states are keyboard-reachable and do not overflow at 375/1440. | VERIFIED | Existing browser checks and completed UAT visual/keyboard acceptance. This does not certify exhaustive screen-reader, assistive-technology, or device coverage. |
| T26 | 17-05 | Adapter tests exercise successful generation, JSON and network failures. | VERIFIED | Independent expected wire payloads, native invalid-content/timeouts and eight-provider hostile-response cases; E4. |
| T27 | 17-05 | Integration proves three distinct saved stage backends. | VERIFIED | [test_saved_three_stage_workflow_and_all_vectors_use_owner_transports](tests/test_e2e_workflow.py#L292): Anthropic discovery, Groq scoring, Gemini web/REST applying, real temporary DB/Chroma and mocked network only; E1. |
| T28 | 17-05 | Tests prove local vectors never call cloud embedding APIs. | VERIFIED | Eight expected local embedding calls in E1; populated profile/similarity/feedback-write/feedback-query failure matrix in E4. This is helper/transport evidence, not a claim that Phase 17 newly wired every historical feedback workflow. |
| T29 | 17-05 | Rate/quota failures become explicit records without automatic model switching. | VERIFIED | E2 covers 429/402/timeout/dimension failure and separate recovery; E3 proves no committed claimable provider-failure interval. |
| T30 | 17-05 | The full regression suite executes with every test passing. | VERIFIED | Latest isolated result: 673 passed, 4 existing deprecation warnings on Python 3.14.7, as supplied for this verification and recorded in VALIDATION. This verifier did not rerun the full suite. |
| T31 | QUAL-01 | Changed source meets the approximate meaningful comment/docstring contract. | VERIFIED | UAT documentation assessment passed. This is human acceptance of incremental meaningful documentation, not a claim that every module meets a numeric ratio. |

**Score: 31/31 truths verified; 0 present-but-behavior-unverified truths.** The four newly resolved behavior claims have current source evidence and named passing regressions; remaining external/quality limits are listed below.

### Current Verification Run

The focused command used `tests/run_phase17.py`, which established disposable database/vector/key paths and blocked service sockets before application imports. It ran the named deadline, discovery, endpoint, vector-preservation, and feedback-owner tests with mocked transports: **21 passed, 2 warnings, 3.41s**. A separate in-memory hanging-fetch probe shortened the wrapper deadline and confirmed discovery cancellation maps to `AIProviderError(category="timeout")`. The latest full isolated suite result was supplied for this verification and recorded in VALIDATION: **673 passed, 4 existing deprecation warnings on Python 3.14.7**; it was not rerun here.

### Four Newly Resolved Findings

| Finding | Current source evidence | Behavioral evidence |
|---|---|---|
| Python-compatible request, health, and discovery deadlines | `asyncio.wait_for` is used by `_with_timeout`, native whole-request handling, adapter health and paginated model listing in [client.py](app/ai/client.py); the settings health boundary also uses `wait_for` in [settings.py](app/api/settings.py). Workspace search found no `asyncio.timeout` in application Python. | Fresh named request/health deadline cases and model-list transport/pagination regressions passed. Discovery listing calls are wrapped through `_with_timeout`; Python 3.10 itself was not executed. |
| Preserve old profile vectors when replacement upsert fails | [embeddings.py](app/ai/embeddings.py) completes replacement upsert before calculating/deleting stale owner IDs. | `test_profile_upsert_failure_preserves_stale_owner_vectors` injects the upsert error and checks prior IDs, documents, metadata, and embeddings remain unchanged; passed. |
| Owner-scoped feedback count and retrieval | [feedback.py](app/ai/feedback.py) supplies the same owner filter to count and similarity retrieval. | `test_other_owners_feedback_does_not_trigger_embedding` verifies another owner's vector yields neutral output without an embedding call; passed. |
| Canonical OpenAI endpoint with explicit Custom support | [client.py](app/ai/client.py) rejects a noncanonical legacy OpenAI endpoint; [settings.py](app/api/settings.py) fixes provider probe hosts while validating explicit Custom URLs. | Owner legacy probe, OpenAI factory, fixed-cloud override, and LAN Custom endpoint regressions passed. |

The fresh [17-REVIEW.md](.planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-REVIEW.md) records all four findings resolved, zero open findings, and clean status. The direct source/test checks above corroborate that assessment.

### Required Artifacts

All listed artifacts exist and contain substantive implementations, not stubs. Wiring/data-flow conclusions are manual source traces backed by the named tests, not the shallow GSD parser result.

| Artifact | Substantive Implementation and Wiring | Status |
| --- | --- | --- |
| [app/ai/client.py](app/ai/client.py) | Four adapters, eight defaults, safe error type, generation and independent embedding factories; imported by settings, worker, domain services and routes. | VERIFIED |
| [app/core/config.py](app/core/config.py) | Eight-provider Literal; used by settings/database/factory. | VERIFIED |
| [app/db/database.py](app/db/database.py) | Owner-encrypted keys, idempotent migration, deferred/batched commit and rollback; called by authenticated settings saves/presets. | VERIFIED |
| [app/api/settings.py](app/api/settings.py) | Owner vault/probes/routing/presets, CV dispatch and safe rescore feedback; consumed by real HTMX forms and REST tests. | VERIFIED |
| [app/scrapers/ai_extractor.py](app/scrapers/ai_extractor.py) | Owner-aware extraction entry point with domain validation; existing helper routing tested directly. No new promise of integration into every site scraper. | VERIFIED for declared helper contract |
| [app/ai/evaluator.py](app/ai/evaluator.py) | Owned scoring and local retrieval, errors escape before score mutation/purge; called by worker/scheduler/rescore. | VERIFIED |
| [app/ai/application_generator.py](app/ai/application_generator.py) | Owner consistency, applying generation and post-success persistence; both material types called by REST/web. | VERIFIED |
| [app/ai/embeddings.py](app/ai/embeddings.py), [app/ai/feedback.py](app/ai/feedback.py) | Independent local factory and finite/batch/existing-dimension validation; profile routes and evaluator retrieval supply owner context. | VERIFIED within existing vector architecture |
| [templates/components/settings.html](templates/components/settings.html), [templates/components/job_inspector.html](templates/components/job_inspector.html), [templates/components/queue_view.html](templates/components/queue_view.html) | Actual Jinja/HTMX targets, provider forms, owned errors and separate actions rendered by web routes. | VERIFIED; UAT acceptance recorded |
| [tests/test_ai_client.py](tests/test_ai_client.py), [tests/test_auth_security.py](tests/test_auth_security.py), [tests/test_e2e_workflow.py](tests/test_e2e_workflow.py) | Active protocol, credential, rollback and transport-backed workflow assertions; included in E4. | VERIFIED |
| [docs/USER_MANUAL.md](docs/USER_MANUAL.md), [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md), [README.md](README.md) | Actual fields, eight IDs, exact presets, local requirements, guard/retry/entitlement/re-index limitations match source. | VERIFIED for Phase 17 documentation |

The installed `verify.artifacts`/`verify.key-links` queries were attempted for all five plans. The shorthand string lists produced zero evaluated entries, with `all_passed: false`/`all_verified: false`; Plan 05 has no key-links block. These results are **not** missing-code evidence or automated verification success. The tables here supply the otherwise unevaluated existence/substance/wiring checks. No commit-existence check applies: no commits were authorized and no summary hashes are invented.

### Key Links and Authenticated Call-Site Trace

| From | To / Owner and Stage | Evidence and Boundary |
| --- | --- | --- |
| Provider/stage/preset forms | Authenticated settings handlers -> validation -> owner UserSetting batch -> refreshed Jinja block | Credential values are not response data. Required keys checked before preset writes. E4/E5 and actual browser HTMX. |
| Test Provider / legacy Test AI / models | Owner or explicit transient key -> selected validated host -> bounded GET-only probe | No global/foreign secrets, fixed cloud probe hosts, saved token endpoint binding, redirect blocking. Old/new route and hostile-header/HTML tests pass E4. |
| Authenticated `/api/scrapers/run` | New worker Session + `current_user.id` -> pipeline scraping and scoring factories | [scrapers.py](app/api/scrapers.py#L40); independent stage resolution in [scheduler.py](app/scrapers/scheduler.py#L156). Existing semaphore/session architecture is not newly certified. |
| Owned discovery/evaluation task | `task.user_id` -> scraping strategist / scoring evaluator | Record lookup precedes scoring resolution; E1/E2. Provider failures use `terminal=True`, one commit; E3. |
| CV upload | `current_user.id` -> scraping extraction/bio; separate owner local vector client -> profile save | [settings.py](app/api/settings.py#L730); explicit `embedding_client=`, session and owner. No profile write/HX-Redirect after tested generation failure; vector work precedes import persistence. E4/E5. |
| Profile API/web updates | Current owner -> fixed local embedder | Explicit owner/session/embedding keyword at both call sites. Ordinary profile save may already be durable: failure reports partial/unsynchronized, not atomic success. E4/E5. |
| LinkedIn API/web sync | Current owner -> analyzer scraping client -> inner analysis/bio injection -> owner local vectors -> profile persistence | [linkedin_analyzer.py](app/ai/linkedin_analyzer.py#L493); E4/E5 preserve previous profile on injected vector failure. LinkedIn network extraction fallbacks are not model failover. |
| Profile API/web bio | Owner scraping client -> `generate_candidate_bio(..., ai_client)` | Legacy zero-argument helper fallback is not used by these authenticated boundaries. Safe provider errors propagate; REST old-bio preservation and browser visible web failure are covered. |
| Settings/profile rescoring | Current owner scoring client -> evaluator -> separate local similarity/feedback retrieval | Factory and runtime errors handled; E3 preserves previous score/summary/evidence. Rescore stops before the post-loop purge on provider error. |
| REST/web cover letter/resume | Owned job + owner profile -> applying client -> successful generation -> save | E1/E2/E3. Generator also rejects contradictory record owners. Cover-letter retry includes the stable original options form. |
| Inspector/Queue switch | Owner preset -> exactly six assignments | No generation, enqueue or retry. Subsequent owned retry is a different request; foreign job/task requests reject before resolution, E2/E4. |
| Vector helpers | Profile/job/feedback text -> separate owner Ollama/nomic client | Legacy positional generation injection is deliberately not a vector override. Explicit test-only `embedding_client` injection is separate. E1/E2/E4. |

The pre-existing scheduled `_periodic_task` remains a trusted installation-level invocation with no account argument; this report does not pretend every legacy/non-authenticated caller is owner-scoped. The two legacy unscoped profile-analysis/bio helpers receive an explicitly resolved client from their authenticated call chains. No new automatic cross-provider retry exists.

### Data-Flow Trace (Level 4)

| Rendered Data | Real Source and Flow | Status |
| --- | --- | --- |
| Saved provider state | Owner UserSetting SELECT/decryption -> boolean has_key -> safe provider_configs -> Jinja Saved/Not configured | FLOWING; stored secret never rendered |
| Three stage assignments | Owner task rows or shared non-secret defaults -> `_routing_settings` -> reusable Jinja block; form saves commit owner rows | FLOWING; CR-02 API/factory/rendered parity checked |
| Provider test status/models | Selected transient adapter GET response -> safe allowlisted health/category -> escaped live fragment/datalist | FLOWING in implementation; transport-mocked in verification |
| Embedding status | Explicit owner Ollama model listing -> nomic presence predicate -> Connected/Unavailable | FLOWING; not an actual embedding-quality or model-entitlement test |
| Inspector evaluation failure | Current-owner failed evaluate task + matching job payload -> escaped error banner | FLOWING; no invented Job error field |
| Queue diagnostics/retry state | Owned ScrapeTask SELECT -> error/status -> switch-only preset or independent retry -> pending row | FLOWING; browser row captures occur after retry |
| Application contents | Owner applying generation -> validated nonempty text -> owner material persistence -> escaped textarea | FLOWING; hostile closing-textarea/script output tested |

Empty initialization state and editable defaults are populated by the documented queries/actions, not static success fallbacks. Existing MockAIClient and preview fixtures are test utilities, not factory-selected production providers.

## Independent Behavioral Evidence

All five invocations below used **exactly** `.venv\Scripts\python.exe tests/run_phase17.py` before the listed arguments. The runner was inspected: unique disposable DATABASE_URL/CHROMA_DIR/ENCRYPTION_KEY_FILE and JOBOT_TESTING are set before pytest/application imports; socket connections are blocked except Windows asyncio's internal `_fallback_socketpair`. Installed SDK and native HTTP backends are both intercepted by the transport fixture. Background loops are disabled. Fake keys only; no real service calls, production storage, installs or source/test edits.

| ID | Arguments After the Guarded Runner | Independent Result | Disposable Root Suffix under Windows Temp |
| --- | --- | --- | --- |
| E1 | `tests/test_e2e_workflow.py::test_saved_three_stage_workflow_and_all_vectors_use_owner_transports -q --tb=short` | 1 passed, 2 warnings, 2.61s; exit 0 | `jobot-17-04-tests-oe839kox` |
| E2 | `tests/test_e2e_workflow.py::test_failure_preservation_and_separate_owned_local_switch_retry -q --tb=short` | 4 passed, 2 warnings, 4.03s; exit 0 | `jobot-17-04-tests-rwdgcaau` |
| E3 | `tests/test_task_queue.py::test_provider_failure_never_commits_claimable_task tests/test_web_routes.py::test_installation_provider_defaults_match_owner_routing tests/test_web_routes.py::test_settings_rescore_safe_failure_preserves_scores tests/test_web_routes.py::test_cover_letter_retry_preserves_original_options -q --tb=short` | 9 passed, 2 warnings, 4.62s; exit 0 | `jobot-17-04-tests-4c0uihyh` |
| E4 | `tests -q --tb=short` | **490 passed, 4 warnings, 75.88s; exit 0** | Historical result; superseded by the latest 673-pass result above. |
| E5 | `tests/test_auth_security.py::test_mid_preset_flush_failure_preserves_both_owners tests/test_auth_security.py::test_settings_cv_and_rescore_use_owner_stage_clients tests/test_profile_and_linkedin.py::test_profile_partial_embedding_failure_is_truthful tests/test_profile_and_linkedin.py::test_linkedin_vector_failure_preserves_profile -q --tb=short` | 6 passed, 2 warnings, 2.03s; exit 0 | `jobot-17-04-tests-oaoa8enf` |

Twenty targeted case executions overlap E4; do not add them to claim 510 distinct tests. Only one full suite was run. Named checks were each under ten seconds of pytest time; the explicit full-regression criterion necessarily required the longer E4 run. Warnings are the existing Starlette/AnyIO alias, Chroma asyncio introspection and two per-request-cookie deprecations. No skip/xfail or collection failure was reported.

### Review Closure

The final REVIEW records clean status and zero remaining findings. Its independent 5+25 targeted passes and prior 42+272 passes remain attributed reviewer evidence, not this verifier's executions. E3/E4 independently exercise the fixes in the current code:

| Finding | Current Evidence | Assessment |
| --- | --- | --- |
| CR-01 atomic terminal provider failure | `mark_failed(..., terminal=True)` commits diagnostic/retry/status once; a real second Session cannot claim an intermediate pending row. Ordinary error lifecycle and explicit retry still pass. | CLOSED |
| CR-02 non-secret defaults | Shared default-provider/endpoint/model selection; credential provenance remains separate. Absent-owner OpenAI/custom settings agree with rendered assignments and factory; orphan/global/environment keys are rejected. | CLOSED |
| CR-03 rescore feedback | Both factory/runtime errors reach bounded escaped fragments; HTMX scope includes the exact settings endpoint/feedback target; failing job's prior score/summary/evidence remain intact. | CLOSED |
| CR-04 retry options | Stable cover-letter options form, escaped `hx-include`; three nondefault tone cases and literal instructions survive manual switch/retry. Browser request equality supplements the unit test's reconstructed POST. | CLOSED |

## Browser Evidence and Limits

This verifier did not start or rerun a browser/server. Existing browser artifacts are prior automated evidence; the current human visual/keyboard acceptance is recorded in UAT. This report does not claim a fresh screenshot inspection.

Artifact directory: `C:/Users/melta/AppData/Local/Temp/jobot-17-04-browser-zj7gay5l/`. The preserved `evidence.json` contains exactly **12 interaction groups**, `page_errors: []`, document widths 375 and 1440, and provider section scroll/client widths 293/293 and 1166/1166. PNGs are five pairs: `settings`, `routing`, `failure`, `rescore-failure`, `queue`, each at **375x812 and 1440x900**.

The groups cover Settings navigation/eight forms/blank passwords/no automatic health, visible rejected 422 preset, exact presets and preserved unsaved key input, independent saved routing round-trip, zero/one/many suggestions/loading/status isolation, all eight four-field provider test POSTs, authentication/local-model status, viewport/focus checks, safe Settings rescore failure/switch/separate retry, Inspector failure/retry option equality/escaping, Queue switch/separate retry, and visible profile-bio failure.

The preview harness sets its own disposable paths/socket guard before imports and mocks adapters. Its rescore method is also mocked; the preserved score-90 browser assertion proves UI behavior, not actual evaluator non-mutation. E2/E3/E4 supply the complementary production-path preservation evidence. Queue screenshots are **post-retry pending** views, not screenshots proving a visible failed row; the preceding harness interactions and route tests supply that evidence.

The UI review retains a P2 advisory: the mobile rescore failure diagnostic and recovery controls are cramped and harder to scan. UAT accepted the tested mobile flow, but this advisory is not represented as fixed. Evidence does not establish exhaustive assistive-technology, contrast, focus-order, or multi-device accessibility.

The browser run predates the final CR-02 provider-default follow-up. It supports the unchanged UI/HTMX/recovery implementation and tested default preview scenario; it does not prove fresh browser interaction with every final installation-default configuration. Current final provider/model/rendered parity is established by E3/E4. Zero page errors means JavaScript page-error events, not zero network/console/accessibility issues of every kind.

## Requirements Coverage

| Requirement | Plans / Supporting Truths | Assessment and Limits |
| --- | --- | --- |
| REQ-HYB-01 | 01/03/05; T04/T08/T09/T10/T11/T27 | SATISFIED for independently saved generation-stage routing; E1 and owner call-site traces. |
| REQ-HYB-02 | 01/02/05; T04/T05/T06 | SATISFIED for eight owner vault slots, encryption/blank retention/matching-owner migration and no borrowed credentials; E4/E5. |
| REQ-HYB-03 | 01/05; T01/T02/T03/T26 | SATISFIED for direct adapter protocols using existing dependencies and mocked transports. Live vendor acceptance is not certified. |
| REQ-HYB-04 | 01/03/05; T12/T17/T28 | SATISFIED for application Ollama/nomic pinning, independent generation/vector resolution and non-destructive dimension rejection. Zero cloud embedding calls in covered paths, not a guarantee of geographic locality for a misconfigured operator endpoint. |
| REQ-HYB-05 | 01/03/04/05; T13/T18/T29 | SATISFIED for explicit safe errors, preserved failing-operation records and manual-only provider recovery. Earlier successful operations remain committed under existing policy. |
| REQ-HYB-06 | 02/04/05; T07/T08/T14..T25 | SATISFIED for implemented forms, status targets, assignment controls, exact presets, automated UI behavior, and recorded UAT acceptance. |
| REQ-ACC-01 | Applicable authenticated boundaries | SATISFIED for touched routes; auth dependencies and unauthenticated/foreign-owner tests. Not a fresh all-project authentication audit. |
| REQ-ACC-03 | Owner configuration/jobs/tasks/profile/material paths | SATISFIED for changed Phase 17 SQL/credential call boundaries. **Not** certification of pre-existing global vector IDs or account partitioning. |
| REQ-ACC-04 | 02; owner key writes/migration | SATISFIED for provider vault reuse of authenticated owner encryption. Existing profile encryption/order architecture is not newly certified. |
| REQ-ACC-07 | 02/04/05; T06/T19/T20 | SATISFIED for secret non-reflection across touched Settings/probe/error surfaces; hostile response/header/ciphertext tests E4. |
| REQ-ACC-08 | Applicable non-regression | Existing owner calibration/remote preferences and unrelated Settings sections preserved by source and regression tests; not a new concurrency/global-settings isolation redesign. |
| REQ-QUAL-01 | All plans; T31 | SATISFIED BY UAT: incremental meaningful documentation was accepted; uneven module ratios are disclosed below. |
| REQ-QUAL-02 | Applicable changed source | SATISFIED for useful boundary documentation in the reviewed slice; no cosmetic churn performed by this verifier, no comment-padding recommendation. |
| REQ-UI-01 | 04 | SATISFIED for the existing FastAPI/Jinja/HTMX/Tailwind integration and recorded UAT; exhaustive accessibility is not claimed. |

All HYB IDs in the roadmap are claimed by the five plans. REQUIREMENTS has no additional Phase-17 traceability allocation left orphaned; applicable ACC/QUAL and UI requirements are explicitly included above. ACC-02/05/06's older password/rotation/onboarding implementations are not claimed as new Phase 17 deliverables. ROADMAP analysis has only Phase 17 in active v7.0 and `next_phase: null`; no finding is silently deferred to a nonexistent later phase.

### Meaningful Comment Coverage

Assessed current source and the actual dirty added-line slice with a read-only Node lexical counter plus `git diff --no-ext-diff --unified=0`. The conservative proxy counts standalone docstrings and full-line comments over nonblank lines, excluding inline comments. It is not a Python AST/semantic quality score and includes some existing section labels; numeric counts are not a claim that every counted line is meaningful. Dirty additions include pre-existing shared edits and are **not** Phase-17-exclusive provenance.

| Module / Slice | Current Module Proxy | Dirty Added-Line Proxy | Assessment |
| --- | --- | --- | --- |
| client | 137/598 (22.9%) | 126/451 (27.9%) | Substantial useful protocol, credential/default and local-vector invariants. |
| database | 63/313 (20.1%) | 54/118 (45.8%) | Useful encryption, transaction ownership and migration constraints; no strict per-function quota inferred. |
| settings API | 143/760 (18.8%) | 130/452 (28.8%) | Changed vault/probe/save boundaries well explained; module proxy slightly below approximate target. |
| worker / task queue | 17.8% / 9.1% | 26.3% / 21.9% | Terminal-failure change has an intent docstring and behavioral proof; legacy module totals should not force unrelated padding. |
| evaluator / embeddings / feedback | 18.8% / 20.5% / 18.9% | 69.5% / 33.8% / 38.1% | Useful local transport, no-fallback and validate-before-write explanations. |
| profile API / LinkedIn analyzer / profile extractor | 4.2% / 7.2% / 7.1% | 0/16, 0/15, 0/13 | Small changed routing/error slices have little new explanatory documentation; existing module undercoverage cannot be called fully compliant. |
| web routes | 47/1158 (4.1%) | 6/123 (4.9%) | Narrow failure/retry/provider wiring added to a large existing module; overall target plainly not established. |
| All 18 measured source modules | 941/6554 (14.4%) | 637/1982 (32.1%) | Neither aggregate certifies per-module meaningful coverage or isolated phase attribution. |

The module ratios are uneven, and the dirty shared tree does not provide an isolated phase-only baseline. UAT test 2 records human acceptance of incremental meaningful documentation. This is not a claim that every changed module meets a numeric ratio; no unrelated padding or broad rewrite is implied.

### Test Quality Audit

| Existing Test Surface | Linked Requirements | Active / Disabled | Strongest Proof | Assessment |
| --- | --- | --- | --- | --- |
| ai_client | HYB-01/03/05, ACC | Active; no skip/xfail markers found | Literal expected endpoints/headers/system fields/JSON flags, exact one-call assertions, typed safe error values | Strong protocol/value proof, not live API certification |
| auth_security / db / config | HYB-02/06, ACC | Active; no disabled required tests found | Two authenticated accounts, ciphertext equality/non-reflection, real DB flush/commit rollback and exact tuples | Strong behavioral persistence proof |
| e2e_workflow | HYB-01/04/05 | Active | Actual saved settings, real temporary DB/Chroma snapshots including values, real adapters with mocked HTTP boundary | Strong integration proof under declared offline conditions |
| web_routes / task_queue | HYB-05/06 | Active | Real second-session interleaving, escaped responses, prior record values, form inclusion and scoped retries | Strong boundary/state proof; unit retry POST reconstruction alone does not prove HTMX serialization |
| profile / embeddings / feedback / evaluator | HYB-01/04/05 | Active | Owner factory arguments, explicit vector failures, prior profile/job/vector preservation, truthful partial status | Useful isolated behavior; no new cross-store atomicity guarantee |
| phase17_browser harness | HYB-05/06, UI | Existing saved execution; not rerun here | Actual HTMX requests/DOM/payload equality/viewport assertions | Provider/rescore logic mocked; current human flow acceptance is recorded separately in UAT |

Disabled required tests found: **0**. Circular expected-output generators found: **0** in the inspected requirement surfaces. The browser harness writes observed evidence JSON/screenshots, not expected fixtures used as an oracle. Protocol literals and independently specified expected state transitions, not SUT-generated baselines, drive the assertions. Parameterization supplies ordinary real-caller inputs; no coincidental-reliance item is asserted without a specific undeclared production precondition. This is not a mutation-testing or statistical coverage certification.

### Disconfirmation and Anti-Patterns

The initial hypotheses were: owner identity might be lost in a legacy helper; provider errors might commit destructive/synthetic success; and retry might silently change options. Source traces plus E1/E2/E3/E5 falsify those hypotheses for the asserted Phase 17 contracts. The final reviewer conclusions were not accepted solely because their totals were green.

The module-level comment ratio remains uneven despite the accepted incremental documentation assessment. The cover-letter unit test's reconstructed retry POST is insufficient alone; existing browser request-body evidence supplies HTMX serialization evidence. A valid-looking model listing cannot establish provider entitlement, and no subjective output-quality or economic comparison oracle exists.

| Surface | Finding | Severity / Disposition |
| --- | --- | --- |
| Modified production Python scan | No unreferenced TBD/FIXME/XXX, TODO/HACK completion stub, or coming-soon implementation found. Three placeholder matches are two HTML attributes and a prompt forbidding placeholders. | No debt-marker BLOCKER |
| Vector helpers | Empty collections alone return neutral no-data values; populated transport/dimension failures raise and preserve existing data. | Not a synthetic error fallback |
| Profile update | Existing durable save can precede vector failure; response is explicitly partial/unsynchronized. | Documented existing transaction boundary, not a false atomicity claim |
| Browser evidence | Existing captures are partial viewports and provider/rescore behavior is mocked; UAT records human flow acceptance. | P2 mobile rescore-layout advisory; no exhaustive accessibility claim |
| Comment target | Module-level coverage is uneven; UAT accepted incremental meaningful documentation. | Limitation disclosed; no numeric blanket claim |

### Decision Coverage

The read-only `check.decision-coverage-verify` gate returned: **All trackable CONTEXT.md decisions are honored by shipped artifacts.** Count: **11/11**, not_honored: empty. This heuristic is non-blocking and does not replace the explicit source/tests above. D-01 compatibility, D-02 owner provenance, D-03 local vectors, D-04 explicit failure, D-05 encryption/blank keys, D-06 safe reflection, D-07 transient probes, D-08 assignment-only presets, D-09 existing stack, D-10 separate manual actions and D-11 preservation all have direct supporting evidence.

### Probe Execution

No phase-declared `probe-*.sh`, PASS-marker migration probe, or tooling migration applies. The declared executable regression gate was run as E4, and the saved browser driver/evidence was inspected separately. No historical prose verify instruction was substituted for an executed probe, and no server was started for spot-checks.

## Human Verification Required

None pending. All three checks in `17-UAT.md` passed. This records the agreed visual/keyboard flow, documentation assessment, and operator endpoint/model test; it does not certify production entitlement, subjective output quality, or exhaustive accessibility.

## Boundaries and Handoff

No implementation gaps requiring fixes were confirmed. All required human checks are complete, so the overall status is `passed`. The remaining limitations below do not constitute outstanding UAT items or failed must-haves.

Python 3.10 was unavailable and was not executed; tests ran on Python 3.14.7. The operator confirmed endpoint/model testing, but that does not prove production entitlement, billing readiness, future provider compatibility, or subjective generation quality. Economic savings were not measured. The P2 mobile rescore-layout advisory remains. No exhaustive screen-reader, assistive-technology, contrast, or multi-device accessibility audit is claimed. Existing vector account partitioning, cross-store atomicity, and production load guarantees were not redesigned or certified.

Fingerprint fields were copied from the installed `verification.fingerprint` query over the listed root-relative current implementation/evidence paths; the query automatically includes PLAN/SUMMARY artifacts and excludes this report. The external temporary browser files are identified above, not falsely included as repository-relative source. No Git revision provenance is asserted for the dirty tree.

Only this verification report was changed. No implementation/test edits, installs, real credentials, production-data access, Git mutations, commits, STATE/ROADMAP/REQUIREMENTS completion changes or milestone transitions were performed.

---

_Verifier: GitHub Copilot (gsd-verifier)._