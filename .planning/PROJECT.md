# Jobot - AI Job Search & Tracking Agent

## What This Is

Jobot is an intelligent, self-hosted job search aggregator and application tracker built with a pure Python modern web stack. It leverages `python-jobspy` for robust extraction across LinkedIn and Google Jobs, complemented by a dedicated Playwright scraper for StepStone. It parses candidate CVs (PDF) and LinkedIn profiles, using a flexible AI & RAG engine supporting **Local Ollama** or **Cloud/Custom AI APIs** (OpenAI, Anthropic, Groq, etc.) with ChromaDB vector embeddings to score fit against candidate profiles. A sleek, easy-to-use FastAPI + HTMX/Tailwind web dashboard enables users to inspect jobs, track status through every application stage, record position notes, configure AI providers with custom keys, and leverage an adaptive feedback loop to automatically refine future search queries and semantic scoring.

## Core Value

Help job seekers find relevant opportunities and move confidently from discovery through application tracking in a reliable, privacy-respecting product.

## Business Context

- **Customer**: Individual job seekers are the provisional first customer segment.
- **Revenue model**: Start with a private beta without billing; evaluate subscription pricing after validating retention and AI operating costs.
- **Success metric**: Users can reach a relevant shortlist and keep their applications current; quantitative activation and retention targets remain to be set from beta evidence.
- **Strategy notes**: No separate business strategy document has been approved.

## Requirements

### Validated

- [x] **Multi-Source Scraping**: Integration of `python-jobspy` for LinkedIn and Google Jobs, plus a dedicated Playwright scraper for StepStone. (Phase 3 & Phase 9)
- [x] **Background Scheduling & Worker**: Periodic background job extraction and persistent SQLite async task queue (`ScrapeTask`). (Phase 3 & Phase 10)
- [x] **Profile & CV Ingestion**: Joined CV (PDF/DOCX) and LinkedIn profile ingestion (`li_at` cookie + `linkedin-api` + Joeyism `linkedin_scraper`) with RAG vector sync. (Phase 2, Phase 7, Phase 11)
- [x] **Pluggable AI & Vector RAG Engine**: Dual AI provider backend supporting Local Ollama (`llama3.1`, `qwen2.5`, `job-searcher-qwen3`) or Cloud APIs (OpenAI, Groq) + ChromaDB vector embeddings. (Phase 2 & Phase 12)
- [x] **Modern Web Dashboard**: Pure Python web frontend (FastAPI + HTMX + Tailwind CSS) with 8-stage Kanban board, sortable Data Table, Job Inspector drawer, Settings panel, Profile manager, and **AI Queue Control Center**. (Phase 4, Phase 7, Phase 10)
- [x] **Comprehensive Status Tracking**: Lifecycle statuses: `seen`, `applied`, `waiting for respond`, `1. interview`, `2. interview`, `3. interview`, `not a good fit`, `rejected`. (Phase 4)
- [x] **Feedback Loop & Continuous Learning**: User feedback notes and status adjustments dynamically tune vector embeddings weights, prompt few-shots, and search query keywords. (Phase 5)
- [x] **Configurable Search & AI Settings**: Custom search titles, target locations, salary ranges, blacklist keywords, parameter scoring weights calibration sliders, and UI-based AI provider selection. (Phase 4 & Phase 12)
- [x] **Containerization & Orchestration**: Production `Dockerfile`, `docker-compose.yml` with Host Ollama GPU/NPU support, and Kubernetes manifests (`k8s/`). (Phase 6)
- [x] **Automation Scripts**: Cross-platform automation scripts (`manage.ps1` and `manage.sh`) for building images, running containers, model preloading, and Kubernetes deployments. (Phase 6)
- [x] **Account Login & Per-User Encrypted Data**: Secure registration/login, revocable sessions, account-scoped data and settings, and user-bound authenticated encryption for sensitive local data. (Milestone 5)
- [x] **Concurrent Background Scraping & Parallel AI Scoring**: Separate bounded worker pools for scraping and evaluation with configurable concurrency. (Milestone 6)
- [x] **Multi-Provider Hybrid AI Routing**: Owner-encrypted provider credentials and independent Scraping, Scoring, Applying, and local-only Embeddings routes with explicit failure handling. (v7.0 Phase 17)
- [x] **Live Model Discovery & Validation**: Owner-scoped provider listings, cache-backed suggestions, non-blocking model warnings, and Ollama model-presence hints. (v7.0 Phase 18)

### Active

