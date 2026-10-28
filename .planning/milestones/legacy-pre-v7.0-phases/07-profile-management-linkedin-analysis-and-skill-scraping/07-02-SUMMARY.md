---
phase: 07-profile-management-linkedin-analysis-and-skill-scraping
plan: 02
subsystem: linkedin-ingestion
tags:
  - linkedin
  - playwright
  - llm-analysis
dependency_graph:
  requires:
    - "07-01"
  provides:
    - app.ai.linkedin_analyzer
  affects:
    - app.api.profile
    - app.web.routes
key_files:
  created:
    - app/ai/linkedin_analyzer.py
  modified:
    - app/api/profile.py
    - app/web/routes.py
status: complete
---

# Phase 07 Plan 02: LinkedIn Profile Ingestion & AI Analyzer Summary

`LinkedInProfileAnalyzer` ingests a LinkedIn profile and syncs it into `UserProfile` and ChromaDB. Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. **Analyzer** (`app/ai/linkedin_analyzer.py`): `sync_linkedin_to_profile()` tries three sources in order when a cookie is given: the `linkedin-api` Voyager client, the Playwright-based `linkedin_scraper`, then raw Playwright DOM text with `li_at` injection. A `raw_text_override` skips scraping.
2. **AI analysis**: `analyze_profile_text()` filters navigation and authwall text, calls the scraping-stage client with `json_mode`, validates into `ExtractedProfile`, and generates a bio when the summary is empty. Invalid or empty output raises a typed provider error and is not stored as a profile.
3. **Persistence**: the extracted profile is embedded with the local embedding client, saved via `save_profile_to_db()`, and the cookie is stored on `UserProfile.linkedin_session_cookie` and encrypted for the owner.
4. **Endpoints**: `POST /api/profile/linkedin/sync` (JSON) and `POST /web/profile/linkedin/sync` (HTMX form).

## Deviations from Plan
- The plan named only URL, cookie, Playwright and text. The implementation adds Voyager and `linkedin_scraper` tiers. Not exercised against live LinkedIn here (offline verification).

## Verification
- `tests/run_phase17.py tests/test_profile_and_linkedin.py`: passed, including `test_linkedin_analyzer_text_extraction`, `test_linkedin_api_public_id_extraction`, `test_fetch_profile_via_joeyism_scraper_empty_cookie`, `test_linkedin_sync_routes_owner_generation_and_local_vectors` and `test_linkedin_vector_failure_preserves_profile`. Combined Phase 7 run: 42 passed.
- No live LinkedIn network call was made.

## Self-Check: PASSED
- `app/ai/linkedin_analyzer.py` FOUND
- `POST /api/profile/linkedin/sync` FOUND
- `POST /web/profile/linkedin/sync` FOUND
