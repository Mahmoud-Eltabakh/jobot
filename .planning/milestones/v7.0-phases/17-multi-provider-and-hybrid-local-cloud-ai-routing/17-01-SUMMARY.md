---
phase: 17-multi-provider-and-hybrid-local-cloud-ai-routing
plan: "01"
subsystem: ai
status: complete
tags: [httpx, openai, ollama, owner-isolation, routing]
requires:
  - phase: 15
    provides: Encrypted account-owned settings and authenticated sessions
provides:
  - Native Anthropic and Gemini REST generation adapters
  - Eight-provider defaults and sanitized AIProviderError diagnostics
  - Compatible owner-aware task factory and fixed local embedding resolver
affects: [17-02, 17-03, 17-04, 17-05]
tech-stack:
  added: []
  patterns: [direct REST adapters, owner-only credential provenance, explicit failure without failover]
key-files:
  created: [.planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-01-SUMMARY.md]
  modified: [app/ai/client.py, tests/test_ai_client.py, .planning/STATE.md]
key-decisions:
  - Keep all existing positional factory arguments and make task_type keyword-only.
  - Resolve user_id without a session through a short-lived owner session.
  - Never inherit installation or foreign credentials for an authenticated owner.
  - Treat model-list success as reachability, not verified generation entitlement.
requirements-covered: [REQ-HYB-01, REQ-HYB-02, REQ-HYB-03, REQ-HYB-04, REQ-HYB-05, REQ-QUAL-01]
requirements-completed: []
actuals:
  tokens: 14992
  tasks: 3
  commits: 0
actuals-basis: Source/test git diff only, 59967 characters divided by four and rounded up; excludes closeout metadata.
duration: Not measured; start timestamp was not captured
completed: 2026-10-27
---

# Phase 17 Plan 01: Multi-Provider Client Foundation Summary

Direct Anthropic/Gemini adapters, bounded safe provider failures, and owner-isolated task routing with local nomic-embed-text resolution.

## Completed Tasks

1. Native REST adapters: correct authentication headers and system/user payloads, JSON/text modes, hidden-thought exclusion, blocked/truncated/empty/malformed response rejection, non-generating health, and explicit unsupported cloud embeddings.
2. Provider defaults: all eight IDs; OpenAI/Groq/DeepSeek/OpenRouter endpoints; validated custom endpoints; bounded SDK requests with retries/redirects disabled; sanitized OpenAI/Ollama generation, embedding and health failures.
3. Factory: get_ai_client(session, user_id, *, task_type='scoring'), explicit unknown-ID rejection, owner task/legacy/default precedence, matching owner legacy-key compatibility, read-only short-lived owner sessions, and fixed local embedding resolution.

## Verification

Every pytest process used a newly generated temporary directory for DATABASE_URL, CHROMA_DIR and ENCRYPTION_KEY_FILE before app imports, with JOBOT_TESTING=1, ENV=testing and telemetry disabled. Previous process environment was restored afterward. No production database, vectors or key file was used. Cloud/Ollama operations used MockTransport or AsyncMock; no paid generation was performed.

- Interpreter: existing .venv/Scripts/python.exe. Installed httpx 0.28.1, openai 3.8.0, ollama 0.6.2, pytest 9.1.1 and pytest-asyncio 1.4.0; no installs or dependency edits.
- Task 1 RED: 2 passed, then missing AnthropicClient; GREEN: all 29 client tests passed.
- Task 2 RED: 29 passed, then missing provider constructor keyword. First implementation check exposed a test fixture omitting the required custom model; repaired locally. GREEN: all 89 client tests passed.
- Task 3 RED: 89 passed, then missing task_type keyword. GREEN: 124 passed, 4 warnings in 10.33s across client/authentication targets.
- Deadline regression RED: 118 passed, then absent native whole-request deadline. Repaired native deadline and malformed SDK model-list handling. GREEN: 133 passed, 4 warnings in 11.15s.
- Final command: `.venv/Scripts/python.exe -m pytest tests/test_ai_client.py tests/test_auth_security.py -q -x -o addopts=''`.
- Final result after documentation additions: **133 passed, 4 warnings in 9.41s**. Warnings are Starlette/AnyIO, Chroma asyncio introspection and per-request test cookies deprecations.
- Editor diagnostics: no errors in either touched Python file. Scoped git diff --check passed.
- AST/token-based documentation count: 130 comment/docstring lines / 583 nonblank module lines = 22.3%; documentation explains protocol, credential, timeout and compatibility invariants.
- Stub scan found no TODO/FIXME/placeholder markers. Existing MockAIClient remains an unchanged test utility, not a production fallback.

## Commits and Preservation

**No staging, commits, branches, stash, reverts, installs or dependency changes.** User authorization explicitly overrides normal executor commit requirements. Commits: 0; no commit ledger or invented hashes. Existing dirty files, including fixtures, database/settings changes and milestone v7.0, were preserved. Only the two planned Python files, this summary and a minimal STATE update were edited.

## Decisions and Scope Limits

Provider defaults are editable hints, not verified live model availability. Custom URLs reject embedded credentials, queries and fragments; local/private HTTP remains supported, not a new network allowlist. Error strings use allowlisted messages and suppress raw exception display; callers must retain this safe contract rather than log underlying context.

No alternate provider/model, synthetic text, or zero-vector recovery is introduced. Application-wide stage/embedding wiring and fallback removal belong to 17-03; encrypted vault migration/settings APIs to 17-02; UI to 17-04; full regression and operator documentation to 17-05. Those plans were not executed. README/manual/contributor synchronization is deferred to the explicit 17-05 documentation task rather than advertising unwired features now.

## Remaining Risks

- Live credential acceptance, paid model entitlement, output quality and actual savings were not tested or claimed.
- Full-suite and browser validation were not run; they are later-plan gates, not omitted 17-01 commands.
- Existing consumers may still hide provider errors or call cloud embeddings until their planned 17-03 migration.
- Existing settings routes are not yet uniformly owner-hardened; this plan secures client resolution only.
- Requirement IDs above are covered only at this foundation boundary, not marked complete phase-wide. Phase 17 remains in progress with 1/5 plans complete.

## Self-Check: PASSED

On-disk source/test/summary artifacts exist; milestone v7.0 is preserved; Phase 17 remains unchecked at 1/5 plans; no 17-02 through 17-05 summary was created. Summary records the exact final 133-pass result and zero commits. Scoped whitespace and Python editor diagnostic checks passed. No commit-existence check applies because commits were prohibited.