- [ ] Deliver a hosted private beta for individual job seekers, subject to validation during v8.0 discovery.
- [ ] Protect each user's profile, job-search data, and generated materials with strict account isolation and clear privacy controls.
- [ ] Offer managed AI with explicit usage limits and provider/data-processing disclosures for the initial beta.
- [ ] Establish production operations, including tested backups and restores, monitoring, incident handling, and an availability target.
- [ ] Preserve the existing self-hosted workflow during the beta unless architecture research identifies a concrete incompatibility.

### Out of Scope

- Auto-applying / submitting forms directly to employer portals (avoids account bans, captcha failures, and accidental bad submissions).
- Public paid launch and billing implementation — defer until beta demand, retention, and operating costs are understood.
- Organization/team workspaces, career-coach client management, and employer/recruiter workflows — not part of the provisional individual-user beta.
- BYO AI keys and multiple selectable hosted AI plans — defer until the managed-AI cost and privacy model is validated.
- Compliance certification or a data-residency promise — no target market or certification has been selected; applicable privacy obligations still need to be identified.

## Context

- Target user wants a streamlined, flexible personal job search copilot.
- The app stays on the main workstation while a phone or companion device accesses it through a secure SSH tunnel, keeping local AI/DB services private and not public-facing.
- Using `python-jobspy` dramatically reduces scraper maintenance for major platforms (LinkedIn, Google Jobs).
- StepStone uses a dedicated Playwright crawler with anti-bot headers and European layout parsing.
- User can freely toggle between local Ollama (for offline privacy and 0 cost) and cloud APIs (for maximum reasoning performance on lower-spec hardware).
- v7.0 completed multi-provider routing and live model discovery. Production SaaS hosting, tenant boundaries, billing, privacy/compliance, service-level objectives, and launch metrics have not been selected.

## Current Milestone: v8.0 Production SaaS Foundation

**Goal:** Prepare a secure, reliable hosted beta that helps individual job seekers discover relevant jobs, generate application materials, and track their search without compromising personal data.

**Target features:**
- A hosted onboarding and personal-workspace journey for individual job seekers.
- Account-isolated profiles, job data, AI outputs, and clear data export/deletion controls.
- Managed AI with explicit per-user usage limits and provider/data-processing disclosures.
- Production deployment, observability, backups and restore testing, incident handling, and a measurable availability objective.
- A private-beta release path that preserves the current self-hosted workflow where practical.

**Working assumptions to validate:** Individual job seekers are the initial customer; the first hosted release is a private beta without billing; team workspaces, public paid launch, and BYO keys are deferred. Hosting provider, initial geography, privacy/compliance obligations, AI vendor, numeric SLO, support model, and the degree of self-hosted compatibility remain open pending research and requirements review.

## Constraints

