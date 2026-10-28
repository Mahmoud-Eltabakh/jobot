---
phase: 07-profile-management-linkedin-analysis-and-skill-scraping
plan: 04
subsystem: profile-ui
tags:
  - htmx
  - jinja
  - profile-tab
dependency_graph:
  requires:
    - "07-01"
    - "07-02"
  provides:
    - templates/components/profile.html
    - /web/views/profile
  affects:
    - templates/base.html
key_files:
  created:
    - templates/components/profile.html
  modified:
    - templates/base.html
    - app/web/routes.py
status: complete
---

# Phase 07 Plan 04: Profile Editing Web Dashboard Tab Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. **Nav**: `templates/base.html` has a "Profile" tab (`hx-get="/web/views/profile"`).
2. **Routes** (`app/web/routes.py`): `GET /web/views/profile`, `POST /web/profile/update` (saves and re-embeds; purges non-matching jobs), `POST /web/profile/generate-bio`, `POST /web/profile/linkedin/sync`, `POST /web/profile/rescore-filter`.
3. **Template** (`templates/components/profile.html`, 298 lines): name, headline, experience years, work model, minimum salary, locations, target titles, bio with AI generation, all skills, per-skill checkboxes for the active scraper skills, LinkedIn URL and `li_at` sync card, CV upload, experience/education/project JSON editors.
4. Embedding failure on save shows a truthful notice instead of success.

## Deviations from Plan / Honest Gaps
- **Target titles are a comma-separated text input**, not an interactive tag manager.
- **LinkedIn "real-time status"** is only an HTMX loading indicator and the result or error banner after the request.
- `index.html` was not changed for this plan; the tab loads into `#view-container` from `base.html`.
- Browser rendering and keyboard use were not human-reviewed here; only server-rendered output is covered by tests.

## Verification
- `tests/run_phase17.py tests/test_profile_and_linkedin.py`: passed, including `test_web_profile_view_and_form_update`, `test_web_profile_update_cv_data_and_rescore`, `test_web_profile_generate_bio_route` and `test_profile_partial_embedding_failure_is_truthful`. Combined Phase 7 run: 42 passed.

## Self-Check: PARTIAL
- `templates/components/profile.html` FOUND
- Profile nav tab FOUND
- Tag-manager UI NOT FOUND (comma-separated input)
