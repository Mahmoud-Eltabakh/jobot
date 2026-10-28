---
phase: 17
milestone: v7.0
status: researched
created: 2026-10-27
discovery_level: 1
independent_researcher: unavailable
---

# Phase 17 Research

## Scope and Evidence

Preserve the five existing plans and all CONTEXT decisions. Extend existing httpx/openai/Ollama clients, authenticated UserSetting encryption, FastAPI forms and Jinja/HTMX. No new framework, packages, billing system, automatic failover, cloud embeddings or employer submission. This is source-grounded planner research, not a separately dispatched researcher result: the session exposes no named-agent dispatch tool. Independent plan/UI checking remains pending.

## Standard Stack

Existing manifests: httpx>=0.28.0, openai>=1.57.0, ollama>=0.4.0, pytest>=8.3.0, pytest-asyncio>=0.24.0, Pydantic v2, SQLModel. Use installed versions; do not upgrade or edit manifests. Tests use AsyncMock/monkeypatch/httpx.MockTransport, not new pytest-httpx. Keep BaseAIClient.generate(prompt, system_prompt=None, json_mode=True) and its string result; downstream Pydantic parsers own domain schemas. Keep separate adapters, not an orchestration framework.

## Verified Local Findings

| ID | Evidence | Required planning consequence |
|----|----------|-------------------------------|
| R-01 | client.py factory takes (session=None, user_id=None); many positional calls exist | Add keyword-only task_type; retain old calls and injected clients. |
| R-02 | configured() falls back to global/environment openai_api_key | Owner secrets must never use global fallback; test missing-owner-key with populated global key. |
| R-03 | set_user_setting commits each write | Add commit=True compatibility option plus one-transaction batch; test injected failure rollback. |
| R-04 | owner legacy openai_api_key already encrypted; AppSettings is plaintext/global | Migrate only same-owner legacy key idempotently; new provider keys never use global storage. Existing installation-only legacy secrets are not implicitly claimed/deleted. |
| R-05 | GET /settings, /test-ai, /ollama/models and web settings use different fallback logic | Retrofit every old/new credential route; test URLs/models/has_key as well as key use. |
| R-06 | strategist and scheduler use unscoped/default clients; worker resolves one default | Stage-specific resolution at controlling entry points; separate scraping/scoring clients and preserve task owner/worker bounds. |
| R-07 | extractor method is extract_from_html; evaluator is evaluate_and_update_job; resume method ends _points | Use actual methods, not names from original plan. |
| R-08 | embeddings.py and feedback.py call the supplied generation client's embed | Dedicated local resolver covers profile write, similarity, feedback write/query; all profile/CV/LinkedIn/web entry points pass owner context. |
| R-09 | evaluator baseline, scraper heuristics, generator templates and profile sync broad catches can hide provider failure | Typed provider failures bypass all success fallbacks; leave persisted materials/jobs/vectors unchanged on failure. |
| R-10 | real queue template is queue_view.html; ScrapeTask.error_message exists, Job error field is not established | Reuse task diagnostics, query owner/job-scoped failure context, no schema invented. |
| R-11 | conftest clears all configured SQLModel tables; main uses JOBOT_TESTING | Set disposable DB/vector/key paths before imports; disable workers/scheduler; never test against data/. |
| R-12 | Settings has user modifications across remote, concurrency and scraper sections | Modify AI section only; no redesign/frontend packages; retain existing tests and settings. |

## Architecture Patterns

### Resolution and migration

get_ai_client(session=None, user_id=None, *, task_type='scoring') supports scraping/scoring/applying/embeddings. Task provider/model overrides owner legacy configuration, then non-secret installation defaults. An owner missing a key gets an explicit configuration error. Zero-argument trusted legacy callers retain installation behavior, but authenticated production boundaries must pass an owner. Unknown task/provider raises before I/O. get_embedding_client always returns Ollama with nomic-embed-text and the owner's Ollama endpoint, independent of generation choices. Optional Ollama credentials use the same encrypted owner vault and Authorization header, never another provider's key.

Vault keys are provider_{provider}_key, provider_custom_url and task_{stage}_{provider,model}. Blank keys preserve; new keys encrypt via existing user-bound authenticated encryption, not a new cipher. Owner-specific legacy custom credentials map to custom only. Global secrets are neither account defaults nor automatically imported. Transaction helper validates/encrypts/adds all writes and commits once, rolls back on any failure. Do not claim an outer transaction is atomic if inner helpers still commit.

### Adapter protocol

