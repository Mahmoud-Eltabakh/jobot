---
phase: 18-live-model-discovery-for-cloud-providers-and-ollama
plan: "03"
subsystem: ai-pipeline
status: complete
tags: [settings-api, model-validation, ollama-requirements, save-warnings]
requires:
  - phase: 18-01
    provides: list_models contract, _catalog_identity, provider-models route
  - phase: 18-02
    provides: ModelCatalog, validate_configured_model, RefreshCooldown
provides:
  - "Cached `POST /api/settings/provider-models` with `refresh` and a 429 cooldown fragment"
  - "Provider test reports the configured model as listed / not in provider list / unchecked via `model-warning-<provider>`"
  - "Ollama chat-model and `nomic-embed-text` presence check with display-only `ollama pull` hints (`ollama-requirements-hint`, `embedding-hint`)"
  - "Cache-only, non-blocking `model-save-warning` on save plus cache invalidation on key/endpoint changes"
affects: [18-04, 18-05]
tech-stack:
  added: []
  patterns: [out-of-band slot elements, cache-only save path, one datalist per response]
key-files:
  created: [.planning/phases/18-live-model-discovery-for-cloud-providers-and-ollama/18-03-SUMMARY.md]
  modified: [app/api/settings.py, app/ai/model_catalog.py, tests/test_web_routes.py, tests/test_auth_security.py]
key-decisions:
  - Provider test performs one extra cached listing GET after a healthy probe; a listing failure leaves the test result intact and reports the model unchecked.
  - Ollama presence unions health `available_models` with the live listing, so existing health mocks keep working and no extra request is needed.
  - The embedding hint is shown only for a reachable host that lacks the model; an unreachable host gets no invented hint.
  - Save warnings use `_provider_client` with the owner's stored key/endpoint and the same `_catalog_identity` as discovery, so `peek` hits discover-time entries.
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

# Phase 18 Plan 03: Settings API Wiring Summary

Discovery is cached with a refresh cooldown, the provider test flags a model missing from the live list, Ollama hosts are checked for required models with pull hints, and saves warn without blocking or rewriting.

## Completed Tasks

1. **Tracer.** `_discover`, `_model_state_fragment`; `list_provider_models` gained `refresh` (429 "Wait a few seconds before refreshing again") and uses the catalog; `test_provider_connection` appends one `model-warning-<provider>` element and merges the live listing into a single OOB datalist via new `_health_fragment` parameters. The Gemini 404 scenario now renders "Model not in provider list".
2. **Ollama.** `required_ollama_models` (tested/default model plus task models routed to Ollama), `ollama_requirements` (tag-insensitive), `_pull_hint` (pattern-validated, escaped, inert `<code>` text), provider-test hint block, and `/test-embeddings` keeps its `Connected`/`Unavailable` span while adding an OOB `embedding-hint` for reachable hosts missing `nomic-embed-text`. The host comes from the owner's saved endpoint (asserted in tests).
3. **Save warnings.** `_save_warning_html` (peek only, exceptions swallowed), `_invalidate_changed_providers`, `_routing_feedback(warning_html=...)`. Each success shape (provider-save span, `ai-routing-controls` block, `#ai-routing-feedback` span) carries exactly one `model-save-warning`; no network on save; submitted values persist exactly.

## Verification

All runs used `.venv\Scripts\python.exe tests/run_phase17.py ... -q` with mocked transports and blocked sockets.

- Plan 03 target (`test_web_routes`, `test_auth_security`, `test_ai_client`, `test_model_catalog`): 406 passed.
- Full suite: **655 passed** (644 after Plan 02 plus 11 new), 4 warnings (Starlette/Chroma deprecations).
- Editor diagnostics: no errors in `settings.py`, `client.py`, `model_catalog.py`.

## Deviations from Plan

- **Edited an existing Phase 17 test.** `tests/test_auth_security.py::test_provider_probe_transport_headers_get_only_no_redirects` asserted exactly one outbound request and no query string. A healthy test now makes the health GET plus one listing GET (Gemini listing carries `pageSize`). The test now expects 1 request on failure and 2 on success, asserts GET/no key in any URL, and keeps the original assertions on the first (health) request. This file was not in the plan's `files_modified`.
- **`normalize_model_name`** was made public in `model_catalog.py` (renamed from `_normalize`) so settings reuses the same normalization; this touches a Plan 02 file.
- **`_discover` signature** is `(user_id, client, refresh=False)`; the plan's `session` parameter was unused and omitted.
- **Ollama presence** is derived from health `available_models` united with the listing instead of preferring `list_models`; chosen so existing autouse health mocks keep working and no extra request is made.
- **Cross-owner test** is at route level (second registered account), not the plan's named fixture.
- Tests were written together with code and passed on first run; no recorded RED failure, so strict TDD compliance is not claimed.

## Preservation

No git operations, installs or dependency edits. Commits: 0. `data/` and any running server untouched; no live provider or Ollama call.

## Remaining Work and Risks

- The `model-warning-<provider>`, `ollama-requirements-hint`, `embedding-hint` and `model-save-warning` OOB targets do not exist in `templates/components/settings.html` yet (Plan 04). Until then htmx will not display them.
- Each healthy provider test now costs two provider GETs (health plus listing; the second may be cached).
- Task-provider-change saves persist an auto-filled default model, and a cached list that lacks it will warn about a value the owner did not type.
- `_routing_settings` can raise `HTTPException` for an invalid stored provider; the save path guards this, the Ollama hint path does not.
- Comment/docstring coverage was not tool-measured; new helpers carry docstrings and sparse rationale comments, likely near the lower end of the 20-30% target.
- No live validation of real provider payloads; shapes come from documented fields and mocks.

## Self-Check: PASSED

Modified files exist and the on-disk full-suite result (655 passed) matches this summary. No commit hashes apply.
