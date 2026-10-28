# Phase 17: Multi-Provider & Hybrid Local/Cloud AI Routing Engine - Context

**Gathered:** 2026-10-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver independent scraping, scoring, and applying provider/model assignments,
encrypted account-owned credentials for the eight planned providers, local-only
Ollama embeddings, explicit provider failures, and usable Settings presets.
No automatic application submission or silent provider failover is in scope.
</domain>

<decisions>
## Implementation Decisions

### Routing and Compatibility
- **D-01:** Keep existing callers and legacy provider settings working during migration.
- **D-02:** Resolve task settings for the authenticated owner; never borrow another account's credentials.
- **D-03:** Keep embeddings on Ollama with nomic-embed-text regardless of generation routing.
- **D-04:** Reject unknown providers and surface failures rather than silently changing models.

### Credentials and Presets
- **D-05:** Reuse authenticated per-user encryption; blank secret inputs preserve saved keys.
- **D-06:** Never render saved keys or raw credential-bearing provider errors in HTML or logs.
- **D-07:** Connection tests use submitted credentials or the current owner's saved credential.
- **D-08:** Local, hybrid, and cloud presets change assignments only, not saved credentials.

### Settings and Failure States
- **D-09:** Extend the existing HTMX/Tailwind Settings view without a new frontend stack.
- **D-10:** Provide independent provider tests and task provider/model controls; keep fallback manual through an explicit local-preset action.
- **D-11:** Preserve existing settings, queue behavior, and unrelated worktree changes.

### Agent's Discretion
- The user is unavailable and explicitly authorized autonomous decisions for later review.
- Choose conservative provider defaults and test payloads without paid live generation.
- Do not claim live credential validation or human acceptance without evidence.
</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- app/ai/client.py owns BaseAIClient, OllamaAIClient, OpenAICompatibleClient, and the factory.
- app/db/database.py provides get_user_setting and encrypted set_user_setting.
- app/api/settings.py and templates/components/settings.html own Settings workflows.

### Established Patterns
- Python/FastAPI, SQLModel, Jinja2, HTMX, existing httpx/openai dependencies.
- Per-user configuration with encrypted sensitive values and non-reflected secrets.
- Existing pytest fixtures and test modules are preferred over new test infrastructure.

### Integration Points
- Scraping strategists/extractors, scoring evaluator, application generation, profile embeddings.
- Queue errors and Settings diagnostics must preserve actionable, secret-free failures.
</code_context>

<specifics>
## Specific Ideas

Preserve the five existing plans. Validate and adjust them against actual code,
especially legacy factory signatures, account isolation, and encrypted migration.
</specifics>

<deferred>
## Deferred Ideas

Automatic cross-provider failover, cloud embeddings, provider billing dashboards,
and automatic employer-form submission remain out of scope.
</deferred>