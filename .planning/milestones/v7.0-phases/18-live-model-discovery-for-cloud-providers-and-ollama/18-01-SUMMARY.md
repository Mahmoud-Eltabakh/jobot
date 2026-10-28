---
phase: 18-live-model-discovery-for-cloud-providers-and-ollama
plan: "01"
subsystem: ai-pipeline
status: complete
tags: [model-discovery, list-models, bounded-http, owner-scoped-route]
requires:
  - phase: 17-04
    provides: Owner-scoped `_provider_client`, safe `AIProviderError` categories, provider cards and datalists
provides:
  - "`ModelListing`, `BaseAIClient.list_models()` and per-adapter listings (Gemini, Anthropic, OpenAI family, OpenRouter, custom, Ollama)"
  - "Shared bounded HTTP helpers, `MODEL_ID_PATTERN` (single definition) and `_catalog_identity`"
  - "`POST /api/settings/provider-models` returning an escaped datalist fragment"
affects: [18-02, 18-03, 18-04]
tech-stack:
  added: []
  patterns: [tracer-first slice, injectable discovery transport, truncate-not-fail caps]
key-files:
  created: [.planning/phases/18-live-model-discovery-for-cloud-providers-and-ollama/18-01-SUMMARY.md]
  modified: [app/ai/client.py, app/api/settings.py, tests/test_ai_client.py, tests/test_web_routes.py]
key-decisions:
  - Discovery uses a direct bounded httpx stream (not the OpenAI SDK) so redirects stay off and OpenRouter `architecture` survives.
  - Caps (10 pages, 500 models) return `truncated=True`; only oversize body, bad shape or non-object JSON is `invalid_response`.
  - IDs that echo the credential are dropped in addition to pattern filtering.
requirements-covered: [REQ-HYB-07, REQ-QUAL-01]
requirements-completed: []
actuals:
  tokens: null
  tasks: 3
  commits: 0
actuals-basis: Token cost not measured; no isolated baseline snapshot of the shared dirty tree.
duration: Not measured
completed: 2026-10-28
---

# Phase 18 Plan 01: Model Listing Contract and Gemini Slice Summary

Every adapter now exposes a bounded, filtered `list_models()`; the Gemini slice runs from adapter to an escaped datalist through an owner-scoped POST route.

## Completed Tasks

1. **Tracer (Gemini end to end).** `ModelListing(provider, models, truncated, supported, embedding_models)`, `_catalog_identity`, `_discovery_http_client`, `_bounded_json`, `_collect_pages`, `_collect_model_ids` and `GeminiClient.list_models` (pageSize=100, `nextPageToken`, `generateContent` filter, embedding/tts/image/aqa/veo exclusion, `models/` stripped). `POST /api/settings/provider-models` builds its client only via `_provider_client`; `MODEL_PATTERN` is now an alias of `MODEL_ID_PATTERN` in `app/ai/client.py`.
2. **Expansion.** Anthropic (`after_id`/`has_more`), OpenAI/Groq/DeepSeek/custom (`<base>/models`, family exclusions), OpenRouter (text output modality), Ollama (`/api/tags`, chat vs embedding split by `details.family`/name, typed errors instead of `[]`). `fetch_available_models` and every `check_health_details` are untouched.
3. **Hostile-input bounds.** Failure-class mapping (401/403/429/5xx/302/non-JSON/array/oversize/timeout/connect), page and model caps, identity stability, adversarial key-echo across all eight providers (exception, repr, `__cause__`, caplog), fixed-cloud endpoint override 422, LAN custom endpoint allowed.

## Verification

All commands ran through `.venv\Scripts\python.exe tests/run_phase17.py ... -q` (disposable DB, sockets blocked; transports mocked).

- Task 1 target (`-k "gemini and (list or discovery or provider_models)"`): 2 passed.
- Task 2 target (`tests/test_ai_client.py`): 200 passed.
- Task 3 target (`tests/test_ai_client.py tests/test_web_routes.py`): 292 passed.
- Full suite: **624 passed** (560 pre-existing + 64 new), 4 warnings (Starlette/Chroma deprecations).

## Documentation Coverage

New helpers carry docstrings stating the invariants (bounds, header-only credentials, no redirect, truncate-not-fail) with short rationale comments; coverage was not measured with a tool and is estimated near the lower end of the 20-30% target for the new block. Full REQ-QUAL-01 acceptance is not claimed.

## Deviations from Plan

- **Tests were written alongside, not strictly RED-first.** Production slices and tests for each task landed together and passed on first run; no recorded RED failure exists, so strict TDD gate compliance is not claimed.
- **Tracer `-k` filter** selects only the two Gemini-named tests; `test_provider_models_without_key_is_rejected_without_request` is covered by the Task 3 run instead.
- **Ollama key source.** `OllamaAIClient` stores its bearer in the `_headers` dict and has no `api_key`; `_client_secret` reads that dict while cloud adapters use `api_key`, as the plan required.
- **Plan-02-era route text.** The route renders "N models listed" for success; non-supported adapters render "Model discovery not available for this provider".

## Preservation

No git staging, commits, branches, stash, installs or dependency edits. Commits: 0. `data/` and any running server were not touched.

## Remaining Work and Risks

- No cache or cooldown yet (Plan 02); every route call hits the provider.
- No UI wiring for `refresh`, task-model datalists or warnings (Plans 03/04).
- No live provider validation was performed; field names come from documented shapes and mock fixtures only.

## Self-Check: PASSED

Modified files exist; the on-disk full-suite result (624 passed) matches this summary. No commit hashes apply.
