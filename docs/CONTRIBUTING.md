# Contributing to Jobot — Developer & Architecture Guide

Welcome! This guide is for developers contributing to the Jobot codebase, architecture, scrapers, AI pipelines, or UI.

---

## 🏗️ 1. Technical Architecture & Philosophy

- **Language Policy**: **Python-First / Pure Python**. Everything (scrapers, API, background jobs, database, AI/RAG engine, and web interface) is written in Python.
- **Frontend Stack**: FastAPI + Jinja2 + HTMX + Tailwind CSS. Zero Node.js/npm dependencies.
- **AI & RAG Engine**: Pluggable interface supporting **Local Ollama** (`ollama-python`) and **Cloud/Custom AI APIs** (`openai` / `httpx`) with ChromaDB for local vector embeddings.
- **Scraping Engine**: `python-jobspy` (LinkedIn, Google Jobs) + Playwright (StepStone).
- **Database**: SQLite with SQLModel / SQLAlchemy (WAL mode enabled for concurrent worker & UI reads/writes).
- **Docker-First Environment**: Hot-reloading Docker Compose stack for local development (`docker-compose.dev.yml`).

---

## 🛠️ 2. Development Setup

### Option A: Docker Development (Recommended)
```bash
# 1. Clone repository
git clone https://github.com/Mahmoud-Eltabakh/jobot.git
cd Jobot

# 2. Start the dev stack with hot reload & local Ollama
docker compose -f docker-compose.dev.yml up --build

# 3. Pull required Ollama models inside the Ollama container (if using local AI)
docker exec -it jobot-ollama-dev ollama pull llama3.1:8b
docker exec -it jobot-ollama-dev ollama pull nomic-embed-text
```
The application will be live at `http://localhost:8000` with instant live code reloading.

### Option B: Local Python Environment
```bash
# 1. Create and activate virtual environment (Python 3.10+)
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies & Playwright Chromium
pip install -r requirements.txt
playwright install chromium

# 3. Copy environment configuration
cp .env.example .env

# 4. Start local development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## 📂 3. Project Directory Structure

```
Jobot/
├── app/
│   ├── main.py              # FastAPI app creation & lifespans
│   ├── core/                # Settings (Pydantic), logging & security
│   │   ├── config.py
│   │   └── logging.py
│   ├── db/                  # SQLModel database engine, models & ChromaDB
│   │   ├── database.py      # SQLite WAL connection & AppSettings helpers
│   │   ├── models.py        # Relational models (Job, FilterRule, UserProfile...)
│   │   └── vector.py        # ChromaDB collections & similarity search
│   ├── scrapers/            # Scraper integrations (JobSpy, StepStone Playwright)
│   ├── ai/                  # AI matching, scoring prompt templates & RAG
│   ├── api/settings.py      # AI, scoring, blacklist & Tailscale preference endpoints
│   ├── api/suggestions.py   # Owner-scoped blacklist/search-term suggestions (approve/dismiss)
│   ├── api/diagnostics.py   # /api/diagnostics/health and polled system alerts (no secrets, no probes)
│   └── web/                 # FastAPI routes, Jinja2 templates & HTMX components
├── data/                    # Persistent SQLite database & ChromaDB files (gitignored)
├── docs/                    # User manual and documentation
│   ├── USER_MANUAL.md       # End-user guide & dashboard walkthrough
│   └── CONTRIBUTING.md      # Developer & contributor guide
├── k8s/                     # Kubernetes manifests
├── scripts/                 # Automation scripts (.sh and .ps1)
├── tests/                   # Pytest test suite
├── Dockerfile.dev           # Development container specification
├── docker-compose.dev.yml   # Multi-container dev orchestrator
├── pyproject.toml           # Project metadata & tool config
└── requirements.txt         # Pinned python dependencies
```

---

## 🧪 4. Testing & Code Quality

### Running Tests

`tests/conftest.py` clears every SQLModel table in the configured engine. It does **not** automatically select an in-memory database. Never run bare pytest against an installation's configured database, Chroma directory or encryption key.

```bash
# Windows: unique disposable storage before app imports, workers disabled, sockets guarded
.venv/Scripts/python.exe tests/run_phase17.py tests -q

# Linux/macOS equivalent
.venv/bin/python tests/run_phase17.py tests -q

