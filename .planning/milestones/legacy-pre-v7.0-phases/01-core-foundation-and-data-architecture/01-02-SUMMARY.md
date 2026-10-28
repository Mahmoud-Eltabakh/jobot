---
phase: 01-core-foundation-and-data-architecture
plan: 02
subsystem: database
tags:
  - sqlite
  - sqlmodel
  - sqlalchemy
  - wal-mode
  - app-settings
  - filter-rules
dependency_graph:
  requires:
    - "01-01"
  provides:
    - app.db.database
    - app.db.models
  affects:
    - app.scrapers
    - app.ai
    - app.web
tech_stack:
  added:
    - sqlmodel 0.0.x
    - sqlalchemy 2.0.x
    - sqlite3 (WAL mode)
key_files:
  created:
    - app/db/__init__.py
    - app/db/database.py
    - app/db/models.py
    - tests/test_db.py
decisions:
  - Enabled SQLite WAL mode (`PRAGMA journal_mode=WAL;`) and foreign keys on all connections.
  - Implemented `AppSettings` model with dynamic JSON serialization for UI-editable AI settings without server restarts.
  - Created `Job` model supporting all 8 lifecycle statuses, compensation tags, and SHA256 deduplication hashes.
  - Added `FilterRule` model for negative blacklist screening by title, keyword, or company.
status: complete
---

# Phase 01 Plan 02: Relational SQLite Database & Models Summary

SQLModel relational SQLite layer with WAL mode concurrency, entity schemas (`Job`, `JobStatusHistory`, `UserProfile`, `SearchConfig`, `FeedbackNote`, `FilterRule`, `AppSettings`), default settings seeding, and test suite.

## What Was Done
1. **Relational Models (`app/db/models.py`)**:
   - `JobStatus`: Enum covering all 8 application lifecycle stages (`seen`, `applied`, `waiting for respond`, `1. interview`, `2. interview`, `3. interview`, `not a good fit`, `rejected`).
   - `Job`: Full schema with source, external IDs, salary ranges, deduplication hash, and AI fit score JSON fields.
   - `JobStatusHistory`: Audit log for status changes and user feedback comments.
   - `UserProfile`: Target titles, locations, compensation minimums, skills JSON, and CV text.
   - `SearchConfig`: Scraper task definitions with schedule intervals and active states.
   - `FeedbackNote`: User notes with sentiment tags.
   - `FilterRule`: Blacklist exclusion rules for titles, keywords, and companies.
   - `AppSettings`: Dynamic key-value configuration storage.
2. **Database Engine & Connection Lifecycle (`app/db/database.py`)**:
   - SQLite engine with `check_same_thread=False` and WAL mode pragma listener.
   - `init_db()` creating tables and seeding initial `AppSettings` (AI provider, Ollama models, default intervals).
   - `get_session()` dependency generator and `get_app_setting()` / `set_app_setting()` helpers.
3. **Automated Test Suite (`tests/test_db.py`)**:
   - Tests for Job CRUD, status history progression, UserProfile JSON list handling, FilterRule queries, and dynamic AppSettings updates.

## Deviations from Plan
- None - plan executed cleanly as specified.

## Verification
- `pytest tests/test_db.py` executed with 4 passing tests in 0.31s.
- SQLite database initialization verified with WAL mode enabled.

## Self-Check: PASSED
- `app/db/models.py` FOUND
- `app/db/database.py` FOUND
- `tests/test_db.py` FOUND