| Provider | Adapter and endpoint | Authentication / response |
|----------|----------------------|---------------------------|
| ollama | OllamaAIClient; owner ollama_base_url | Optional owner bearer token; chat content and fixed-model embeddings. |
| openai | OpenAICompatibleClient; https://api.openai.com/v1 | Bearer key; chat.completions string, json_object mode. |
| anthropic | AnthropicClient; https://api.anthropic.com/v1/messages | x-api-key, anthropic-version 2023-06-01; top-level system, max_tokens=4096, messages; concatenate text blocks only. |
| gemini | GeminiClient; https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent | x-goog-api-key header; systemInstruction, contents, generationConfig.responseMimeType; non-thought candidate text only. |
| groq | OpenAICompatibleClient; https://api.groq.com/openai/v1 | Provider-specific bearer key. |
| deepseek | OpenAICompatibleClient; https://api.deepseek.com | Provider-specific bearer key. |
| openrouter | OpenAICompatibleClient; https://openrouter.ai/api/v1 | Provider-specific bearer key; optional non-secret HTTP-Referer/X-Title. |
| custom | OpenAICompatibleClient; owner provider_custom_url | Own key only; validated http(s) URL; no embedded credentials/query/fragment or redirect following. |

Provider defaults must include editable model hints: Ollama llama3.1:8b, OpenAI gpt-4o-mini, Anthropic claude-sonnet-4-5, Gemini gemini-2.5-flash, Groq llama-3.3-70b-versatile, DeepSeek deepseek-chat, OpenRouter openai/gpt-4o-mini; custom requires an explicit model. These strings are compatibility defaults, not verified account entitlements or a claim that a model remains available. A retired/unsupported model must error, never silently change.

Use generation timeout 120s, connect timeout 5s, health deadline 5s, no SDK retries by default. Keep existing lower Ollama health bounds. Close httpx clients with async context managers; propagate cancellation. Cloud adapters must implement abstract embed even where unsupported (explicit NotImplementedError). Keep direct existing OpenAI embed API compatible, but never call it from application vector paths.

JSON mode is an output request, not schema enforcement. Anthropic adds explicit JSON-only instructions, Gemini uses REST camelCase responseMimeType, OpenAI-compatible uses existing response_format. Query strategist expects an array while OpenAI json_object expects an object: for that path request an object envelope containing queries, unwrap and validate it, and accept a legacy array from injected callers. Preserve existing extraction/evaluation models and reject invalid/empty/blocked/truncated content with a typed safe failure, not fabricated data. Do not expose thought blocks or provider payloads.

Health is non-generating: Ollama GET /api/tags; OpenAI-family SDK models.list; Anthropic GET /v1/models; Gemini GET /v1beta/models. A public models list (notably gateways) cannot prove credentials or billing. Report reachability plus credential_validation='unverified' where applicable; never generate a paid probe or announce a model is usable from model listing alone.

### Presets

| ID / label | Scraping | Scoring | Applying |
|------------|----------|---------|----------|
| local / 100% Free / Local | ollama + owner's ollama_model | same | same |
| hybrid / Cost-Optimized Hybrid | ollama + owner's ollama_model | same | openai + gpt-4o-mini |
| cloud / Max Quality Cloud | openai + gpt-4o-mini | same | same |

Default ollama_model is llama3.1:8b. Each tuple remains editable. Preset labels are requested product labels, not measured economic/quality claims. Missing owner credentials rejects with 422 and no writes. Presets update six assignment fields only, never secrets/endpoints. The manual local action uses preset=local and does not enqueue/retry; retry is separate and owner-checked. Preserve existing queue retry semantics rather than introducing a new failure/retry state machine.

### Failure transparency and vectors

AIProviderError stores provider/model/category/status_code and a stable bounded safe message. Categories: configuration, authentication, rate_limit, quota, timeout, unavailable, invalid_response, embedding_dimension. No raw key/body/request/URL/exception chain in persisted strings, logs or fragments; escape HTML separately. Unknown IDs are ValueError configuration failures. REST maps provider failure to 502 (local unavailable 503); HTMX must explicitly display non-2xx error fragments. Queue stores only safe fields in existing error_message and marks failed. No automatic provider/model switch, template material, heuristic extraction or direct-score substitution after a provider failure.

Vector compatibility validates finite/nonempty vectors, batch dimension agreement and collection dimension before write/query. A mismatch requires explicit operator re-index after backup; do not reset collections, fabricate zeros or cloud-embed. No destructive migration/re-index is part of this phase. Existing vector account-partitioning architecture is not redesigned; changed paths retain ownership context and must not broaden visibility.

## Architectural Responsibility Map

| Boundary | Owner | Consuming plans |
|----------|-------|-----------------|
| Protocol, defaults, safe error, client/embedding resolution | app/ai/client.py | 01 |
| Encryption, owner migration, batched commit | app/db/database.py | 02 |
| Authentication, validation, secret/preset/test routes | app/api/settings.py | 02, then 04 for fragment wiring |
| Stage selection and error propagation | worker/scheduler/strategist/extractor/evaluator/generator/profile paths | 03, then web in 04 |
| Display and manual actions | web routes/settings/inspector/queue_view | 04 |
| Cross-boundary regression and accurate docs | existing tests and documentation suite | 05 |

## Don't Hand-Roll

Reuse user encryption, SQLModel transaction/session APIs, httpx transport mocks, OpenAI SDK payloads, Pydantic model_validate/model_validate_json, Jinja escaping and HTMX partial rendering. Do not add orchestration, gateway, telemetry, crypto or testing dependencies. Meaningful docstrings should explain secret provenance, transaction ownership and local-vector invariants toward the 20-30% convention, not narrate syntax.

