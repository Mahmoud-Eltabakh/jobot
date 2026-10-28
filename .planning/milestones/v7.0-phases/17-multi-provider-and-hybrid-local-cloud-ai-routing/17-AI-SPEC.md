# AI-SPEC - Phase 17: Multi-Provider and Hybrid Routing

Status: draft, source-grounded autonomous planning contract (2026-10-27). No separate framework-selector/researcher/eval-planner or independent review result is claimed. No new dependencies or paid/live model calls authorized.

## 1. System Classification

System Type: Hybrid extraction, fit scoring and application content generation with local vector retrieval. Phase 17 changes provider routing, not autonomous tool execution or the business prompt strategy.

Critical failures: account credentials/configuration cross owners; private embeddings reach a cloud endpoint; provider errors become fabricated success or a silent model swap; assignment changes partially persist; raw secrets/provider responses reach UI/logs/queue diagnostics.

## 1b. Domain Context

Industry: personal career-search assistance. Users own resumes, employment history, job notes and provider keys. Stakes: high privacy/reputational impact; generated application content is human-reviewed, never employer-submitted automatically.

| Dimension | Good | Bad | Stakes / Source |
|-----------|------|-----|-----------------|
| Ownership | Owner-specific credentials and configuration | Another account/global key is borrowed | Critical; REQ-ACC and D-02 |
| Local vectors | All vector text stays with configured Ollama | Cloud embed called for feedback or CV | Critical; REQ-HYB-04 |
| Generation fidelity | Existing system/user prompts, tone and domain parsers retained | New adapter strips system prompt or invents fallback materials | High; existing generator/evaluator/extractor tests |
| Failure truthfulness | Safe error with provider/model/status and explicit manual recovery | False success, silent swap, swallowed quota | High; REQ-HYB-05 |

Known domain failure: resumes contain untrusted text, generated materials can invent achievements, and fit failures can erase/promote jobs if substituted with baseline scoring. Preserve existing prompt boundaries and never treat provider output as instructions to modify routing or credentials. Privacy/GDPR considerations may apply to CV processing by chosen cloud vendors; no legal compliance certification is asserted. User reviews generated content before use. Engineer evaluates deterministic routing/security; candidate owns factual application review.

## 2. Framework Decision

Selected Framework: existing direct BaseAIClient adapters using installed httpx/openai/ollama and Pydantic, no orchestration framework.

Version: retain installed versions satisfying current manifests, httpx>=0.28.0/openai>=1.57.0/ollama>=0.4.0; record installed versions during execution, no version upgrade. Anthropic REST compatibility version 2023-06-01; Gemini v1beta REST.

Rationale: eight providers require protocol translation and owner settings, not agents/graphs. Adding LiteLLM/LangChain/native heavy SDKs increases dependencies and migration cost without meeting an unmet requirement. Alternatives: provider-native Anthropic/Gemini SDKs rejected because httpx is present; gateway framework rejected to honor direct-adapter requirement and no new dependencies. Partial vendor lock-in accepted only inside adapters; preserve BaseAIClient contract.

## 3. Framework Quick Reference

No installation step. Existing imports remain app.ai.client, httpx, openai, SQLModel Session. Intended owner-aware entry point (contract illustration, not implemented yet):

```python
generation_client = get_ai_client(session, current_user.id, task_type="scoring")
embedding_client = get_embedding_client(session, current_user.id)
response = await generation_client.generate(prompt, system_prompt=system_prompt, json_mode=True)
```

Generation returns text; domain Pydantic schemas validate afterward. HTTP clients use async context management, connect=5s/generation=120s, health whole-operation deadline 5s, max_retries=0. Cloud adapters implement abstract embed with an explicit unsupported error; application vector paths use Ollama only. No static global per-account client cache.

Official protocol sources and response shapes are recorded in RESEARCH. Anthropic uses top-level system and text content blocks; Gemini uses systemInstruction/contents/generationConfig.responseMimeType and candidate text, excluding thought parts. Reject refusal/truncation/invalid/empty outputs. OpenAI json_object expects object output: query arrays use a queries envelope with validated unwrapping, preserving injected legacy array compatibility.

## 4. Implementation Guidance

Task assignments and encrypted keys persist under current user_id. Factory has existing positional session/user_id and keyword-only task_type. Missing/unknown provider/model/key errors are explicit, not alternate-provider fallback. Local/hybrid/cloud presets follow exact RESEARCH tuples and update only assignments atomically. Optional Ollama token stays owner-encrypted and bound to the owner's host. Non-generating health never proves model entitlement or billing. Default model hints are editable and not certified live availability.

