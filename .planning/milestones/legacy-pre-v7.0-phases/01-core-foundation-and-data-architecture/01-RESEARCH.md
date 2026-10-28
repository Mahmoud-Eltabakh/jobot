# Phase 1: Core Foundation & Data Architecture - Research

## Overview
Phase 1 establishes the bedrock of the Jobot platform: project configuration, runtime structure, relational SQLite persistence (via SQLModel), vector storage (via ChromaDB), and centralized settings management with zero external daemon requirements.

## Technical Analysis

### 1. Project Scaffolding & Packaging
- **Packaging Standard**: Python `pyproject.toml` using standard `setuptools` or `hatchling` / `flit` with dependency definitions, or `requirements.txt` + `pyproject.toml`.
- **Directory Layout**:
  ```
  Jobot/
  ├── app/
  │   ├── __init__.py
  │   ├── main.py              # FastAPI app creation & lifespans
  │   ├── core/
  │   │   ├── __init__.py
  │   │   ├── config.py        # Pydantic Settings & env management
  │   │   └── logging.py       # Rich / Standard logging configuration
  │   ├── db/
  │   │   ├── __init__.py
  │   │   ├── database.py      # SQLite connection engine & session factory
  │   │   ├── models.py        # SQLModel table definitions
  │   │   └── vector.py        # ChromaDB client & collection helper
  │   ├── api/
  │   │   └── ...
  │   └── services/
  │       └── ...
  ├── data/                    # Storage directory for sqlite.db and chromadb
  ├── tests/
  │   ├── conftest.py
  │   ├── test_config.py
  │   ├── test_db.py
  │   └── test_vector.py
  ├── pyproject.toml
  └── requirements.txt
  ```

### 2. Relational Database: SQLModel (SQLAlchemy + Pydantic)
- **Why SQLModel**: Unifies Pydantic data validation with SQLAlchemy ORM tables in pure Python without duplicate schema definitions.
- **SQLite Engine**: SQLite WAL mode (`PRAGMA journal_mode=WAL;`) enabled on startup for concurrent reads and writes from background scrapers and the web UI.
- **Entity Models**:
  - `Job`: `id`, `source` (linkedin/google/stepstone), `source_id`, `title`, `company`, `location`, `is_remote`, `salary_min`, `salary_max`, `salary_currency`, `url`, `description`, `fit_score`, `fit_reasons_json`, `status` (default "seen"), `created_at`, `updated_at`.
  - `JobStatusHistory`: `id`, `job_id`, `old_status`, `new_status`, `notes`, `changed_at`.
  - `UserProfile`: `id`, `full_name`, `target_titles_json`, `target_locations_json`, `target_salary_min`, `skills_json`, `cv_raw_text`, `linkedin_url`, `updated_at`.
  - `SearchConfig`: `id`, `source`, `keywords`, `location`, `interval_hours`, `is_active`, `last_run_at`.
  - `FeedbackNote`: `id`, `job_id`, `sentiment` (positive/negative/neutral), `note_text`, `created_at`.

### 3. Vector Database: ChromaDB (Local Embedded Mode)
- **Embedded Mode**: In-process `chromadb.PersistentClient(path="data/chroma")`.
- **Collections**:
  - `cv_profile`: Stores semantic chunks of the candidate's CV, key skills, and past achievements.
  - `job_descriptions`: Stores embedded summaries of scraped job postings for semantic similarity queries.
  - `user_feedback`: Stores positive/negative comments and notes mapped to job vectors for adaptive learning.
- **Default Embedding Function**: `nomic-embed-text` via Ollama API, with fallback to ChromaDB's default lightweight embedding function `all-MiniLM-L6-v2` or `SentenceTransformerEmbeddingFunction` when offline.

### 4. Configuration & Settings Management
- **Pydantic Settings**: `pydantic-settings` (`BaseSettings`) loading `.env` with type annotations for `DATABASE_URL`, `CHROMA_PATH`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBED_MODEL`, `LOG_LEVEL`.

## Validation Architecture
- **Pytest Suite**: Fast unit and integration tests under `tests/` verifying database initialization, table CRUD, WAL mode activation, config loading, and ChromaDB collection CRUD.
- **Expected Test Execution Time**: < 3 seconds.