## Package Legitimacy Audit

No package-manager install tasks exist. httpx, openai, ollama, pytest and pytest-asyncio already appear in repository manifests; nothing new is authorized. Any later dependency proposal requires a fresh registry legitimacy audit and human approval; no unattended install.

## Validation Architecture

Extend existing test_ai_client, test_auth_security, test_db/config, test_ai_scraping, test_embeddings/feedback/evaluator, test_application_generator/profile_and_linkedin, test_web_routes/htmx_views and e2e/parallel modules. Each source slice runs its task's focused pytest immediately. Parametrize providers and error cases; mocked transports never generate paid traffic. Guard two-account/global-key isolation, legacy positional compatibility, blank keys, rollback, all four local-vector operations, synthetic-success catches, HTMX 422 behavior and separate switch/retry. Existing per-phase verify commands are mostly prose, not runnable; do not copy them as commands. Windows commands use .venv/Scripts/python.exe -m pytest from repo root; full-suite gate is once in 17-05. See VALIDATION for safe environment and exact task map. Browser desktop/mobile checks are execution-only and remain pending at planning time.

## Sources and Confidence

- Actual source/tests above read 2026-10-27; source contracts take precedence over older external brain-plan references (removed from plans).
- https://platform.claude.com/docs/en/api/messages and /en/api/models/list: fetched 2026-10-27; confirms messages/system/max_tokens/content blocks and non-generating model list. Examples now show newer API version/auth options; executor must retain compatibility-header tests and verify x-api-key support before any live use.
- https://ai.google.dev/api/generate-content and https://ai.google.dev/api/models: fetched 2026-10-27; confirms generateContent, systemInstruction, responseMimeType, candidate/finish handling and model listing. Do not copy volatile sample model names as verified entitlements.
- Context7 CLI resolved /encode/httpx; targeted docs query recorded during planning. Installed SDK compatibility is checked by tests rather than assumed from latest docs.
- Confidence: high in local signatures/risks; model entitlements and real credential behavior unverified. No paid/live provider smoke test performed. Graph disabled; context/codebase drift checks skipped for absent prior artifacts/map. No independent researcher, pattern-mapper, AI/UI checker or plan-checker result is claimed.

## Source Coverage Audit

| Source | ID | Scope item | Plans | Status |
|--------|----|------------|-------|--------|
| GOAL | G-17 | Independent hybrid stages, vault, local vectors, transparent failure and presets | 01-05 | COVERED |
| REQ | REQ-HYB-01 | Stage routing | 03, 05 | COVERED |
| REQ | REQ-HYB-02 | Eight-provider encrypted vault | 01, 02, 05 | COVERED |
| REQ | REQ-HYB-03 | Direct lightweight adapters | 01, 05 | COVERED |
| REQ | REQ-HYB-04 | Local nomic vectors | 03, 05 | COVERED |
| REQ | REQ-HYB-05 | Safe explicit failures/manual recovery | 03, 04, 05 | COVERED |
| REQ | REQ-HYB-06 | Credential tests, task controls, presets | 02, 04, 05 | COVERED |
| RESEARCH | R-01, R-02 | Compatibility and secret provenance | 01, 05 | COVERED |
| RESEARCH | R-03, R-04, R-05 | Atomicity, migration, legacy route isolation | 02, 05 | COVERED |
| RESEARCH | R-06, R-07, R-08, R-09 | Real methods, every stage/vector path, no hidden success | 03, 04, 05 | COVERED |
| RESEARCH | R-10, R-12 | Actual templates, owned errors, preserved UI | 04 | COVERED |
| RESEARCH | R-11 | Disposable test storage | all via VALIDATION, 05 | COVERED |
| CONTEXT | D-01 | Compatibility | 01, 02, 03, 05 | COVERED |
| CONTEXT | D-02 | Owner isolation | 01-05 | COVERED |
| CONTEXT | D-03 | Local vectors | 01, 03, 04, 05 | COVERED |
| CONTEXT | D-04 | Unknown provider/transparent failure | 01-05 | COVERED |
| CONTEXT | D-05 | Encryption/blank keys | 02, 04, 05 | COVERED |
| CONTEXT | D-06 | Non-reflection | 01, 02, 04, 05 | COVERED |
| CONTEXT | D-07 | Submitted/owner test credentials | 02, 04, 05 | COVERED |
| CONTEXT | D-08 | Assignment-only presets | 02, 04, 05 | COVERED |
| CONTEXT | D-09 | Existing HTMX/Tailwind | 04, 05 | COVERED |
| CONTEXT | D-10 | Independent tests/controls/manual local | 02, 04, 05 | COVERED |
| CONTEXT | D-11 | Preserve existing settings/queue/worktree | all | COVERED |

Deferred CONTEXT ideas are excluded, not missing. Runtime behavior is planned, not implemented or verified.