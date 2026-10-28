---
phase: 17-multi-provider-and-hybrid-local-cloud-ai-routing
plan: "02"
subsystem: settings
status: complete
tags: [owner-isolation, encrypted-vault, atomic-settings, provider-health]
requires:
  - phase: 17-01
    provides: Eight-provider defaults, adapters, owner-aware factory and safe errors
provides:
  - Encrypted owner provider vault and idempotent legacy credential migration
  - Atomic settings batches and credential-gated local/hybrid/cloud presets
  - Validated owner-only individual and legacy provider probes
affects: [17-03, 17-04, 17-05]
tech-stack:
  added: []
  patterns: [one-transaction settings writes, non-generating probes, secret-free diagnostics]
key-files:
  created: [.planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-02-SUMMARY.md]
  modified: [app/core/config.py, app/db/database.py, app/api/settings.py, tests/test_config.py, tests/test_db.py, tests/test_auth_security.py, .planning/STATE.md]
key-decisions:
  - Preserve the single-setting commit default; expose deferred commits for atomic batches and migration.
  - Never import installation/environment credentials into owner vault or health checks.
  - Validate a complete form before writes; presets change only six task fields.
  - Keep saved tokens bound to owner endpoints and disable redirect following.
  - Keep UI rendering and documentation-suite integration in their assigned later plans.
requirements-covered: [REQ-HYB-02, REQ-HYB-06, REQ-ACC-04, REQ-ACC-07, REQ-QUAL-01]
requirements-completed: []
actuals:
  tokens: null
  tasks: 3
  commits: 0
actuals-basis: No isolated pre-edit diff snapshot was captured; token cost is unmeasured rather than conflating existing shared-worktree changes with this plan.
duration: Not measured; focused command durations recorded below
completed: 2026-10-27
---

# Phase 17 Plan 02: Encrypted Provider Vault and Settings Summary

Owner-encrypted eight-provider credentials, atomic task settings/presets, and validated non-generating provider checks with safe legacy compatibility.

## Completed Tasks

1. Settings accepts all eight provider IDs. Provider vault slots automatically encrypt nonblank values; blank submissions preserve existing ciphertext. set_user_setting retains its default commit behavior and adds commit=False. set_user_settings rolls back writes, autoflushes and encryption/commit failures. Non-secret seeding is idempotent and no longer seeds environment API keys. Owner-only migration preserves explicit records and maps legacy custom credentials only to custom.
2. POST /api/settings/test-provider validates provider, model and endpoint before I/O, tests submitted or matching owner credentials without persisting them, and has a five-second whole-operation deadline. Fixed cloud hosts cannot be overridden; custom/local HTTP remains supported without userinfo/query/fragment or redirect following. Legacy test-ai, model discovery and settings JSON use owner-only credentials/configuration. Optional Ollama tokens stay bound to the saved endpoint. Safe categorized diagnostics, escaped model options, token-echo filtering and unreadable-key handling prevent credential/raw-error reflection. CV upload uses owner scraping generation plus independent local embedding resolution; rescore-all explicitly selects scoring.
3. POST /api/settings/ai accepts legacy forms and optional task/provider fields; /ai/credentials shares that validated atomic save path. Legacy migration participates in the same transaction. Unknown/duplicate fields, invalid providers/models and credential-bearing endpoints reject before writes. Presets update precisely six task fields: local uses owner Ollama model for all stages; hybrid uses Ollama for scraping/scoring and OpenAI gpt-4o-mini for applying; cloud uses OpenAI gpt-4o-mini throughout. Hybrid/cloud require a matching owner OpenAI credential. Failed validation or commit leaves ciphertext, settings and other owners unchanged.

## Verification

Every pytest process used a unique temporary directory for DATABASE_URL, CHROMA_DIR and ENCRYPTION_KEY_FILE before application imports, JOBOT_TESTING=1, ENV=testing and disabled telemetry. The wrapper restored the previous process environment afterward. No test used production SQLite, Chroma or encryption-key storage. The existing .venv/Scripts/python.exe was used without installs or dependency edits.