- **Language Policy**: **Python-First / Pure Python**: Everything (backend, scrapers, data models, AI/RAG engine, web UI rendering, background workers) must be implemented in Python unless a specific sub-task strictly demands another language. Zero Node.js/npm dependencies for the web stack (HTMX + Tailwind CSS via CDN/standalone).
- **Strict Real-Data Policy (Zero Synthetic Mocks in Runtime)**: No fake placeholder responses or synthetic fallback jobs in production/runtime. All scrapers and AI evaluations must execute against live services. When a live service is unreachable or blocked, Jobot raises explicit actionable error diagnostics and UI status alerts instead of masking failures with mock data.
- **Queue-Driven Execution**: Scraping and AI scoring jobs run through a persistent SQLite async worker queue with state management (`pending`, `in_progress`, `completed`, `failed`) ensuring continuous background execution without dropping tasks.
- **Execution & Development Environment**: Container-first workflow: Development runs inside Docker containers with source bind-mounts and hot-reloading (`docker-compose.dev.yml`). Production runs via `docker-compose.yml` or Kubernetes.
- **SaaS Hosting Decision**: No cloud host, tenant architecture, billing provider, or production service-level objective is approved yet; resolve these before implementing the SaaS release path.
- **Tech Stack**: Pure Python backend and web UI (FastAPI + Jinja2 + HTMX + Tailwind CSS) + SQLite / ChromaDB.
- **AI Backend**: Pluggable provider interface supporting Local Ollama (`ollama-python`) and OpenAI-compatible client (`openai` / `httpx`) with runtime settings persisted in SQLite and fully editable in the UI.
- **Scraping Engine**: Python (`python-jobspy` + `playwright-python` for StepStone and authenticated LinkedIn profile ingestion).
- **Comment Coverage**: New and substantially modified source modules target approximately 20–30% meaningful comment coverage, including useful docstrings and explanations of non-obvious behavior. Trivial narration and unrelated comment-only churn are prohibited.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python-First Architecture | Unified ecosystem across scrapers, AI pipeline, database models, and web UI for maintainability and seamless execution | ✓ Validated |
| Docker-First Development | Ensures consistent Playwright browser environments, system libraries, and local Ollama networking across all host operating systems | ✓ Validated |
| Persistent DB-backed AI Settings | AI parameters (provider, models, API keys, endpoints) are initialized on startup and editable in the UI without server restarts | ✓ Validated |
| Pluggable AI Provider (Ollama vs API Key) | Users on high-end PCs run Ollama for 100% offline privacy; users on laptops/lower-spec hardware can plug in OpenAI/Groq API keys | ✓ Validated |
| `python-jobspy` for LinkedIn & Google Jobs | Battle-tested open-source scraper library handling rate limits, headers, and DOM changes | ✓ Validated |
| Dedicated Playwright for StepStone | Clean headless browser crawler tailored to StepStone's layout and pagination | ✓ Validated |
| Pure Python Web Stack (FastAPI + HTMX) | Snappy reactive UI without Node.js/build overhead, unified Python backend | ✓ Validated |
| ChromaDB Embedded Vector Store | Zero external daemon needed, in-process SQLite storage for CV and feedback vectors | ✓ Validated |
| Status & Notes-driven Vector Tuning | Uses user feedback comments and application outcomes to refine semantic scoring | ✓ Validated |
| Containerization & K8s Manifests | Enables single-command local spin-up via Docker Compose and scalable private cluster deployment via Kubernetes | ✓ Validated |
| Cross-Platform Automation Scripts | Provides seamless build, run, model pull, and deployment automation for Linux/macOS (bash) and Windows (PowerShell) | ✓ Validated |
| Persistent SQLite Task Queue (`ScrapeTask`) | Atomic task claiming worker loop ensures resilient, non-blocking background job discovery and batch scoring | ✓ Validated (Phase 10) |
| Multi-Stage LinkedIn Profile Ingestion | Combines `linkedin-api` Voyager REST API with Joeyism `linkedin_scraper` and Playwright for rich profile extraction | ✓ Validated (Phase 11) |
| Joined CV + LinkedIn Data Model | Merges skills, education, and career experience from both CV uploads and LinkedIn syncs into a single combined profile | ✓ Validated (Phase 11 & 12) |
| Normalized Skill-Based Scoring & Calibration Sliders | Normalizes sub-factor scores to 0-100% with instant disqualification for 0 skill match, plus fine-tuning UI sliders in Settings | ✓ Validated (Phase 12) |
| Open-Source Community Best Practices | Added MIT License, Code of Conduct, Security Policy, Issue Templates, and PR checklist | ✓ Validated (Phase 12) |
| Secure SSH Tunnel Access for Mobile Devices | Lets the app stay on the main workstation while a phone connects through a secure SSH tunnel, avoiding public exposure and preserving the private local AI stack | Validated (Milestone 3) |
| Tailscale SSH Settings Without Privileged Web Controls | Displays status and validated connection preferences while leaving network administration in the host operating system | ✓ Validated (Phase 13) |
| Experience, Education & Project Signal Scoring | Uses a candidate's historical skills, educational background, and project work as explicit ranking signals so the fit score reflects the true professional profile | ✓ Validated (Milestone 4) |
| Meaningful Comment Coverage | Targets 20–30% explanatory comments and docstrings in changed modules while rejecting syntax narration and mechanical padding | Active project convention |
| User-Scoped Authenticated Encryption | Binds encrypted profile and provider secrets to the owning account, supports key IDs and rotation, and prevents stored secrets from being reflected into HTML | ✓ Validated (Phase 15) |
| Decoupled Dual-Worker Concurrency | Separates network I/O scraping from compute-intensive LLM evaluation into concurrent worker pools with bounded semaphores to maximize throughput while avoiding Ollama OOM and scraper IP blocks | ✓ Validated (Milestone 6) |
| Owner-Scoped Hybrid AI Routing | Separate encrypted provider credentials and independent pipeline-stage routing while keeping embeddings on owner-local Ollama and provider failures explicit | ✓ Validated (v7.0 Phase 17) |
| Live Model Discovery Is Advisory | Cache provider model lists per owner and configuration; show warnings without rewriting selected models or implying generation entitlement | ✓ Validated (v7.0 Phase 18) |
| Hosted SaaS Starts with Individual Workspaces | Keep personal data isolated by account and defer team permissions until user demand validates the added access-control surface | — Provisional for v8.0 |
| Private Beta Before Monetization | Validate retained use and AI unit costs before committing to billing, subscription tiers, or public launch | — Provisional for v8.0 |


## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-28 after starting v8.0 SaaS milestone discovery with provisional assumptions.*
