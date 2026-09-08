# Research Summary: Jobot AI Job Search Agent & Dashboard

## Domain Overview
Building an automated personal job search pipeline with local AI and a modern Python UI involves three core architectural pillars:
1. **Multi-source Job Scraping Pipeline**: Leveraging `python-jobspy` for robust, maintained extraction across LinkedIn and Google Jobs (plus Indeed/Glassdoor), coupled with a dedicated Playwright crawler for StepStone.
2. **Local AI & Vector RAG Ingestion**: Using Ollama (e.g. `llama3.1:8b`, `qwen2.5:7b`) and embedding models (`nomic-embed-text`, `bge-small-en-v1.5`) with ChromaDB for semantic similarity, skill gap extraction, and scoring.
3. **Pure Python Web Dashboard & Adaptive Feedback**: Providing responsive Kanban / Table interfaces with HTMX/Tailwind + FastAPI and leveraging user annotations and status progressions to continuously tune search queries and vector relevance weighting.

## Key Technical Decisions & Patterns

### 1. Scraping Engine Architecture
- **JobSpy Integration (`python-jobspy`)**: Handles **LinkedIn** and **Google Jobs** search requests, proxy management, headers, pagination, and anti-blocking routines natively without brittle custom DOM selectors.
- **Dedicated StepStone Scraper (Playwright)**: Headless browser automation targeting StepStone (stepstone.de / stepstone.com), handling cookie consent popups, dynamic job card pagination, salary badges, and full job description extraction.
- **Deduplication**: Hash-based deduplication on normalized `(company_name, job_title, normalized_location)` stored in SQLite.

### 2. Local AI & Vector RAG Strategy
- **Ollama Client**: Asynchronous `ollama-python` client with configurable base URL (`http://localhost:11434`).
- **Embedding Store**: ChromaDB (in-process SQLite-backed) storing:
  1. Profile chunk embeddings (CV sections, key skills, experience history).
  2. Job description embeddings (title, description, required qualifications).
  3. User feedback & note embeddings (positive/negative reaction vectors).
- **Matching & Scoring**:
  - Distance metrics (cosine similarity) combined with prompt-driven LLM evaluation.
  - LLM outputs structured JSON: `{ "fit_score": 88, "pros": [...], "cons": [...], "missing_skills": [...] }`.
- **Feedback Loop**:
  - Positions marked "not a good fit" or "rejected" supply negative keyphrases to exclude in future searches.
  - Positions marked "applied" or progressing to "interview" reinforce positive keyword and skill weights.

### 3. Pure Python Web Architecture
- **FastAPI + Jinja2 + HTMX + Tailwind CSS**: Zero-node build, snappy reactive UI with server-side rendering, modal dialogs, and instant status updates without full page reloads.
- **Database**: SQLite with SQLAlchemy or SQLModel for clean schema migrations and single-file portability.
- **Task Scheduling**: APScheduler / Asyncio background worker for periodic execution.

### 4. Containerization & Kubernetes Architecture
- **Playwright in Docker**: Base image `python:3.11-slim` or `mcr.microsoft.com/playwright/python:v1.49.0-noble` with required system shared libraries (`libnss3`, `libatk`, `libcups2`, etc.) and `playwright install chromium --with-deps`.
- **Docker Compose Topology**:
  - `jobot`: Port 8000 exposed, depends on `ollama` with healthcheck, environment variables for `OLLAMA_BASE_URL=http://ollama:11434`, volumes mounted for `./data:/app/data`.
  - `ollama`: Official `ollama/ollama:latest` image, GPU reservation (`nvidia-container-runtime`), volume for `ollama_data:/root/.ollama`.
- **Kubernetes Architecture**:
  - Namespace: `jobot`.
  - Storage: `PersistentVolumeClaim` (ReadWriteOnce) for SQLite & ChromaDB (`jobot-data-pvc`) and Ollama models (`ollama-models-pvc`).
  - Deployments: `jobot-deployment` (1 replica to avoid SQLite write lock conflicts) and `ollama-deployment` (with optional GPU resources).
  - Services & Ingress: ClusterIP services for inter-pod routing and Ingress (NGINX/Traefik) for domain routing.
- **Automation Scripts**:
  - `scripts/build.sh` & `scripts/build.ps1`: Builds docker image with proper tags.
  - `scripts/run-docker.sh` & `scripts/run-docker.ps1`: Starts docker-compose stack and triggers Ollama model pull (`ollama pull llama3.1:8b`).
  - `scripts/deploy-k8s.sh` & `scripts/deploy-k8s.ps1`: Applies K8s manifests in correct order with status rollout checks.

## Gotchas & Risk Mitigations
- **Scraper Stability**: Using `python-jobspy` isolates core job board layout changes to a widely-maintained upstream library.
- **Anti-bot Blocks on StepStone**: Use Playwright stealth plugins, randomized user agents, and respectful crawl delays (2-5s).
- **Ollama Availability**: Graceful fallback UI when Ollama is offline or model is not pulled yet, with a status indicator in the dashboard.
- **PDF Extraction**: Use `pypdf` / `pdfplumber` for robust multi-column CV parsing and text extraction.
