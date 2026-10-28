# Jobot Execution Roadmap

## Phase 1: Core Foundation & Data Architecture (Complete)

- **Goal**: Establish the Python backend project structure, SQLite models, vector store (ChromaDB), and settings manager.
- **Plans**:
  - `01-01-PLAN.md`: Project scaffolding (FastAPI, dependencies, environment management, config system). — ✓ Complete
  - `01-02-PLAN.md`: Database layer (SQLAlchemy/SQLModel schema for Jobs, Profiles, Notes, SearchConfigs, StatusHistory). — ✓ Complete
  - `01-03-PLAN.md`: Vector database integration (ChromaDB setup for embedding storage and similarity queries). — ✓ Complete

## Phase 2: CV Parsing & Pluggable AI Matching Engine (Ollama / Cloud API) (Complete)

- **Goal**: Ingest PDF CVs / LinkedIn profile data and build the pluggable AI RAG matching & scoring engine supporting Local Ollama and Cloud/Custom APIs.
- **Plans**:
  - `02-01-PLAN.md`: CV upload & text extraction (PDF/DOCX) + structured profile extraction using LLM. — ✓ Complete
  - `02-02-PLAN.md`: Semantic embedding pipeline for CV profiles and candidate preferences in ChromaDB. — ✓ Complete
  - `02-03-PLAN.md`: Pluggable AI Client & Evaluation Agent: Unified abstraction for Ollama & OpenAI-compatible APIs, prompt engineering for 0-100% fit scoring, strengths, gaps, and missing skills. — ✓ Complete

## Phase 3: Multi-Source Scraping Engine, Filter Pipeline & Background Worker (Complete)

- **Goal**: Implement `python-jobspy` for LinkedIn & Google Jobs, build a dedicated StepStone Playwright crawler, establish title/keyword pre-filtering, and background scheduling with deduplication.
- **Plans**:
  - `03-01-PLAN.md`: Scraper framework & deduplication pipeline with normalized hashing and SQLite persistence. — ✓ Complete
  - `03-02-PLAN.md`: `python-jobspy` integration for LinkedIn & Google Jobs (with rate-limiting and filter mapping). — ✓ Complete
  - `03-03-PLAN.md`: Dedicated StepStone Playwright scraper (handling cookie popups, pagination, salary badges, and detail extraction). — ✓ Complete
  - `03-04-PLAN.md`: **Title & Keyword Pre-Filter Pipeline**: Rule-based screening discarding blacklisted titles (e.g., "Director", "Lead", "Intern") and negative keywords before LLM scoring. — ✓ Complete
  - `03-05-PLAN.md`: APScheduler periodic background worker & on-demand scrape triggers. — ✓ Complete

## Phase 4: Modern Web Dashboard & Job Tracker UI (Complete)

- **Goal**: Implement a clean, responsive web interface with Kanban board, table view, job inspector, multi-criteria sorting & filtering engine, status management, and AI Provider settings.
- **Plans**:
  - `04-01-PLAN.md`: Dashboard layout & theme (Tailwind CSS + HTMX components in FastAPI Jinja2 templates). — ✓ Complete
  - `04-02-PLAN.md`: Kanban board & Table views with live status transitions (all 8 stages). — ✓ Complete
  - `04-03-PLAN.md`: **Multi-Criteria Sorting & Filtering Engine**: Instant HTMX filtering & sorting across Fit Score, salary range, work model (Remote/Hybrid/On-site), source platform, date posted, matched skills, and status toggles. — ✓ Complete
  - `04-04-PLAN.md`: Job Inspector detail modal with AI score breakdown, direct links, and user notes/comments. — ✓ Complete
  - `04-05-PLAN.md`: Settings UI: Search filters, blacklist managers (titles, companies, negative keywords), locations, and **AI Provider Configurator** (Toggle Local Ollama vs. API Key, model dropdown, connection test button). — ✓ Complete

## Phase 5: Feedback Loop & Search Refinement Engine (Complete, verified; gaps closed 2026-10-28)

- **Goal**: Implement vector RAG learning, adaptive blacklist suggestions, and scraper query tuning based on user status updates and comments.
- **Plans**:
  - `05-01-PLAN.md`: Feedback extraction from user comments & negative/positive status vectors.
  - `05-02-PLAN.md`: Adaptive search keyword generator, automatic blacklist rule suggestions, and RAG score re-weighting loop.
  - `05-03-PLAN.md`: End-to-end integration testing and full workflow validation.