- Schema RED: anthropic rejected by the original three-provider Literal. After expansion, 15 tests passed before the expected missing batch API failure.
- Vault RED: the batch capability assertion failed. GREEN: 21 config/database tests passed in 1.32s, including encryption, blank preservation, idempotency and injected mid-batch/commit rollback.
- Probe RED: the new route returned 404. GREEN: 37 route/CV tests passed before stage wiring; four future-route authentication cases were temporarily deselected, then included once Task 3 existed.
- CV RED: observed scoring-only resolution instead of scraping plus embeddings. GREEN: 38 route/CV tests passed in 4.70s before Task 3.
- Preset RED: the new preset route returned 404. GREEN: 65 authentication/database tests passed in 7.67s, including all preset tuples and commit rollback.
- Adversarial RED/GREEN checks additionally proved and repaired unsafe legacy URL reflection, unreadable-key exceptions and bearer-token echo through remote model names.
- Transport harness correction: the installed OpenAI SDK uses httpx2, unlike the native adapters' httpx. The first transport regression intercepted only httpx, so one fake-key GET https://api.openai.com/v1/models escaped the mock and returned 401. No generation or real provider credential was used. The repaired test discovers the SDK backend and mocks both transports; all eight providers now assert exactly one model-list GET, correct credential headers, no redirect following and no credential/log/HTML leakage.
- Final combined command: `.venv/Scripts/python.exe -m pytest tests/test_config.py tests/test_db.py tests/test_auth_security.py tests/test_cv_parser.py tests/test_ai_client.py -q -x -o addopts=''`.
- Final result: **232 passed, 4 warnings in 20.52s**. Warnings are existing Starlette/AnyIO, Chroma asyncio introspection and per-request test-cookie deprecations. All three plan target sets and Wave 1 client regressions are included.
- Editor diagnostics: no errors in the six touched Python files.
- AST/token-based comment/docstring coverage: config 10/52 (19.2%), database 63/313 (20.1%), settings API 142/719 (19.7%). Documentation explains security, transaction and compatibility boundaries; existing unrelated code was preserved.
- Stub scan found only an existing HTML input placeholder attribute, not a functional stub or TODO/FIXME.
- Scoped whitespace checks pass for five Python files. The settings file retains pre-existing trailing whitespace in the unrelated scraper settings block (current line 795); it was present in the initial read and intentionally not cleaned up.

## Commits and Preservation

**No git staging, commits, branches, stash, reverts, installs or dependency changes. Commits: 0.** The user's explicit shared-worktree constraints override executor commit/ledger requirements. Existing edits in client, worker, templates, fixtures, parser and every other unrelated file were left intact. Only the six planned Python files, this summary and the existing Phase 17 progress line in STATE were edited. Milestone v7.0 remains unchanged; Phase 17 is incomplete at 2/5 plans.

## Deviations and Limits

- Missing-key and invalid-form failures perform no migration or writes. Successful manual saves migrate submitted legacy owner state inside the same transaction, rather than committing migration first. Presets intentionally perform no migration so they never change credential/endpoint records.
- Unsafe legacy URL redaction, unreadable-key normalization and token-echo filtering are same-scope security repairs, not new architecture or services.
- No separate code refactor was needed after the green checks. No machine RED-evidence classifier verdict or per-task commits are claimed; the actual failing commands and semantic causes are recorded above.
- Token/duration effort totals were not captured reliably. Existing dirty-tree deltas were not reported as isolated plan effort.

## Remaining Work and Risks

Routing saves/presets currently return secret-free feedback plus an ai-settings-updated refresh event; Plan 04 owns actual refreshed routing-control markup and explicit HTMX handling of non-2xx fragments. No template/UI work was performed here. User manual, contributor guide and README synchronization remains the explicit Plan 05 documentation task, not a claim that unwired UI is shipped.

Plans 03/04/05, full-suite regression, browser evidence and independent review were not executed. Other application stage/vector/error consumers remain assigned to those plans. Live credential acceptance, paid model entitlement, generation quality and economic savings are unverified. Local/private HTTP endpoints remain supported intentionally; URL validation is not a network allowlist. No paid generation or automatic retry/failover was performed.

## Self-Check: PASSED

All six planned Python files and both completed-plan summaries exist. STATE retains milestone v7.0 and an unchecked Phase 17 at 2/5 plans. No 17-03, 17-04 or 17-05 summary exists. The summary records the exact final 232-pass result, zero commits and the fake-key transport-test incident. No commit-existence check applies because git mutations were forbidden.