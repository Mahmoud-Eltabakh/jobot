# Jobot Requirements

## Product Requirements

### 1. Data Storage & Architecture
- **REQ-DB-01**: Single-file SQLite database with SQLAlchemy/SQLModel models for `Jobs`, `JobStatusHistory`, `UserProfile`, `SearchConfigs`, `FeedbackNotes`, `FilterRules`, and `AppSettings` (storing persistent, UI-editable AI configurations and system preferences initialized with sensible defaults on startup).
- **REQ-DB-02**: Vector storage via embedded ChromaDB for CV embeddings, job description embeddings, and feedback embeddings.
- **REQ-DB-03**: Automatic database migration and initialization on startup with default settings seeding.

### 2. Profile & CV Ingestion
- **REQ-CV-01**: PDF and DOCX CV file upload with text extraction (`pypdf` / `pdfplumber`).
- **REQ-CV-02**: LinkedIn profile export parser / structured manual profile entry.
- **REQ-CV-03**: Automated profile extraction using Ollama to parse skills, years of experience, target job roles, and seniorities.
- **REQ-CV-04**: Store chunked and embedded CV representation in vector database.

### 3. Multi-Source Web Scraping & Filtering Engine
- **REQ-SCR-01**: `python-jobspy` integration for robust, multi-source **LinkedIn** and **Google Jobs** scraping (plus Indeed/Glassdoor optional flags).
- **REQ-SCR-02**: Dedicated Playwright scraper for **StepStone** jobs with pagination, dynamic card handling, and full job detail extraction.
- **REQ-SCR-03**: Deduplication engine preventing duplicate job entries based on normalized company, title, and link hashes.
- **REQ-SCR-04**: **Pre-AI Ingestion Filter Pipeline**: Fast rule-based exclusion filter that discards or flags scraped jobs matching blacklisted job title patterns (e.g. regex/substrings for "Staff", "Director", "Intern", "Senior Principal") or excluded keywords (e.g. "No Remote", "PHP", "Unpaid") *before* running AI scoring to conserve LLM tokens and compute.
- **REQ-SCR-05**: Anti-blocking measures (randomized request intervals, stealth headers, session management).

### 4. Background Worker & Scheduling
- **REQ-SCH-01**: Configurable periodic background job scraper (e.g. every 6, 12, or 24 hours).
- **REQ-SCH-02**: On-demand "Scrape Now" trigger from dashboard for immediate search execution.
- **REQ-SCH-03**: Background queue worker processing newly scraped jobs through the pre-filter and AI scoring pipeline.

### 5. AI Evaluation & RAG Matching Engine
- **REQ-AI-01**: Pluggable AI backend supporting **Local Ollama** (`llama3.1`, `mistral`, `qwen2.5`) OR **External/Cloud API** (OpenAI, Anthropic, Groq, or any OpenAI-compatible base URL with API key).
- **REQ-AI-02**: Fit score calculation (0–100%) based on semantic cosine similarity + LLM qualitative analysis.
- **REQ-AI-03**: Structured analysis generation containing Match Summary, Key Strengths, Missing Skills / Gaps, and Tailored Recommendation.
- **REQ-AI-04**: Robust fallback handling with live provider health/status verification and latency monitoring.

### 6. User Interface & Tracking
- **REQ-UI-01**: Pure Python web dashboard (FastAPI + HTMX + Tailwind CSS) with clean, modern styling.
- **REQ-UI-02**: Kanban Board view with drag-and-drop or one-click status transitions across all 8 stages:
  `seen`, `applied`, `not a good fit`, `rejected`, `1. interview`, `2. interview`, `3. interview`, `waiting for respond`.
- **REQ-UI-03**: **Advanced Multi-Criteria Sorting & Filtering Toolbar**:
  - **Sorting Dimensions**: Fit Score (Highest/Lowest), Salary (Highest/Lowest), Date Scraped/Posted (Newest/Oldest), Company (A–Z), Job Title (A–Z).
  - **Filter Criteria**:
    - **Work Model**: Remote Only, Hybrid, On-site toggles.
    - **Minimum Fit Score Slider**: Live threshold filter (e.g., ≥ 70%, ≥ 80%, ≥ 90%).
    - **Salary Filter**: Minimum desired compensation threshold with currency normalization.
    - **Source Board**: LinkedIn, StepStone, Google Jobs checkboxes.
    - **Location & Distance**: City/Country text filter.
    - **Skill & Keyword Match Tags**: Filter positions containing specific positive skills or matching candidate CV highlights.
    - **Quick Toggles**: "Hide Not a Good Fit", "Hide Rejected", "Show Bookmarked/Starred Only".
