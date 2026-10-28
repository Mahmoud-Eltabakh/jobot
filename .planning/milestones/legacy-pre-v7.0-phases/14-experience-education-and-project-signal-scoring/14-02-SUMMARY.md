---
phase: 14-experience-education-and-project-signal-scoring
plan: 02
subsystem: profile-ui
tags:
  - profile
  - merge
dependency_graph:
  requires:
    - "14-01"
  provides:
    - templates.components.profile.history_sections
  affects: []
key_files:
  created: []
  modified:
    - templates/components/profile.html
    - app/ai/profile_extractor.py
    - app/web/routes.py
status: complete
---

# Phase 14 Plan 02: Profile Sections UI & Merge Integrity Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. **UI**: `templates/components/profile.html` shows separate CV and LinkedIn parsed-text panels, and editable JSON textareas for experience, education and projects, alphabetized by `sort_profile_entries` in `get_profile_view`. `POST /web/profile/update` saves all three.
2. **Merge** (`save_profile_to_db`): experience is joined and deduped by title+company, education by school+degree, projects by name, and skills and titles are unioned. Existing entries are kept and CV and LinkedIn raw text are stored separately. Verified by reading the code only; no test saves a second source into an existing profile.

## Deviations from Plan / Honest Gaps
- "Sortable" means a fixed alphabetical sort at render time, not a user control. Edits are raw JSON text. Invalid JSON is silently ignored on save, and plain text becomes `{"description": ...}` entries.
- The LinkedIn panel textarea (`linkedin_raw_text`) has no matching form parameter, so edits to it are dropped.
- Experience is sorted alphabetically, not chronologically.
- A profile-form save re-embeds an `ExtractedProfile` without experience, education or projects.
- **Closed 2026-10-28:** see 14-VERIFICATION.md Gap Closure; remaining caveats listed there.

## Verification
- `tests/test_profile_and_linkedin.py` (profile edit and rescore) and `test_save_profile_to_db` (single save into an empty DB) pass. The merge path is untested.

## Self-Check: PASSED
- Source-separated sections and non-destructive merge FOUND
- Persisting `linkedin_raw_text` edits NOT FOUND