## Phase 6: Containerization, Kubernetes & DevOps Automation (Complete; verification gaps closed 2026-10-28, live Docker check pending)

- **Goal**: Package Jobot into production Docker containers, provide multi-container Docker Compose with Ollama, author Kubernetes manifests, and supply build/run/deploy automation scripts.
- **Plans**:
  - `06-01-PLAN.md`: Production `Dockerfile` with Playwright browser installation and `.dockerignore`. — ✓ Complete
  - `06-02-PLAN.md`: `docker-compose.yml` linking Jobot with Ollama, GPU support, and named persistent volumes. — ✓ Complete
  - `06-03-PLAN.md`: Kubernetes manifests (`k8s/` Deployment, Service, PVC, ConfigMap, Ingress for Jobot & Ollama). — ✓ Complete
  - `06-04-PLAN.md`: Automation scripts (`scripts/` build, run, deploy, and model pull for Bash and PowerShell). — ✓ Complete

## Phase 7: Profile Management, LinkedIn Profile Analysis & Skill-Driven Scraping (Complete, verified with human-needed browser/live LinkedIn check)

- **Goal**: Implement a dedicated profile editing tab, LinkedIn profile analysis & sync, and dynamic skill-driven scraper query generation.
- **Plans**:
  - `07-01-PLAN.md`: Profile Data Model Enhancements & ChromaDB Vector Sync. — ✓ Complete
  - `07-02-PLAN.md`: LinkedIn Profile Ingestion & AI Analyzer. — ✓ Complete
  - `07-03-PLAN.md`: Dynamic Skill-Driven Scraping Query Builder. — ✓ Complete
  - `07-04-PLAN.md`: Profile Editing Web UI Tab & Partials. — ✓ Complete
  - `07-05-PLAN.md`: Verification & E2E Integration Suite. — ✓ Complete

## Phase 8: AI Cover Letter Generator & Resume Tailoring Engine (Complete; no independent verification report, not re-audited)

- **Goal**: Build an ATS-optimized, tailored application generator producing customized cover letters and targeted CV bullet points per job match.
- **Plans**:
  - `08-01-PLAN.md`: Application Artifact Data Model & Prompt Architecture. — ✓ Complete
  - `08-02-PLAN.md`: REST API & Application Generation Pipeline. — ✓ Complete
  - `08-03-PLAN.md`: Job Inspector UI Cover Letter & Tailoring Tabs. — ✓ Complete
  - `08-04-PLAN.md`: Verification & Integration Test Suite. — ✓ Complete

## Phase 9: AI-Assisted Intelligent Web Scraping Engine (Complete, verified with human-needed live extraction check)

- **Goal**: Implement AI-assisted web scraping with dynamic DOM/HTML extraction, intelligent Boolean search query generation, and spam filtering.
- **Plans**:
  - `09-01-PLAN.md`: AI DOM & HTML Structured Job Extractor. — ✓ Complete
  - `09-02-PLAN.md`: AI Query Strategist & Platform-Specific Search Optimizer. — ✓ Complete
  - `09-03-PLAN.md`: Hybrid Scraper Pipeline Integration with Playwright & JobSpy. — ✓ Complete
  - `09-04-PLAN.md`: UI Controls, Verification & Documentation Sync. — ✓ Complete

## Milestone 2: Production Real-Data Queue Engine & Live Integrations

### Phase 10: Persistent SQLite Task Queue & Continuous Scraping Worker (Complete, verified; gaps closed 2026-10-28)

- **Goal**: Implement a persistent SQLite-backed task queue and async background worker loop for continuous, resilient job discovery and batch AI evaluation.
- **Plans**:
  - `10-01-PLAN.md`: `ScrapeTask` SQLModel queue schema, state machine transitions, and persistent task storage. — ✓ Complete
  - `10-02-PLAN.md`: Async queue worker daemon with rate-limiting, job dispatching, and failure tracking. — ✓ Complete
  - `10-03-PLAN.md`: Real-time queue monitoring REST API and HTMX **AI Queue View & Control Center** tab. — ✓ Complete
  - `10-04-PLAN.md`: Verification & integration tests for queue reliability and continuous scraping. — ✓ Complete

