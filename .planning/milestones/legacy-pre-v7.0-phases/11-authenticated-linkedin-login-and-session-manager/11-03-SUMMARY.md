---
phase: 11-authenticated-linkedin-login-and-session-manager
plan: 03
subsystem: linkedin-ui
tags:
  - htmx
  - profile-ui
dependency_graph:
  requires:
    - "11-02"
  provides:
    - templates.components.profile.linkedin_cookie_form
  affects: []
key_files:
  created: []
  modified:
    - templates/components/profile.html
    - app/web/routes.py
status: complete
---

# Phase 11 Plan 03: LinkedIn Login Web UI & Profile Sync Dialog Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. **Cookie sync form** (`templates/components/profile.html`): LinkedIn URL plus `li_at` cookie fields, instructions for obtaining the cookie, and a sync button. The route is `POST /web/profile/linkedin/sync` (`app/web/routes.py`).
2. The Profile view renders (`test_profile_tab_linkedin_cookie_form`).

## Deviations from Plan / Honest Gaps
- **Not delivered:** the email/password "LinkedIn Account Login" form, `POST /web/profile/linkedin/login`, and any Logged In / Active Cookie / Expired status badge. No route, template or test references them, and no code path reads cookie validity.
- ROADMAP.md reworded this plan to a cookie-sync card, which is what exists; the PLAN file itself still specifies the login form and status.

## Verification
- `tests/test_linkedin_auth.py` (3 tests) and `tests/test_profile_and_linkedin.py` pass.

## Self-Check: PARTIAL
- Cookie form FOUND
- Credential login endpoint NOT FOUND
- Session status display NOT FOUND