- **REQ-UI-04**: Split-pane / Modal Job Inspector showing full job description, AI analysis, company info, direct application link, and user comments.
- **REQ-UI-05**: User Notes and Feedback field per position to record interview logs, impressions, and specific reasons for fit/rejection.

### 7. Feedback Loop & Search Optimization
- **REQ-FBL-01**: Status-driven learning: jobs marked `not a good fit` or `rejected` with notes generate negative keyphrases, vector penalties, and suggestions for blacklist rules.
- **REQ-FBL-02**: Jobs marked `applied` or `interview` reinforce positive skill vectors and search terms.
- **REQ-FBL-03**: Search query optimizer that refines scraper query parameters and negative exclusion lists based on historical feedback.

### 8. Search Settings & AI Provider Configuration
- **REQ-CFG-01**: Web interface for managing search keywords, target job titles, target locations (Remote/Hybrid/Onsite), and salary filters.
- **REQ-CFG-02**: **Comprehensive Blacklist & Filtering Configuration**: UI editor to add/edit/delete excluded title phrases (e.g., "Senior Lead", "Manager"), blacklisted companies, and negative body keywords (e.g., "C1 German", "No Visa sponsorship", "Travel 50%").
- **REQ-CFG-03**: **AI Provider Configuration UI**: Toggle between **Local Ollama** and **API Key / Cloud Provider** (OpenAI, Anthropic, Groq, Custom OpenAI-compatible endpoint). Includes model dropdown, API key input, connection test button, and status diagnostics.

### 9. Containerization, Orchestration & DevOps Automation
- **REQ-OPS-01**: Multi-stage `Dockerfile` and `Dockerfile.dev` installing Python dependencies and Playwright browser binaries (Chromium) in a lightweight Linux runtime.
- **REQ-OPS-02**: Docker Compose configurations for both development (`docker-compose.dev.yml` with source code bind-mounts and hot reload) and production (`docker-compose.yml`) orchestrating Jobot and a local Ollama container with persistent volume mounts for SQLite (`/app/data`), ChromaDB (`/app/data/chroma`), and Ollama models (`/root/.ollama`), with GPU passthrough support.
- **REQ-OPS-03**: Kubernetes manifests (`k8s/`): Namespace, ConfigMap, Secrets, PVCs (data, chroma, ollama-models), Deployments for Jobot and Ollama, Services, and Ingress configuration.
- **REQ-OPS-04**: Cross-platform automation scripts (`scripts/` in Bash and PowerShell) for building images, running local development/production containers, model pre-pulling, and deploying to Kubernetes clusters.

### 10. Queue-Driven Background Scraping & Continuous Task Processing
- **REQ-QUE-01**: Persistent SQLite-backed task queue (`ScrapeTask` / `JobTask`) tracking background scraping queries, extraction jobs, and AI scoring batches across restarts.
- **REQ-QUE-02**: Asynchronous background worker loop continuously consuming queued scraping tasks with rate-limiting, concurrency control, and failure logging.
- **REQ-QUE-03**: Real-time queue status endpoint and dashboard widget showing active, pending, and completed scraping tasks.

### 11. Authenticated LinkedIn Login & Session Management
- **REQ-LIN-01**: Automated Playwright interactive login workflow allowing candidate credentials or `li_at` session cookie injection.
- **REQ-LIN-02**: Secure local cookie session persistence in SQLite (`UserProfile.linkedin_session_cookie`) avoiding repeated authentication prompts.
- **REQ-LIN-03**: Full authenticated profile extraction capturing detailed work history, endorsements, skills, and about sections.

### 12. Strict Real-Data Enforcement & Actionable Error Handling
- **REQ-DAT-01**: Zero synthetic mock fallbacks in runtime/production code: scrapers, LinkedIn analyzer, and AI evaluators strictly execute live network and LLM requests.
- **REQ-DAT-02**: Actionable UI error notifications, alert banners, and status badges displayed when Ollama is offline, network requests are blocked, or credentials require renewal.
- **REQ-DAT-03**: Comprehensive error diagnostics and failure history logged to SQLite for debugging.
