# Phase 18: Live Model Discovery for Cloud Providers & Ollama - Context

**Gathered:** 2026-10-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Fetch the live model list from each configured provider (Gemini, Anthropic, OpenAI,
Groq, DeepSeek, OpenRouter, custom OpenAI-compatible) and from the owner's Ollama host
(local or remote, e.g. http://192.168.1.15:11434), offer the results as suggestions in
Settings, and warn when a configured model is not in the live list.

Real incidents motivating the phase: Gemini `gemini-2.5-flash` returned 404 on
generation although the provider test passed (the test only proved that the listing
endpoint was reachable); the Ollama host lacked `nomic-embed-text` and the chosen chat model.

Out of scope: remote `ollama pull`, automatic model selection or failover, paid
generation probes, pricing/quotas, new dependencies, a new frontend stack.
</domain>

<decisions>
## Implementation Decisions

### Discovery Semantics
- **D-01:** Discovery is advisory. A model "listed" is not proven usable (entitlement, region, deprecation can still fail); UI wording says "listed", never "verified".
- **D-02:** Never change a saved or submitted model automatically. Discovery, tests and saves never write a model setting the owner did not submit.
- **D-03:** Free text always remains possible. Suggestions use `<datalist>` on the existing model inputs; an unlisted model produces a non-blocking amber warning ("Not in provider list"), never a rejected save.
- **D-04:** Only generation/chat-capable models are suggested. Gemini: `supportedGenerationMethods` contains `generateContent` and the ID is not an embedding/TTS/image-only family. Anthropic: all listed. OpenAI-family: exclude embedding, whisper/audio/tts/realtime, image (dall-e, gpt-image), moderation IDs. OpenRouter: output modalities include `text`. Ollama: exclude embedding families so only chat models are suggested for generation.
- **D-05:** Normalize for comparison only: strip Gemini `models/` prefix and treat an Ollama name without tag as `:latest`. Stored values are the exact strings the owner typed or picked.

### Safety and Ownership
- **D-06:** Credentials travel only in headers (Bearer / `x-api-key` / `x-goog-api-key`); discovery requests are POST forms from the browser so no key reaches a URL, query string, log line or response body. Page tokens (not secrets) may be query parameters.
- **D-07:** Owner-scoped only: the key, endpoint and model come from `_provider_client` (submitted values or that owner's vault). No global/environment key is ever used; a saved key cannot follow an unsaved changed endpoint (existing rule).
- **D-08:** SSRF stance is consistent with Phase 17 `_validated_url`: URL hygiene (http/https, no userinfo/query/fragment), redirects disabled, no private-network denylist because self-hosted and LAN Ollama are first-class. Compensating controls: authenticated owner only, bounded timeouts, 1 MiB response cap, 10 page cap, only model-ID strings extracted and pattern-filtered, remote body/exception text never reflected.
- **D-09:** Errors reuse `AIProviderError` categories; listing failures render the sanitized message and leave the free-text input working.
- **D-10:** Every model ID shown is `MODEL_ID_PATTERN`-filtered (relocated to `app/ai/client.py`; `MODEL_PATTERN` stays as an alias) and HTML-escaped; IDs that fail the pattern are dropped. Caps (<=500 models, <=10 pages) never error: overflow returns a TRUNCATED listing (`truncated=True`). Only an oversized body (>1 MiB), malformed shape or non-object JSON is `invalid_response`.

### Caching and Refresh
- **D-11:** In-process cache keyed by owner + provider + endpoint + salted key fingerprint (never the key), 5-minute TTL, 256-entry cap. Failures are not cached. Manual "Refresh models" bypasses the cache but has a 5-second per-owner/provider cooldown to protect provider quotas.
- **D-12:** Settings GET performs no discovery (existing test `test_provider_settings_are_explicit_and_secret_free` must stay green). Save validation uses the cache only (no network on save) and warns non-blockingly.

### Ollama
- **D-13:** The Ollama check uses the owner's configured endpoint and verifies both every Ollama-assigned chat model (provider default model plus any `task_<stage>_model` whose provider is ollama) and `nomic-embed-text` (tag-insensitive). Missing models yield a display-only `ollama pull <model>` hint built from a pattern-validated name; nothing is executed or pulled remotely.

### Compatibility
- **D-14:** Existing routes (`/test-provider`, `/test-embeddings`, `/ollama/models`), element IDs (`provider-status-*`, `provider-models-*`, `embedding-status`) and their current response text ("Connected", "Unavailable", "Reachable; credentials unverified") stay valid; new behavior is additive.
- **D-15:** No new dependencies; tests use `httpx.MockTransport`/`AsyncMock`/`monkeypatch`, never the network (the `run_phase17.py` runner blocks sockets).

### Agent's Discretion
- Module layout (`app/ai/model_catalog.py` for cache/validation), dataclass names, exact cooldown and TTL constants within D-11 bounds.
- Wording of warnings within D-01/D-03.
- Ollama capability detection by `details.family` heuristic instead of an N+1 `/api/show` per model.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/ai/client.py`: `_NativeCloudClient` (Anthropic/Gemini; header auth, 5 s connect, `follow_redirects=False`), `OpenAICompatibleClient` (SDK `models.list` for health), `OllamaAIClient.fetch_available_models` (`/api/tags`, swallows errors to `[]`), `AIProviderError`, `_provider_error`, `_validated_url`.
- `app/api/settings.py`: `_provider_client` (owner-scoped transient client), `_health_details`, `_health_fragment` (already swaps an out-of-band `datalist#provider-models-<provider>`), `MODEL_PATTERN`, `/test-provider`, `/test-embeddings`, `/ollama/models`, `_validated_ai_values`, `update_ai_settings`.
- `templates/components/settings.html`: provider cards with `list="provider-models-<provider>"` + empty datalist, `provider-status-*`, `provider-save-*`; routing block with `task-<stage>-model` free-text inputs (no list yet).

### Established Patterns
- HTMX fragments with escaped server-owned text; `hx-on::before-swap` lets 4xx/5xx swap in the providers section.
- Tests: `authenticated_client` / `authenticated_user` fixtures, `tests/run_phase17.py` runner (disposable DB, sockets blocked).

### Integration Points
- `_health_fragment` datalist swap, `/test-embeddings`, task model inputs, `docs/USER_MANUAL.md`, `docs/CONTRIBUTING.md`.
</code_context>

<specifics>
## Specific Ideas

- Gemini listing: `GET /v1beta/models?pageSize=100[&pageToken=...]`, response `models[].name` ("models/gemini-2.5-flash"), `supportedGenerationMethods`, `nextPageToken`.
- Anthropic listing: `GET /v1/models?limit=100[&after_id=...]`, `data[].id`, `has_more`, `last_id`.
- OpenAI-family listing: `GET <base>/models`, `data[].id` (OpenRouter adds `architecture.output_modalities`).
- Ollama listing: `GET /api/tags`, `models[].name`, `details.family`.
</specifics>

<deferred>
## Deferred Ideas

- Remote `ollama pull` from the UI.
- Paid generation probe ("test this model") per model.
- Persistent (database) catalog cache and background refresh.
- Model pricing / context-window metadata display.
- Private-network denylist for custom endpoints (conflicts with LAN-first design).
</deferred>
