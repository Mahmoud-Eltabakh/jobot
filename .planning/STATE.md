# Project State

## Project Reference

See: [.planning/PROJECT.md](.planning/PROJECT.md) (updated 2026-09-08)

**Core value:** Continuously discover high-relevance job opportunities across multiple platforms and rank them accurately against a candidate's CV using local Ollama AI and adaptive Vector RAG learning, managed through a clean and responsive web dashboard.
**Current focus:** Milestone 5 is complete. Jobot now provides authenticated, encrypted, per-user operation across the dashboard, APIs, queue, profile, scoring, and settings layers.

## Phase Status

### Milestone 1: Core Foundation & Feature Suite (Complete)
- [x] **Phase 1: Core Foundation & Data Architecture** — Complete (3 plans: 01-01, 01-02, 01-03)
- [x] **Phase 2: CV Parsing & Pluggable AI Matching Engine (Ollama / Cloud API)** — Complete (3 plans: 02-01, 02-02, 02-03)
- [x] **Phase 3: Multi-Source Scraping Engine, Filter Pipeline & Background Worker** — Complete (5 plans: 03-01, 03-02, 03-03, 03-04, 03-05)
- [x] **Phase 4: Modern Web Dashboard & Job Tracker UI** — Complete (5 plans: 04-01, 04-02, 04-03, 04-04, 04-05)
- [x] **Phase 5: Feedback Loop & Search Refinement Engine** — Complete (3 plans: 05-01, 05-02, 05-03)
- [x] **Phase 6: Containerization, Kubernetes & DevOps Automation** — Complete (4 plans: 06-01, 06-02, 06-03, 06-04)
- [x] **Phase 7: Profile Management, LinkedIn Profile Analysis & Skill-Driven Scraping** — Complete (5 plans: 07-01, 07-02, 07-03, 07-04, 07-05)
- [x] **Phase 8: AI Cover Letter Generator & Resume Tailoring Engine** — Complete (4 plans: 08-01, 08-02, 08-03, 08-04)
- [x] **Phase 9: AI-Assisted Intelligent Web Scraping Engine** — Complete (4 plans: 09-01, 09-02, 09-03, 09-04)

### Milestone 2: Production Real-Data Queue Engine & Live Integrations (Complete)
- [x] **Phase 10: Persistent SQLite Task Queue & Continuous Scraping Worker** — Complete (4 plans: 10-01, 10-02, 10-03, 10-04)
- [x] **Phase 11: Authenticated LinkedIn Session Manager & Profile Analysis** — Complete (4 plans: 11-01, 11-02, 11-03, 11-04)
- [x] **Phase 12: Strict Real-Data Enforcement, Scoring Calibration & Actionable Error UI** — Complete (3 plans: 12-01, 12-02, 12-03)

### Milestone 3: Secure Remote Access & Phone SSH Tunnel (Complete)
- [x] **Phase 13: Secure Phone Access Through an SSH Tunnel** — Complete (4 plans: 13-01, 13-02, 13-03, 13-04)

### Milestone 4: Experience, Education & Project Signal Scoring (Complete)
- [x] **Phase 14: Experience, Education & Project Signal Scoring** — Complete (3 plans: 14-01, 14-02, 14-03)

### Milestone 5: Account Login & Per-User Encrypted Data (Complete)
- [x] **Phase 15: Secure User Accounts and Encrypted Personal Data** — Complete (3 plans: 15-01, 15-02, 15-03)

## Progress Log

