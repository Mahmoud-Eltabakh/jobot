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

## Phase 5: Feedback Loop & Search Refinement Engine
- **Goal**: Implement vector RAG learning, adaptive blacklist suggestions, and scraper query tuning based on user status updates and comments.
- **Plans**:
  - `05-01-PLAN.md`: Feedback extraction from user comments & negative/positive status vectors.
  - `05-02-PLAN.md`: Adaptive search keyword generator, automatic blacklist rule suggestions, and RAG score re-weighting loop.
  - `05-03-PLAN.md`: End-to-end integration testing and full workflow validation.

## Phase 6: Containerization, Kubernetes & DevOps Automation (Complete)
- **Goal**: Package Jobot into production Docker containers, provide multi-container Docker Compose with Ollama, author Kubernetes manifests, and supply build/run/deploy automation scripts.
- **Plans**:
  - `06-01-PLAN.md`: Production `Dockerfile` with Playwright browser installation and `.dockerignore`. — ✓ Complete
  - `06-02-PLAN.md`: `docker-compose.yml` linking Jobot with Ollama, GPU support, and named persistent volumes. — ✓ Complete
  - `06-03-PLAN.md`: Kubernetes manifests (`k8s/` Deployment, Service, PVC, ConfigMap, Ingress for Jobot & Ollama). — ✓ Complete
  - `06-04-PLAN.md`: Automation scripts (`scripts/` build, run, deploy, and model pull for Bash and PowerShell). — ✓ Complete

## Phase 7: Profile Management, LinkedIn Profile Analysis & Skill-Driven Scraping (Complete)
- **Goal**: Implement a dedicated profile editing tab, LinkedIn profile analysis & sync, and dynamic skill-driven scraper query generation.
- **Plans**:
  - `07-01-PLAN.md`: Profile Data Model Enhancements & ChromaDB Vector Sync. — ✓ Complete
  - `07-02-PLAN.md`: LinkedIn Profile Ingestion & AI Analyzer. — ✓ Complete
  - `07-03-PLAN.md`: Dynamic Skill-Driven Scraping Query Builder. — ✓ Complete
  - `07-04-PLAN.md`: Profile Editing Web UI Tab & Partials. — ✓ Complete
  - `07-05-PLAN.md`: Verification & E2E Integration Suite. — ✓ Complete

## Phase 8: AI Cover Letter Generator & Resume Tailoring Engine (Complete)
- **Goal**: Build an ATS-optimized, tailored application generator producing customized cover letters and targeted CV bullet points per job match.
- **Plans**:
  - `08-01-PLAN.md`: Application Artifact Data Model & Prompt Architecture. — ✓ Complete
  - `08-02-PLAN.md`: REST API & Application Generation Pipeline. — ✓ Complete
  - `08-03-PLAN.md`: Job Inspector UI Cover Letter & Tailoring Tabs. — ✓ Complete
  - `08-04-PLAN.md`: Verification & Integration Test Suite. — ✓ Complete

## Phase 9: AI-Assisted Intelligent Web Scraping Engine (Complete)
- **Goal**: Implement AI-assisted web scraping with dynamic DOM/HTML extraction, intelligent Boolean search query generation, and spam filtering.
- **Plans**:
  - `09-01-PLAN.md`: AI DOM & HTML Structured Job Extractor. — ✓ Complete
  - `09-02-PLAN.md`: AI Query Strategist & Platform-Specific Search Optimizer. — ✓ Complete
  - `09-03-PLAN.md`: Hybrid Scraper Pipeline Integration with Playwright & JobSpy. — ✓ Complete
  - `09-04-PLAN.md`: UI Controls, Verification & Documentation Sync. — ✓ Complete

## Milestone 2: Production Real-Data Queue Engine & Live Integrations

### Phase 10: Persistent SQLite Task Queue & Continuous Scraping Worker
- **Goal**: Implement a persistent SQLite-backed task queue and async background worker loop for continuous, resilient job discovery and batch AI evaluation.
- **Plans**:
  - `10-01-PLAN.md`: `ScrapeTask` SQLModel queue schema, state machine transitions, and persistent task storage.
  - `10-02-PLAN.md`: Async queue worker daemon with rate-limiting, job dispatching, and failure tracking.
  - `10-03-PLAN.md`: Real-time queue monitoring REST API and topbar UI status widget.
  - `10-04-PLAN.md`: Verification & integration tests for queue reliability and continuous scraping.

### Phase 11: Authenticated LinkedIn Login & Session Manager
- **Goal**: Build automated Playwright credential login and cookie session persistence for live, rich LinkedIn profile synchronization.
- **Plans**:
  - `11-01-PLAN.md`: Playwright login handler with credential support, 2FA prompt detection, and session cookie capture.
  - `11-02-PLAN.md`: Authenticated profile DOM extractor for full employment history, skills, and endorsements.
  - `11-03-PLAN.md`: UI login modal / credential form on the Profile tab with live status feedback.
  - `11-04-PLAN.md`: Verification & live session handling tests.

### Phase 12: Strict Real-Data Enforcement & Actionable Error UI
- **Goal**: Eliminate all synthetic mock fallbacks across runtime scrapers, analyzers, and AI evaluators, replacing them with explicit actionable error alerts in the web UI.
- **Plans**:
  - `12-01-PLAN.md`: Audit and remove synthetic placeholder fallbacks in `StepStoneScraper`, `AIScraperExtractor`, `LinkedInProfileAnalyzer`, and AI evaluators in production execution.
  - `12-02-PLAN.md`: Actionable UI alert banners and notification toast system for offline Ollama or blocked scraper targets.
  - `12-03-PLAN.md`: Diagnostics health endpoint and test suite verifying zero-mock real execution.
