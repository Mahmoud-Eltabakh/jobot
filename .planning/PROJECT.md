# Jobot - AI Job Search & Tracking Agent

## What This Is

Jobot is an intelligent, self-hosted job search aggregator and application tracker built with a pure Python modern web stack. It leverages `python-jobspy` for robust extraction across LinkedIn and Google Jobs, complemented by a dedicated Playwright scraper for StepStone. It parses candidate CVs (PDF) and LinkedIn profiles, using a flexible AI & RAG engine supporting **Local Ollama** or **Cloud/Custom AI APIs** (OpenAI, Anthropic, Groq, etc.) with ChromaDB vector embeddings to score fit against candidate profiles. A sleek, easy-to-use FastAPI + HTMX/Tailwind web dashboard enables users to inspect jobs, track status through every application stage, record position notes, configure AI providers with custom keys, and leverage an adaptive feedback loop to automatically refine future search queries and semantic scoring.

## Core Value

Continuously discover high-relevance job opportunities across multiple platforms (LinkedIn, Google Jobs, StepStone) and rank them accurately against a candidate's CV using local Ollama AI or external LLM APIs and adaptive Vector RAG learning, managed through a clean, responsive pure Python dashboard.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **Multi-Source Scraping**: Integration of `python-jobspy` for LinkedIn and Google Jobs, plus a dedicated Playwright scraper for StepStone.
- [ ] **Background Scheduling & Worker**: Periodic cron/interval background job extraction with rate-limiting, deduplication, and manual trigger support.
- [ ] **Profile & CV Ingestion**: Extract skills, experiences, and qualifications from uploaded PDF CVs and LinkedIn profile exports/URLs.
- [ ] **Pluggable AI & Vector RAG Engine**: Dual AI provider backend supporting **Local Ollama** (`llama3.1`, `mistral`, `qwen2.5`) OR **Cloud/Custom APIs** (OpenAI, Anthropic, Groq, OpenAI-compatible endpoints) + ChromaDB vector embeddings for semantic fit scoring (0–100%) and gap analysis.
- [ ] **Modern Web Dashboard**: Pure Python web frontend (FastAPI + HTMX + Tailwind CSS) featuring Kanban board, table view, multi-criteria sorting/filtering toolbar (Fit Score, salary, remote/workplace, source, dates, matched skills), split-pane job inspector, and comprehensive settings panel.
- [ ] **Comprehensive Status Tracking**: Lifecycle statuses: `seen`, `applied`, `not a good fit`, `rejected`, `1. interview`, `2. interview`, `3. interview`, `waiting for respond`.
- [ ] **Feedback Loop & Continuous Learning**: User notes and status adjustments dynamically tune vector embeddings weights, prompt few-shots, and search query keywords.
- [ ] **Configurable Search & AI Settings**: Custom search titles, target locations (Remote/Hybrid/Onsite), salary ranges, blacklist keywords, and UI-based AI provider selection (Ollama vs. API Key with connection testing).
- [ ] **Containerization & Orchestration**: Production `Dockerfile` (with Playwright Chromium runtime), `docker-compose.yml` (Jobot + Ollama with persistent storage), and Kubernetes manifests (`k8s/` Deployments, Services, PVCs, Ingress).
- [ ] **Automation Scripts**: Comprehensive shell & PowerShell scripts for building images, local execution, model preloading, and Kubernetes deployments.

### Out of Scope

- Auto-applying / submitting forms directly to employer portals (avoids account bans, captcha failures, and accidental bad submissions).
- Forcing cloud subscriptions (system runs 100% self-hosted & offline with Ollama by default, while allowing optional API keys).
- Multi-tenant enterprise user management (single-user / personal desktop dashboard focus for v1).

## Context

- Target user wants a streamlined, flexible personal job search copilot.
- Using `python-jobspy` dramatically reduces scraper maintenance for major platforms (LinkedIn, Google Jobs).
- StepStone requires a dedicated Playwright crawler with anti-bot headers and European/German layout parsing.
- User can freely toggle between local Ollama (for offline privacy and 0 cost) and cloud APIs (for maximum reasoning performance on lower-spec hardware).

## Constraints

- **Language Policy**: **Python-First / Pure Python**: Everything (backend, scrapers, data models, AI/RAG engine, web UI rendering, background workers) must be implemented in Python unless a specific sub-task strictly demands another language. Zero Node.js/npm dependencies for the web stack (HTMX + Tailwind CSS via CDN/standalone).
- **Strict Real-Data Policy (Zero Synthetic Mocks in Runtime)**: No fake placeholder responses or synthetic fallback jobs in production/runtime. All scrapers and AI evaluations must execute against live services. When a live service is unreachable or blocked, Jobot raises explicit actionable error diagnostics and UI status alerts instead of masking failures with mock data.
- **Queue-Driven Execution**: Scraping and AI scoring jobs run through a persistent SQLite async worker queue with state management (`pending`, `in_progress`, `completed`, `failed`) ensuring continuous background execution without dropping tasks.
- **Execution & Development Environment**: Container-first workflow: Development runs inside Docker containers with source bind-mounts and hot-reloading (`docker-compose.dev.yml`). Production runs via `docker-compose.yml` or Kubernetes.
- **Tech Stack**: Pure Python backend and web UI (FastAPI + Jinja2 + HTMX + Tailwind CSS) + SQLite / ChromaDB.
- **AI Backend**: Pluggable provider interface supporting Local Ollama (`ollama-python`) and OpenAI-compatible client (`openai` / `httpx`) with runtime settings persisted in SQLite and fully editable in the UI.
- **Scraping Engine**: Python (`python-jobspy` + `playwright-python` for StepStone and authenticated LinkedIn login).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python-First Architecture | Unified ecosystem across scrapers, AI pipeline, database models, and web UI for maintainability and seamless execution | — Pending |
| Docker-First Development | Ensures consistent Playwright browser environments, system libraries, and local Ollama networking across all host operating systems | — Pending |
| Persistent DB-backed AI Settings | AI parameters (provider, models, API keys, endpoints) are initialized on startup and editable in the UI without server restarts | — Pending |
| Pluggable AI Provider (Ollama vs API Key) | Users on high-end PCs run Ollama for 100% offline privacy; users on laptops/lower-spec hardware can plug in OpenAI/Groq API keys | — Pending |
| `python-jobspy` for LinkedIn & Google Jobs | Battle-tested open-source scraper library handling rate limits, headers, and DOM changes | — Pending |
| Dedicated Playwright for StepStone | Clean headless browser crawler tailored to StepStone's layout and pagination | — Pending |
| Pure Python Web Stack (FastAPI + HTMX) | Snappy reactive UI without Node.js/build overhead, unified Python backend | — Pending |
| ChromaDB Embedded Vector Store | Zero external daemon needed, in-process SQLite storage for CV and feedback vectors | — Pending |
| Status & Notes-driven Vector Tuning | Uses user feedback comments and application outcomes to refine semantic scoring | — Pending |
| Containerization & K8s Manifests | Enables single-command local spin-up via Docker Compose and scalable private cluster deployment via Kubernetes | — Pending |
| Cross-Platform Automation Scripts | Provides seamless build, run, model pull, and deployment automation for Linux/macOS (bash) and Windows (PowerShell) | — Pending |
| Interactive Developer Decision-Making | All architecture, dependency, and plan changes prompt the developer with structured options, pros/cons, and decision context before acting | — Pending |


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
*Last updated: 2026-09-07 after leveraging JobSpy & StepStone Playwright architecture*