### Phase 11: Authenticated LinkedIn Session Manager & Profile Analysis (Complete, verified with human-needed live LinkedIn check)

- **Goal**: Build automated cookie session persistence (`li_at`), `linkedin-api` Voyager REST API, and Joeyism `linkedin_scraper` integration for rich LinkedIn profile synchronization.
- **Plans**:
  - `11-01-PLAN.md`: `li_at` cookie injection and multi-stage profile sync handler (`linkedin-api` REST + Joeyism `linkedin_scraper` + Playwright). — ✓ Complete
  - `11-02-PLAN.md`: Authenticated profile DOM extractor for full employment history, skills, and education. — ✓ Complete
  - `11-03-PLAN.md`: Profile UI card with `li_at` cookie sync and explanatory notice in the Profile tab. — ✓ Complete
  - `11-04-PLAN.md`: Verification & live session handling tests. — ✓ Complete

### Phase 12: Strict Real-Data Enforcement, Scoring Calibration & Actionable Error UI (Complete, verified; gaps closed 2026-10-28)

- **Goal**: Eliminate all synthetic mock fallbacks across runtime scrapers, analyzers, and AI evaluators, replacing them with normalized profile-skill-based fit scoring, parameter calibration sliders, and actionable UI error banners.
- **Plans**:
  - `12-01-PLAN.md`: Audit and remove synthetic placeholder fallbacks in `StepStoneScraper`, `AIScraperExtractor`, `LinkedInProfileAnalyzer`, and AI evaluators in production execution. — ✓ Complete
  - `12-02-PLAN.md`: Actionable UI alert banners, toast notification system, and interactive parameter scoring calibration sliders in Settings. — ✓ Complete
  - `12-03-PLAN.md`: Diagnostics health endpoint, auto-purging of non-matching jobs (0% fit score), and test suite verifying real execution and parameter calibration. — ✓ Complete

## Milestone 3: Secure Remote Access & Phone SSH Tunnel (Active)

### Phase 13: Secure Phone Access Through an SSH Tunnel (Complete; no independent verification report, not re-audited)

- **Goal**: Allow Jobot to be used from a phone or secondary device over a secure SSH tunnel while the app and its local AI stack remain on the main machine.
- **Plans**:
  - `13-01-PLAN.md`: Tunnel design, SSH key setup, and secure remote access architecture. — ✓ Complete
  - `13-02-PLAN.md`: Browser/mobile access flow, forwarding rules, and user guidance for phone usage. — ✓ Complete
  - `13-03-PLAN.md`: Security verification, operational checklist, and support docs. — ✓ Complete
  - `13-04-PLAN.md`: Tailscale SSH Settings panel, bounded runtime status detection, persisted connection preferences, and input validation. — ✓ Complete

## Milestone 4: Experience, Education & Project Signal Scoring (Complete)

### Phase 14: Experience, Education & Project Signal Scoring (Complete, verified; gaps closed 2026-10-28 with one accepted deviation: only history/education/project weights drive the stored score)

- **Goal**: Use the candidate’s historical skills, education, and prior project experience as first-class signals in the fit score so the model reflects their real profile quality, not only the latest CV keywords.
- **Plans**:
  - `14-01-PLAN.md`: Profile signal model review and scoring design for skills, education, experience, and project evidence. — ✓ Complete
  - `14-02-PLAN.md`: Data model and UI updates to display, sort, and edit parsed project and education sections. — ✓ Complete
  - `14-03-PLAN.md`: Scoring pipeline updates, calibration settings, and verification of profile-aware filtering. — ✓ Complete

## Milestone 5: Account Login & Per-User Encrypted Data (Complete)

### Phase 15: Secure User Accounts and Encrypted Personal Data (Complete; verification gaps closed 2026-10-28)

- **Goal**: Add account login, user isolation, and encrypted storage for sensitive profile and AI data while preserving Jobot’s local-first, open-source architecture.
- **Plans**:
  - `15-01-PLAN.md`: Authentication model, user table design, password hashing, and session lifecycle. — ✓ Complete
  - `15-02-PLAN.md`: Encryption and key management for CV data, credentials, LinkedIn cookies, and per-user data storage. — ✓ Complete
  - `15-03-PLAN.md`: UI login flow, account isolation, and verification of multi-user security boundaries. — ✓ Complete

## Milestone 6: Concurrent Background Scraping & Parallel AI Scoring Engine (Complete)

