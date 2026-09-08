# Jobot - AI Job Search & Tracking Agent

## What This Is

Jobot is an intelligent, self-hosted job search aggregator and application tracker built with a pure Python modern web stack. It leverages `python-jobspy` for robust extraction across LinkedIn and Google Jobs, complemented by a dedicated Playwright scraper for StepStone. It parses candidate CVs (PDF) and LinkedIn profiles, using a flexible AI & RAG engine supporting **Local Ollama** or **Cloud/Custom AI APIs** (OpenAI, Anthropic, Groq, etc.) with ChromaDB vector embeddings to score fit against candidate profiles. A sleek, easy-to-use FastAPI + HTMX/Tailwind web dashboard enables users to inspect jobs, track status through every application stage, record position notes, configure AI providers with custom keys, and leverage an adaptive feedback loop to automatically refine future search queries and semantic scoring.

## Core Value

Continuously discover high-relevance job opportunities across multiple platforms (LinkedIn, Google Jobs, StepStone) and rank them accurately against a candidate's CV using local Ollama AI or external LLM APIs and adaptive Vector RAG learning, managed through a clean, responsive pure Python dashboard.

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

### Active

- [ ] Define the next milestone after authenticated multi-user hardening.

### Out of Scope

- Auto-applying / submitting forms directly to employer portals (avoids account bans, captcha failures, and accidental bad submissions).
- Forcing cloud subscriptions (system runs 100% self-hosted & offline with Ollama by default, while allowing optional API keys).
- Multi-tenant enterprise user management (single-user / personal desktop dashboard focus for v1).

## Context

- Target user wants a streamlined, flexible personal job search copilot.
- The app stays on the main workstation while a phone or companion device accesses it through a secure SSH tunnel, keeping local AI/DB services private and not public-facing.
- Using `python-jobspy` dramatically reduces scraper maintenance for major platforms (LinkedIn, Google Jobs).
- StepStone uses a dedicated Playwright crawler with anti-bot headers and European layout parsing.
- User can freely toggle between local Ollama (for offline privacy and 0 cost) and cloud APIs (for maximum reasoning performance on lower-spec hardware).

## Constraints

- **Language Policy**: **Python-First / Pure Python**: Everything (backend, scrapers, data models, AI/RAG engine, web UI rendering, background workers) must be implemented in Python unless a specific sub-task strictly demands another language. Zero Node.js/npm dependencies for the web stack (HTMX + Tailwind CSS via CDN/standalone).
- **Strict Real-Data Policy (Zero Synthetic Mocks in Runtime)**: No fake placeholder responses or synthetic fallback jobs in production/runtime. All scrapers and AI evaluations must execute against live services. When a live service is unreachable or blocked, Jobot raises explicit actionable error diagnostics and UI status alerts instead of masking failures with mock data.
- **Queue-Driven Execution**: Scraping and AI scoring jobs run through a persistent SQLite async worker queue with state management (`pending`, `in_progress`, `completed`, `failed`) ensuring continuous background execution without dropping tasks.
- **Execution & Development Environment**: Container-first workflow: Development runs inside Docker containers with source bind-mounts and hot-reloading (`docker-compose.dev.yml`). Production runs via `docker-compose.yml` or Kubernetes.
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
*Last updated: 2026-09-08 after adding Tailscale SSH Settings and beginning Milestone 5 account and encrypted-data hardening.*