# Focused example, same safety wrapper
.venv/Scripts/python.exe tests/run_phase17.py tests/test_ai_client.py tests/test_auth_security.py -q -x
```

The runner sets unique temporary `DATABASE_URL`, `CHROMA_DIR` and `ENCRYPTION_KEY_FILE`, plus `JOBOT_TESTING=1`, `ENV=testing` and disabled Chroma telemetry, before application imports. It blocks unmocked socket connections, including local services; Windows asyncio's internal socket pair is the narrow exception. Environment changes stay inside the child Python process. Use fake keys only. Keep real cloud requests, paid generation and model downloads out of regression tests. Provider credentials and encryption secrets in your developer environment must not be used by test doubles.

### Security & Functional Testing
- **Isolated Storage**: Use the runner above or set all disposable storage variables before any application import. The shared autouse fixture deletes SQL rows, not vector collections; tests that need vector isolation must own a disposable collection/store and supply explicit embeddings.
- **Transport Tests**: The `provider_transport` fixture intercepts native `httpx` and the installed OpenAI SDK's actual HTTP backend (which can be `httpx2`). Mocking only one backend is insufficient. Unexpected destinations must fail rather than fall through to a network request.
- **Security Tests**: All PRs modifying authentication, queue ingestion, or AI parsing must include tests verifying error resilience and boundary enforcement.

### Code Formatting & Linting
We use Ruff for linting and code formatting:
```bash
# Run linter checks
ruff check .

