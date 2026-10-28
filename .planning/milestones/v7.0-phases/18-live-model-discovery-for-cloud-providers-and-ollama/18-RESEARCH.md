---
phase: 18
milestone: v7.0
status: researched
created: 2026-10-28
discovery_level: 1
independent_researcher: unavailable
---

# Phase 18 Research

## Scope and Evidence

Source-grounded planner research from current code (not a separately dispatched researcher). Provider API shapes are taken from the documented REST listing endpoints already referenced by Phase 17 health checks; implementers must confirm field names against recorded mock fixtures, not live calls. No new packages: httpx, openai, ollama, pytest, pytest-asyncio are already installed.

## Verified Local Findings

| ID | Evidence | Planning consequence |
|----|----------|----------------------|
| R-01 | `_NativeCloudClient.check_health_details` GETs `/v1/models` or `/v1beta/models` and only checks the list key is a list | Provider test passes for a model that 404s on generation (Gemini incident). Reuse the listing, add model-in-list validation. |
| R-02 | Gemini listing returns `models[].name` as `models/<id>`; `GeminiClient.generate` already strips `models/` | Normalize prefix for comparison and suggestions. Listing is paginated via `nextPageToken`; first page only today. |
| R-03 | Listing includes embedding/TTS/image models | Filter on `supportedGenerationMethods` containing `generateContent` plus ID-family exclusion. |
| R-04 | `OpenAICompatibleClient.check_health_details` uses SDK `models.list()` (auto-pagination, typed objects drop extras such as OpenRouter `architecture`) | Discovery uses direct bounded httpx GET `<base>/models` with Bearer header and `follow_redirects=False`; SDK health stays untouched. |
| R-05 | `OllamaAIClient.fetch_available_models` swallows every error into `[]`; `check_health_details` returns `available_models` and `model_present` | Add a typed listing that distinguishes "unreachable" from "no models"; keep old classmethod and tests. |
| R-06 | `_health_fragment` already emits `<datalist id="provider-models-<provider>" hx-swap-oob>` with up to 100 escaped options for healthy results | Extend rather than replace; datalist exists per provider card, task model inputs have no `list`. |
| R-07 | `_provider_client` enforces owner key, fixed cloud endpoints, saved-token-to-endpoint binding, `MODEL_PATTERN` | Single entry point for discovery clients; no new credential path. |
| R-08 | `AIProviderError` messages are allowlisted categories | Discovery errors reuse them; never include bodies/URLs. |
| R-09 | `/test-embeddings` already requires `nomic-embed-text` by `model.split(":")[0]` match on the owner's endpoint (`get_embedding_client`) and returns "Connected"/"Unavailable" with no hint | Add actionable missing-model list and pull hint without changing the existing text contract. |
| R-10 | `update_ai_settings` validates then commits and returns `_routing_feedback`/provider-save fragment | Save warnings append non-blocking text to those fragments using cache-only lookups. |
| R-11 | `tests/run_phase17.py` blocks all socket connects; existing tests monkeypatch `OllamaAIClient.fetch_available_models` and `check_health_details` in an autouse fixture | New tests need explicit transport injection; autouse mocks must keep working. |
| R-12 | `MODEL_PATTERN` lives in `app/api/settings.py` | Client-side filtering needs the same pattern; move the definition to `app/ai/client.py` and import it in settings to avoid drift. |

## Architecture Notes

- **Listing helper:** one `_discovery_http_client()` factory in `client.py` (timeout 5 s connect / 8 s total, `follow_redirects=False`) that tests monkeypatch to inject `httpx.MockTransport`. A `_bounded_json(response)` reads at most 1 MiB.
- **Result type:** frozen dataclass `ModelListing(provider, models: tuple[str, ...], truncated: bool)`; `BaseAIClient.list_models()` defaults to an empty "unsupported" listing so `MockAIClient` and legacy subclasses keep working.
- **Pagination caps:** 10 pages, 500 models, duplicate IDs collapsed, order preserved (Gemini/OpenAI ordering is not alphabetical; sort case-insensitively for the UI).
- **Cache:** `app/ai/model_catalog.py` with `ModelCatalog` (TTL 300 s, 256 entries, per-key refresh cooldown 5 s, `time.monotonic` injectable for tests). Key = `(user_id, provider, endpoint, sha256(salt + key)[:16])` where salt is per-process random.
- **Validation:** `validate_configured_model(provider, model, listing) -> "listed" | "not_listed" | "unchecked"`; `unchecked` when the list is unsupported/unavailable/truncated-and-absent.
- **Ollama requirements:** `required_ollama_models(session, user_id)` = provider default model + `task_<stage>_model` where provider is ollama, plus `nomic-embed-text`; `missing = [m for m in required if not present(m, listing)]`.
- **Routes:** new `POST /api/settings/provider-models` (form: provider, api_key, base_url, model, refresh) so keys never appear in URLs. `/test-provider` and `/test-embeddings` gain validation output.
- **UI:** reuse `provider-models-<provider>` datalists; add `list=` to task model inputs bound to the selected task provider; `Refresh models` button per provider card; `model-warning-*` live regions (text + icon, not color only).

## Open Questions (resolved by CONTEXT)

- Block save on unlisted model? No (D-03): lists can be incomplete or stale.
- Network on save? No (D-12): cache-only.
- SSRF denylist? No (D-08): consistent with Phase 17 LAN/self-hosted support.

## Validation Architecture

All new behavior is covered by mocked-transport unit tests (`tests/test_ai_client.py`, new `tests/test_model_catalog.py`) and route/HTML tests (`tests/test_web_routes.py`). Runner: `.venv\Scripts\python.exe tests/run_phase17.py <tests> -q`. No live provider, no real keys, no Ollama host in CI.
