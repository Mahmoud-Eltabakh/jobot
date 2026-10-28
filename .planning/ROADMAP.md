# Jobot Execution Roadmap

## Milestones

- **Milestones 1-6** — Phases 1-16 completed; original phase details are preserved in the legacy phase archive.
- **v7.0 Multi-Provider & Hybrid Local/Cloud AI Routing Engine** — Phases 17-18 shipped 2026-10-28; [roadmap archive](milestones/v7.0-ROADMAP.md), [requirements archive](milestones/v7.0-REQUIREMENTS.md), [audit](milestones/v7.0-MILESTONE-AUDIT.md).
- **v8.0 Production SaaS Foundation** — Completed private-beta readiness milestone covering product contract, security invariants, persistence foundation, workflow design, and launch gates.
- **v9.0 Official LinkedIn OpenID Connect & Developer Portal Integration** — Active milestone replacing legacy Playwright scraping with official OIDC authentication from the LinkedIn Developer Product Catalog.

## Active Milestone: v9.0 Official LinkedIn OpenID Connect & Developer Portal Integration

The v9.0 milestone integrates the official "Sign In with LinkedIn using OpenID Connect" (OIDC) product from the LinkedIn Developer Product Catalog (https://developer.linkedin.com/product-catalog), delivering 1-click SSO on login and registration, verified candidate profile account linking, and decommissioning brittle Playwright password submission.

### Phase 24: LinkedIn Developer Portal OpenID Connect & OAuth2 Redesign (Superseded)

- Goal: Replace legacy Playwright headless login and manual li_at cookie scraping with official LinkedIn OpenID Connect.
- Key outputs: `LinkedInOIDCClient`, `/auth/linkedin/login`, `/auth/linkedin/callback`, SSO buttons on login/register, connected profile status badge in Profile tab, AES-GCM encrypted token persistence, and 100% offline mocked test suite.
- Exit criteria: Automated tests verify OIDC login, registration, and profile linkage with zero unmocked network sockets.
- Status: Superseded by the manual LinkedIn PDF-import direction. Do not execute `24-01-PLAN.md`; it remains as historical planning context only.

### Phase 25: Professional Page Architecture and Route Separation

**Goal:** Deliver direct, refresh-safe authenticated workspace pages while preserving the existing HTMX fragment, mutation, API, tenant-isolation, and popup contracts.
**Requirements**: TBD
**Depends on:** None
**Plans:** 3 plans

Plans:
- [ ] 25-01-PLAN.md — Establish the dashboard shell, canonical navigation, and root compatibility redirect.
- [ ] 25-02-PLAN.md — Add canonical board and table pages while retaining filter and inspector workflows.
- [ ] 25-03-PLAN.md — Add queue, profile, and settings pages with route and browser regression coverage.

## Milestone Archive: v8.0 Production SaaS Foundation (Complete)

The v8.0 milestone resolved key product and operational questions before a controlled private-beta launch path was documented and closed.

### Phase 19: Beta Contract and Policy Decisions (Complete)

- Goal: confirm who the beta serves, which sources are allowed, how AI usage is governed, and what the operational policy envelope is.
- Key outputs: target customer and geography, source-access terms, data-processing disclosures, own/support model, beta scope, and non-billing or pricing decision.
- Exit criteria: policy decisions recorded or explicitly deferred with owners and risks.
- Status: executed via Phase 19 context, plan, and summary artifacts; private-beta contract documented.

### Phase 20: Tenant, Privacy, and Hosted Security Invariants (Complete)

- Goal: prove account isolation and data protection before any hosted production workflow is built.
- Key outputs: ownership inventory, fail-closed auth checks, cross-account security tests, sensitive-data flow map, and key-management design.
- Exit criteria: tenant isolation is validated by regression tests and privacy controls are mapped to every write path.
- Status: executed via the phase 20 context, plan, and summary artifacts; the tenant-isolation foundation is locked.

### Phase 21: Hosted Persistence and Runtime Foundation (Complete)

- Goal: establish durable hosted state and the runtime roles required for a private beta.
- Key outputs: selected database and migration strategy, hosted/local storage adapters, queue ownership, migration/rollback plan, and operational service boundaries.
- Exit criteria: database and runtime design is approved with tested backup and recovery steps.
- Status: executed via the phase 21 context, plan, and summary artifacts; the hosted runtime contract is documented.

### Phase 22: Hosted Personal Workflow and Managed-AI Controls (Complete)

- Goal: turn the validated security and persistence foundation into the beta user experience.
- Key outputs: hosted onboarding, job workflow, AI usage UX, provider disclosures, export/delete controls, and cost guardrails.
- Exit criteria: the hosted beta workflow works with rate limits and clear user-facing error states.
- Status: executed via the phase 22 context, plan, and summary artifacts; the private-beta workflow is defined.

### Phase 23: Production Gates and Private-Beta Readiness (Complete)

- Goal: verify the service is operationally safe to invite users into a private beta.
- Key outputs: observability, backup/restore drills, deletion/retention verification, support runbooks, load and cost tests, incident response plan, and release-go decision gate.
- Exit criteria: the beta is ready for controlled invitation, not general public launch.
- Status: executed via the phase 23 context, plan, and summary artifacts; the readiness gate and launch contract are complete.

## Phases

<details>
<summary>Completed historical phases 1-16 (Milestones 1-6)</summary>

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

</details>