# Format code
ruff format .
```

### Comment Coverage

For new or substantially modified source modules, target approximately **20–30% meaningful comment coverage** across non-blank source lines. This is a module-level readability target, not a rigid quota for every function.

Comments that count toward the target include:

- Module, class, and function docstrings that document behavior or contracts.
- Explanations of non-obvious control flow, invariants, security boundaries, failure handling, and external-service constraints.
- Short section comments that make a complex operation easier to scan.

Avoid comments that simply translate code into English, repeat names, describe obvious assignments, or exist only to increase the percentage. When modifying an existing file, improve comments around the changed behavior without reformatting or commenting unrelated areas.

---

## 🧩 5. Core Development Guidelines

1. **Database Schema Changes**:
   - Add/modify models in `app/db/models.py`.
   - Update `app/db/__init__.py` exports.
   - Add corresponding test cases in `tests/test_db.py`.
2. **AI Provider Implementations**:
   - Keep AI clients pluggable with editable models and an explicit manual local routing option. Never implement silent provider/model failover or synthetic success after a provider failure.
3. **Scraper Guidelines**:
   - Always implement human-like delays (2-5s) and handle anti-bot headers.
   - Always run raw scraped jobs through the **Title & Keyword Pre-Filter Pipeline** before calling LLM scoring.
4. **Security & Data Isolation**:
   - Every new FastAPI endpoint returning or modifying user data **must** validate the resource against `owned_by_id(current_user.id)`.
   - Never expose raw credentials (like `li_at` cookies) in JSON responses.
5. **Interactive Decisions**:
   - Maintain the developer decision-making protocol. Any structural or architectural changes must be documented in `.planning/`.
5. **Remote Access Integrations**:
   - Keep Tailscale and SSH administration outside the FastAPI process. The web UI may detect status and persist validated connection preferences, but must not invoke privileged connect/disconnect operations.
   - Bound subprocess status checks with a timeout and invoke executables without `shell=True`.
   - Validate any hostname, username, or port interpolated into displayed command guidance.
   - Cover Settings rendering and persistence in `tests/test_web_routes.py`.

---

### Phase 17 Routing and Failure Contracts

`get_ai_client(session, user_id, *, task_type="scoring")` supports `scraping`, `scoring`, `applying` and the special local-only `embeddings` task. Preserve existing positional callers. Account clients are resolved per invocation; never cache another owner's client or share SQLModel sessions between concurrent tasks. `get_embedding_client(session, user_id)` always selects owner-local Ollama with `nomic-embed-text`. Legacy positional generation injections into vector helpers are not embedding overrides; tests must use the explicit `embedding_client=` seam when needed.

Provider IDs: `ollama`, `openai`, `anthropic`, `gemini`, `groq`, `deepseek`, `openrouter`, `custom`. Native Anthropic/Gemini REST adapters use the existing `httpx`; OpenAI/Groq/DeepSeek/OpenRouter/Custom use the installed OpenAI-compatible SDK. No extra provider framework or dependency is required. `PROVIDER_DEFAULTS` in `app/ai/client.py` is the canonical editable-model/endpoint table, not a live availability registry. Cloud adapters must not receive application vector text.

Owner settings contracts:

- Secrets: `provider_{provider}_key`; optional Ollama bearer token uses `provider_ollama_key`. Blank values preserve ciphertext. New slots always encrypt; never use plaintext global `AppSettings` for account credentials.
- Endpoints: `ollama_base_url`, `provider_custom_url`; provider hints: `{provider}_model`. Account custom endpoints must not inherit global URLs or another provider's credentials.
- `get_provider_defaults` shares effective non-secret Ollama installation/owner endpoint and model defaults across factories, Settings, probes and local/hybrid presets. OpenAI uses its canonical fixed endpoint consistently across Settings, probes and generation. A noncanonical legacy `openai_base_url` is rejected before sending the OpenAI key; configure OpenAI-compatible endpoints explicitly as `custom` with `provider_custom_url` and its own key. Never add keys to the defaults resolver; custom provider model hints retain precedence over matching-owner legacy hints.
- Six assignments: `task_scraping_provider`, `task_scraping_model`, `task_scoring_provider`, `task_scoring_model`, `task_applying_provider`, `task_applying_model`.
- `local`: all stages `ollama` + owner's `ollama_model` (default `llama3.1:8b`). `hybrid`: scraping/scoring local, applying `openai` + `gpt-4o-mini`. `cloud`: all stages `openai` + `gpt-4o-mini`. Presets alter only these six fields; hybrid/cloud reject absent owner OpenAI credentials before writing.
- Matching owner legacy `ai_provider`/`openai_api_key` settings migrate idempotently during a successful settings save; custom legacy keys remain custom. Explicit vault/task records win. Reads/probes never migrate or import global/environment credentials.
- `set_user_setting(..., commit=False)` participates in `set_user_settings` batches. Validate the entire input before staging writes; flush, encryption or commit failure must roll back the entire batch. Preset tests inject a failure after intermediate flushes, not only before commit.

Settings routes are authenticated: `GET /api/settings`, `POST /api/settings/ai` (alias `/ai/credentials`), `POST /api/settings/ai/preset`, `POST /api/settings/test-provider`, legacy `POST /api/settings/test-ai`, `GET /api/settings/ollama/models`, and explicit `POST /api/settings/test-embeddings`. Individual probes accept `provider`, `api_key`, `base_url`, `model` and never persist submitted values. Stored keys are write-only; JSON exposes `has_key`, not secret values. Fixed cloud hosts are shared by Settings, probes and generation. Local/custom HTTP(S) endpoints reject userinfo/query/fragment and redirects; URL validation is not a network allowlist.

Model identifiers are at most 200 characters and match `[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,199}`. Save-form values are bounded to 8192 characters. Generation deadlines are 120 seconds, cloud connect timeout five seconds, whole-operation health deadline five seconds (Ollama per-request health timeout four seconds). SDK retries and redirect following are disabled. Non-generating model listing does not verify paid generation, billing or model entitlement.

`AIProviderError` categories: `configuration`, `authentication`, `quota`, `rate_limit`, `timeout`, `unavailable`, `invalid_response`, `embedding_dimension`. Expose allowlisted messages, not exception chains, request URLs, remote bodies, prompts or keys. Application REST errors bound provider/model metadata to 40/120 characters; queue diagnostics use the same bounds and the existing 1000-character `error_message` limit. REST local unavailable/timeout uses 503; other upstream failures use 502. Web provider fragments use 503 for Ollama and 502 for cloud, including cloud timeouts. HTMX must explicitly display non-2xx fragments.

Generation must succeed before a job/material update. Local vector paths validate finite/nonempty/batch-consistent dimensions against stored collections before writing/querying, never reset incompatible collections or delete jobs as outage recovery. Explicit backed-up re-indexing is an operator procedure, not a shipped automatic migration. Existing collection partitioning and cross-store atomicity are not redesigned. Local switch saves assignments only; separate owned retry/generation resolves the newly saved client. Routing tests do not establish output quality, cost savings, hardware compatibility, live entitlements or human UI acceptance.

Provider queue errors call `TaskQueue.mark_failed(..., terminal=True)` to commit diagnostic, retry count and failed status once; ordinary errors retain automatic retries. Settings rescoring catches both factory and evaluator provider errors, with non-2xx HTML swapping scoped to its feedback target. Cover-letter Retry includes the stable original options form, not reflected instructions in the failure fragment.

### Phase 18 Model Discovery Contracts

- `BaseAIClient.list_models() -> ModelListing` (`app/ai/client.py`): `models`, `embedding_models`, `truncated`, `supported`. Listed means advertised, never verified. Filters: Gemini keeps `generateContent` models and drops embed/tts/image/aqa/veo; OpenAI-style lists drop embedding/audio/image/moderation families; Ollama uses `/api/tags` and separates embedding models. IDs must match `MODEL_ID_PATTERN`; others are dropped.
- Caps: `MAX_LISTING_PAGES = 10`, `MAX_LISTED_MODELS = 500`, `MAX_LISTING_BYTES = 1 MiB` (oversize is `invalid_response`), 8s total/5s connect timeout, redirects off.
- Anthropic continuation pages require a non-empty string `last_id` when `has_more` is true; a missing or malformed cursor is `invalid_response`, never a complete listing.
- Keys travel only in headers via POST forms (`POST /api/settings/provider-models`, `refresh=1` to bypass cache); never put them in URLs, logs or fragments. Clients come only from `_provider_client`, so owner key/endpoint binding applies. Remote text reaches HTML only as pattern-filtered, escaped IDs.
- `ModelCatalog` (`app/ai/model_catalog.py`, singleton via `get_model_catalog`/`reset_model_catalog`): key is `(user_id, provider, endpoint, key digest)` from `_catalog_identity`; 300s TTL, 256 entries, 5s per-owner/provider refresh cooldown (`RefreshCooldown` -> 429), `peek` (cache-only, used by saves, no network) and `invalidate` on key/endpoint changes. `validate_configured_model` returns listed / not_listed / unchecked.
- Server fragments use out-of-band slots that must exist in `templates/components/settings.html`: `model-warning-<provider>`, `ollama-requirements-hint`, `embedding-hint`, `model-save-warning`, and `provider-models-<provider>` datalists. Client warnings use `jobotModelWarn` with `textContent` only.
- SSRF stance: custom/Ollama endpoints get URL hygiene (no userinfo/query/fragment, no redirects), not a network denylist; LAN hosts are intentionally allowed.
- Tests: patch `app.ai.client._discovery_http_client` or use the `provider_transport` fixture (MockTransport); reset the catalog per test (see `reset_catalog` in `tests/test_web_routes.py`); use sentinel keys only. Run `.venv\Scripts\python.exe tests/run_phase17.py tests/test_web_routes.py tests/test_model_catalog.py tests/test_ai_client.py tests/test_auth_security.py -q`.

---

## 🔄 6. Open Source Contribution Workflow

### 1. Issue Reporting
- **Bug Reports**: Use [.github/ISSUE_TEMPLATE/bug_report.md](.github/ISSUE_TEMPLATE/bug_report.md). Include steps to reproduce, execution mode (Host Ollama / Docker), and relevant terminal/container logs.
- **Feature Requests**: Use [.github/ISSUE_TEMPLATE/feature_request.md](.github/ISSUE_TEMPLATE/feature_request.md). Explain the motivation, proposed solution, and alternatives considered.

### 2. Branching & Pull Requests
- Fork the repository and create a feature branch off `main` (`git checkout -b feature/my-new-feature`).
- Run tests through the isolated wrapper above and report any baseline failures explicitly; check code with `ruff check .` and format only your changed scope.
- Submit a Pull Request targeting `main` using [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).

### 3. Community & Conduct
Please adhere to our [Code of Conduct](../CODE_OF_CONDUCT.md) in all community interactions. For security disclosures, see our [Security Policy](../SECURITY.md).

---

## 🔄 7. Documentation Synchronization

Whenever you add or change features:
1. Update `docs/USER_MANUAL.md` for end-user functionality.
2. Update `docs/CONTRIBUTING.md` for architecture/developer workflows.
3. Commit your documentation updates along with your code changes.