Keep existing prompt length caps, prompt/user separation and tone handling. No schema expansion, business scoring redesign, automatic tool actions or extra prompt-improvement experiment in scope. Use safe AIProviderError diagnostics, no raw request/body/URL/chained exception logging. Preserve existing task queue concurrency; cancellation propagates.

## 4b. AI Systems Best Practices

### Structured Outputs with Pydantic

Reuse existing AIExtractedJobListing and evaluator/profile models. Illustrative consumer contract:

```python
from app.scrapers.ai_extractor import AIExtractedJobListing

validated_listing = AIExtractedJobListing.model_validate_json(response)
```

Arrays use parsed/validated item models or existing expected structure; JSON mode is not validation. No hidden model repair or cross-provider retry on parse failure. The illustrative snippets do not authorize production code changes during planning.

### Async, Prompts and Context

Await I/O, close short-lived clients, never share SQLModel Sessions across concurrent tasks; keep per-task owners and semaphore limits. Prompt text is untrusted data and never controls provider URLs, keys or task assignment. Preserve existing truncation caps and fit scoring schema. Do not expose hidden reasoning blocks.

### Cost and Latency

No live paid generation in planning/tests. Embeddings are local nomic-embed-text. Requested presets reduce cloud stages by construction but measured savings and comparative quality are not claimed. Existing retries are manual and provider health has a bounded deadline.

## 5. Evaluation Strategy

| Dimension | Pass Criterion | Measurement | Priority |
|-----------|----------------|-------------|----------|
| Routing | Every stage receives its saved provider/model | pytest owner-aware E2E and factory spies | Critical |
| Secret isolation | Zero foreign/global secret use in authenticated flows | Two-account matrix + log/HTML/JSON/header assertions | Critical |
| Embedding locality | Zero cloud embed calls for profile/job/feedback | Local transport spy across four paths | Critical |
| Failure truthfulness | Typed error, no swap/synthetic material or destructive update | Inject 401/402/429/5xx/timeout/dimension failures | Critical |
| Atomicity | Every preset saves all six fields or none | Commit-failure injection/DB assertions | High |
| Prompt/schema fidelity | Existing prompt/JSON/text contracts remain valid | Existing and expanded adapter/domain tests | High |

Primary Tool: existing pytest/Pydantic and transport spies; no eval service/LLM judge needed for this deterministic routing change. Reference dataset: test-only parameter matrix of eight provider IDs, two accounts, four task identifiers, three presets, legacy/new/blank/missing keys, malformed/blocked/empty content and status/timeouts. Store examples inside existing test modules, not a new benchmark file. Engineer labels expected protocol/routing outcomes. Subjective output quality/model ranking remains unverified, not inferred from mocked payload tests.

Commands and ownership per task are in VALIDATION. CI/developer gate: isolated `.venv/Scripts/python.exe -m pytest tests -q`, preceded by each slice's focused tests.

## 6. Guardrails

Online: reject unknown IDs/missing keys/invalid endpoints before network; owner-bound encrypted credentials; fixed-model local vectors; safe categorized errors; validate whole assignment update before one commit; no provider/model automatic switch; no browser reflection. Offline: regression matrix blocks new leakage, hidden success or cloud vectors. No automatic job/material/collection deletion on provider errors. Explicit re-index remains operator-controlled after backup.

## 7. Production Monitoring

Tracing Tool: existing application logging plus owned ScrapeTask error/status history. No Phoenix/third-party tracing dependency or new telemetry service is added under the no-new-dependencies scope. Log only provider/model/category/status and existing task IDs; never prompts, CVs, keys or raw payloads. Safe failure is immediately visible to its owner in Queue/Inspector/Settings. Existing test regressions, not an invented operational alerting platform, are the release gate. Human content quality review is user-driven; no benchmark quality or live entitlement result exists yet.

## Checklist

- [x] System and critical privacy/failure risks classified.
- [x] Existing direct-adapter framework selected with alternatives documented.
- [x] Protocol/parser/async and owner boundaries grounded in source and docs.
- [x] Deterministic evaluation matrix and guardrails assigned to plans.
- [ ] New assertions, browser evidence and independent review complete.

Approval: pending independent review; runtime/model quality not validated by this artifact.