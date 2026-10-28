---
phase: 18-live-model-discovery-for-cloud-providers-and-ollama
plan: "02"
subsystem: ai-pipeline
status: complete
tags: [model-catalog, ttl-cache, refresh-cooldown, owner-isolation]
requires:
  - phase: 18-01
    provides: ModelListing and _catalog_identity
provides:
  - "`ModelCatalog` (TTL 300 s, 256 entries, single-flight, 5 s refresh cooldown) with `get_or_fetch`, `peek`, `invalidate`"
  - "`validate_configured_model` returning listed / not_listed / unchecked"
  - "`get_model_catalog` singleton plus `reset_model_catalog` for tests"
affects: [18-03]
tech-stack:
  added: []
  patterns: [injectable monotonic clock, salted key digest, no-I/O cache layer]
key-files:
  created: [app/ai/model_catalog.py, tests/test_model_catalog.py, .planning/phases/18-live-model-discovery-for-cloud-providers-and-ollama/18-02-SUMMARY.md]
  modified: []
key-decisions:
  - Cooldown starts on any refresh attempt, including a failed one, and is keyed per owner and provider.
  - "`RefreshCooldown` is a plain exception (not `AIProviderError`) so the route can render a friendly 429."
  - Ollama membership is checked against chat models only; embedding names live in `ModelListing.embedding_models`.
requirements-covered: [REQ-HYB-07, REQ-HYB-08]
requirements-completed: []
actuals:
  tokens: null
  tasks: 3
  commits: 0
actuals-basis: Token cost not measured.
duration: Not measured
completed: 2026-10-28
---

# Phase 18 Plan 02: Model Catalog Cache and Validator Summary

A network-free, owner-scoped cache with TTL, cooldown and single-flight fetch, plus a normalizing configured-model validator.

## Completed Tasks

1. **Tracer.** `get_or_fetch` cache hit path and `validate_configured_model` (Gemini `models/` prefix and Ollama `:latest` normalized for comparison only; truncated/unsupported/empty/failed listings are `unchecked`).
2. **TTL, cap, failures.** 300 s TTL (299 s hit, 300 s refetch), oldest-first eviction at 256, failures propagate uncached, per-key lock gives single-flight, cancellation releases the lock, `peek` is cache-only, `invalidate(user_id, provider=None)`.
3. **Cooldown and isolation.** `refresh=True` bypasses a fresh entry; a second refresh inside 5 s raises `RefreshCooldown(seconds_remaining)` without calling the provider; owner, key and endpoint changes are distinct keys; a sentinel key never appears in repr, str or stored keys.

## Verification

Run via `.venv\Scripts\python.exe tests/run_phase17.py ... -q`.

- `tests/test_model_catalog.py tests/test_ai_client.py`: 270 passed.
- Full suite: **644 passed** (624 after Plan 01 plus 20 new), 4 warnings (Starlette/Chroma deprecations).

## Deviations from Plan

- The plan said the module imports `AIProviderError` and `_catalog_identity`; it imports only `ModelListing`, since the catalog receives the identity tuple from callers and never raises provider errors itself.
- Tests were written together with the code and passed on first run; no recorded RED failure, so strict TDD compliance is not claimed.
- Added `reset_model_catalog()` (not named in the plan) so Plan 03 tests can isolate cache state.

## Preservation

No git operations, installs or dependency edits. Commits: 0. No existing file modified.

## Remaining Work and Risks

- The catalog is not wired into any route yet (Plan 03).
- The cache is in-process: it is not shared across workers and is lost on restart (accepted by D-11).
- Comment/docstring coverage in the new module is not tool-measured; module and class docstrings state the invariants, with sparse inline rationale.

## Self-Check: PASSED

`app/ai/model_catalog.py` and `tests/test_model_catalog.py` exist; the recorded 644-pass result matches the last full run. No commit hashes apply.