- **2026-09-07**: Initialized Jobot project specification, requirements, domain research, roadmap, and configuration.
- **2026-09-07**: Executed Phase 1: Built FastAPI app with `/health` endpoint, SQLModel SQLite schema with WAL concurrency & default settings seeding, embedded ChromaDB vector store, development Docker Compose stack, and 100% passing test suite.
- **2026-09-07**: Executed Phase 2: Built `CVParser` (`pdfplumber` + `pypdf`), `ExtractedProfile` structured extractor, `BaseAIClient` multi-provider client (`OllamaAIClient`, `OpenAICompatibleClient`), `JobEvaluator` with prompt injection defense, and `ProfileEmbedder` ChromaDB vector RAG pipeline with 24 passing tests.
- **2026-09-07**: Executed Phase 3: Built `ScrapedJob` contract, SHA-256 deduplication pipeline, `JobSpyScraper` (LinkedIn/Google), `StepStoneScraper` (Playwright), `JobFilterPipeline` (Title/Keyword blacklist screening), and `APScheduler` background worker with `POST /api/scrapers/run` endpoint (35 passing tests).
- **2026-09-07**: Executed Phase 4: Built pure Python web dashboard with 8-stage Kanban board, sortable Data Table view, live multi-criteria filter toolbar, slide-over Job Inspector drawer with notes editor, and Settings panel with AI Configurator (Ollama vs. Cloud API key test button) and blacklist manager (44 passing tests).
- **2026-09-07**: Executed Phase 5: Implemented feedback vector learning, adaptive blacklist suggester, search query optimizer, and E2E integration test suite.
- **2026-09-08**: Executed Phase 6: Authored production `Dockerfile`, `docker-compose.yml` with Host Ollama GPU/NPU support, Kubernetes manifests (`k8s/`), and PowerShell/Bash automation scripts (`manage.ps1` / `manage.sh`).
- **2026-09-08**: Executed Phase 7: Built Profile tab UI, `ExtractedProfile` ChromaDB vector sync, `LinkedInProfileAnalyzer` with Playwright and `li_at` cookie injection, and `AIQueryStrategist` for dynamic profile skill search query generation.
- **2026-09-08**: Executed Phase 8: Built `ApplicationGenerator` for 1-click tailored cover letters (4 custom tones: Professional, Direct, Enthusiastic, Conversational) and ATS-optimized accomplishment bullet points with Job Inspector UI tabs.
- **2026-09-08**: Executed Phase 9: Built `AIScraperExtractor` for dynamic DOM extraction, AI Query Strategist Boolean search formulation, and spam/promotional ad filtering.
- **2026-09-08**: Executed Phase 10: Built `ScrapeTask` SQLModel queue schema, `TaskQueue` atomic claiming manager, `QueueWorker` continuous async background loop, and real-time HTMX **AI Queue View & Control Center** tab with pause/resume, retry, and clear capabilities.
- **2026-09-08**: Executed Phase 11: Integrated Tom Quirk's `linkedin-api` (Voyager REST API) and Joeyism's `linkedin_scraper` Playwright engine with `li_at` cookie injection for rich candidate profile sync.
- **2026-09-08**: Executed Phase 12: Enforced zero synthetic mock fallbacks, implemented normalized profile-skill-based fit scoring with 0% disqualification for 0 skill match, added UI sliders for parameter scoring weight calibration, auto-purging of non-matching jobs, joined CV + LinkedIn profile merging, and complete open-source documentation suite (MIT License, Code of Conduct, Security Policy, PR/Issue templates). All 85 unit tests passing.
- **2026-09-08**: Executed Phase 13: Documented the secure phone-access architecture through an SSH tunnel, added the cross-platform mobile access flow, and finalized the host-only security checklist and validation steps. The design keeps Jobot, Ollama, SQLite, and the scraping stack on the main machine while treating the phone as a secure client endpoint.
- **2026-09-08**: Completed Phase 13 follow-up 13-04: Added a Tailscale SSH Settings panel with persisted connection preferences, bounded runtime status detection, validated command inputs, and no privileged web controls.
- **2026-09-08**: Began Phase 15 implementation for account login, revocable sessions, user ownership fields, and encrypted-data primitives; full route-level isolation and sensitive-field integration remain active work.
- **2026-09-08**: Established a repository-wide code-quality convention targeting approximately 20–30% meaningful comments and docstrings in new or substantially modified modules, without mechanical narration or unrelated comment-only churn.
- **2026-09-08**: Completed Phase 15: Added first-run registration, login/logout, revocable sessions, user-scoped records and settings, encrypted sensitive profile/provider data, legacy ownership migration, secret non-reflection, and authenticated regression coverage. Full suite: 99 passed.
