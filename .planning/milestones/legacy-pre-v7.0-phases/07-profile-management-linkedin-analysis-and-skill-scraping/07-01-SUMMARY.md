---
phase: 07-profile-management-linkedin-analysis-and-skill-scraping
plan: 01
subsystem: profile-data
tags:
  - sqlmodel
  - chromadb
  - profile
  - embeddings
dependency_graph:
  requires:
    - "01-03"
    - "02-01"
  provides:
    - app.db.models.UserProfile
    - app.ai.embeddings.ProfileEmbedder
    - app.api.profile
  affects:
    - app.scrapers.scheduler
    - app.web.routes
key_files:
  modified:
    - app/db/models.py
    - app/db/database.py
    - app/ai/embeddings.py
    - app/ai/profile_extractor.py
  created:
    - app/api/profile.py
status: complete
---

# Phase 07 Plan 01: Profile Data Model & Vector Synchronization Summary

Structured profile columns, profile REST endpoints, and ChromaDB profile embedding. Written retrospectively from a goal-backward audit (2026-10-28); only independently verified facts are recorded.

## What Was Verified
1. **Schema** (`app/db/models.py` L107-131): `UserProfile` has `headline`, `bio`, `experience_years`, `work_preference`, `active_search_skills_json`, `experience_history_json`, `education_json`, `projects_json`, `linkedin_session_cookie`, `linkedin_data_json`. `migrate_sqlite_columns()` in `app/db/database.py` adds the new columns to existing databases.
2. **Embedding** (`app/ai/embeddings.py`): `ProfileEmbedder.chunk_profile()` emits three chunks: `profile_summary` (name, headline, bio), `profile_skills` (all skills and active skills) and `profile_experience` (years, work preference, target roles and locations). `embed_and_store_profile()` embeds every chunk and validates dimensions before the first upsert.
3. **Extractor** (`app/ai/profile_extractor.py`): `ExtractedProfile` carries headline, active skills, experience history, education and projects. `save_profile_to_db()` merges and de-duplicates CV and LinkedIn data.
4. **REST** (`app/api/profile.py`): `GET /api/profile`, `POST /api/profile/update` (saves, then re-embeds; reports `partial` if embedding fails), `POST /api/profile/linkedin/sync`, `POST /api/profile/generate-bio`.

## Deviations from Plan / Honest Gaps
- **Experience history is not embedded.** The plan asked to chunk "experience history"; no chunk contains past roles. `test_profile_embeddings_sync` asserts exactly 3 chunks, which encodes this.
- **`linkedin_data_json` is never written** by any code path (schema and encryption list only).
- `POST /api/profile/update` takes no experience history, education or projects. The web form route handles those.
- Embedding backend is now pinned to the local `nomic-embed-text` resolver (Phase 17), not the generation provider.

## Verification
- `tests/run_phase17.py tests/test_profile_and_linkedin.py tests/test_embeddings.py tests/test_cv_parser.py`: 42 passed (disposable DB/Chroma, network blocked).

## Self-Check: PARTIAL
- `app/api/profile.py` FOUND
- `ProfileEmbedder` FOUND (3 chunks, no experience-history chunk)
- `linkedin_data_json` writer NOT FOUND