### Phase 16: Concurrent Background Scraping & Parallel AI Scoring Engine (Complete)

- **Goal**: Implement decoupled asynchronous worker pools and bounded semaphores to execute multi-source scraping queries and batch AI job evaluations simultaneously in parallel without blocking or resource exhaustion.
- **Plans**:
  - `16-01-PLAN.md`: Decoupled dual-worker loop architecture with task-type claiming and bounded `asyncio.Semaphore` pools. — ✓ Complete
  - `16-02-PLAN.md`: Multi-source concurrent scraping (JobSpy + StepStone parallel dispatch) and parallel batch AI job scoring pipeline. — ✓ Complete
  - `16-03-PLAN.md`: Concurrency configuration settings, UI sliders in Settings, live parallel activity metrics in AI Queue View, and verification test suite. — ✓ Complete

## v7.0 Milestone 7: Multi-Provider & Hybrid Local/Cloud AI Routing Engine (Active)

### Phase 17: Multi-Provider & Hybrid Local/Cloud AI Routing Engine (Complete)

**Goal:** Decouple AI execution into task-based stages (Scraping, Scoring, Applying) with an encrypted multi-provider credential vault (Ollama, OpenAI, Anthropic, Gemini, Groq, DeepSeek, OpenRouter), local-pinned embeddings, explicit failure transparency, and 1-click cost-saving presets.
**Requirements:** REQ-HYB-01, REQ-HYB-02, REQ-HYB-03, REQ-HYB-04, REQ-HYB-05, REQ-HYB-06
- **Status**: Complete; fresh verification passed 31/31 truths, all 3 UAT checks passed, security reports zero open threats, and fresh code review is clean. Latest isolated suite: 673 passed, 4 existing warnings on Python 3.14.7. Python 3.10 was not available; see `17-VERIFICATION.md` and `17-REVIEW.md` for limits.
- **Plans**:
- [x] 17-01-PLAN.md
- [x] 17-02-PLAN.md
- [x] 17-03-PLAN.md
- [x] 17-04-PLAN.md
- [x] 17-05-PLAN.md
  - `17-01-PLAN.md`: Multi-Provider Adapters & Unified Client Factory (Anthropic, Gemini, Groq, DeepSeek, OpenRouter + task-based `get_ai_client`).
  - `17-02-PLAN.md`: Multi-Provider Credential Vault, DB Settings & Test API Endpoints.
  - `17-03-PLAN.md`: Pipeline Dispatch Integration (Scraping, Scoring, Applying) & Local Embeddings Pinning.
  - `17-04-PLAN.md`: Multi-Provider Settings UI, One-Click Presets & Actionable Error UI.
  - `17-05-PLAN.md`: Verification & End-to-End Test Suite.

### Phase 18: Live Model Discovery for Cloud Providers & Ollama

**Goal:** Fetch the available model list live from each configured provider's API (Gemini, OpenAI, Anthropic, Groq, DeepSeek, OpenRouter, custom OpenAI-compatible) and from Ollama (local or remote host), and offer them as validated selections in Settings, so stale or wrong model IDs (such as the Gemini 404 and the missing Ollama model) are caught before a task runs.
**Requirements:** REQ-HYB-07 (model discovery), REQ-HYB-08 (configured-model validation)
- **Status**: 5/5 plans implemented; 670 tests pass (mocked). Canonical verification is human_needed (live provider/Ollama and browser checks pending); see `18-VERIFICATION.md`. Independent review not run.
- **Plans**:
  - `18-01-PLAN.md` (wave 1): Per-provider `list_models()` adapters with pagination/filtering/bounds; Gemini tracer through `POST /api/settings/provider-models`.
  - `18-02-PLAN.md` (wave 2): `ModelCatalog` owner-scoped TTL cache, refresh cooldown, configured-model validator.
  - `18-03-PLAN.md` (wave 3): Settings API integration: cached discovery, provider-test model validation, Ollama chat-model + `nomic-embed-text` checks with pull hints, cache-only save warnings.
  - `18-04-PLAN.md` (wave 4): Settings UI: Refresh models, datalist on provider/task model inputs, accessible "Not in provider list" warnings.
  - `18-05-PLAN.md` (wave 5): Incident regressions, owner-isolation/leak tests, full-suite run, USER_MANUAL/CONTRIBUTING sync.
