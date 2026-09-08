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
```bash
# Run complete test suite
pytest

# Run specific test file
pytest tests/test_db.py -v

# Run full test suite with in-memory database to avoid corrupting local data
pytest
```

### Security & Functional Testing
- **In-Memory Testing**: The test suite automatically runs against an in-memory database by forcing `DATABASE_URL="sqlite:///:memory:"` in `conftest.py`.
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
   - Keep AI clients pluggable. Never hardcode proprietary cloud models as strict requirements; always support local Ollama fallback.
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

## 🔄 6. Open Source Contribution Workflow

### 1. Issue Reporting
- **Bug Reports**: Use [.github/ISSUE_TEMPLATE/bug_report.md](.github/ISSUE_TEMPLATE/bug_report.md). Include steps to reproduce, execution mode (Host Ollama / Docker), and relevant terminal/container logs.
- **Feature Requests**: Use [.github/ISSUE_TEMPLATE/feature_request.md](.github/ISSUE_TEMPLATE/feature_request.md). Explain the motivation, proposed solution, and alternatives considered.

### 2. Branching & Pull Requests
- Fork the repository and create a feature branch off `main` (`git checkout -b feature/my-new-feature`).
- Ensure all tests pass (`pytest`) and code is formatted (`ruff check .` and `ruff format .`).
- Submit a Pull Request targeting `main` using [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).

### 3. Community & Conduct
Please adhere to our [Code of Conduct](../CODE_OF_CONDUCT.md) in all community interactions. For security disclosures, see our [Security Policy](../SECURITY.md).

---

## 🔄 7. Documentation Synchronization

Whenever you add or change features:
1. Update `docs/USER_MANUAL.md` for end-user functionality.
2. Update `docs/CONTRIBUTING.md` for architecture/developer workflows.
3. Commit your documentation updates along with your code changes.
