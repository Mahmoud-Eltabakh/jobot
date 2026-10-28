---
phase: 11-authenticated-linkedin-login-and-session-manager
plan: 01
subsystem: linkedin-auth
tags:
  - playwright
  - linkedin
  - session-cookie
dependency_graph:
  requires:
    - "01-02"
  provides:
    - app.scrapers.linkedin_auth.LinkedInAuthManager
  affects: []
key_files:
  created:
    - app/scrapers/linkedin_auth.py
  modified: []
status: complete
---

# Phase 11 Plan 01: Playwright Interactive Login & Session Cookie Extractor Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. **Manager** (`app/scrapers/linkedin_auth.py`): `LinkedInAuthManager.login_and_capture_session()` rejects blank credentials, drives Playwright to `/login`, fills the form, detects `checkpoint`/`challenge` URLs (returns `requires_2fa` with guidance to paste `li_at`), extracts `li_at`, and never returns the raw cookie in its result.
2. **Persistence**: when a session and `user_id` are supplied, the cookie is written to the owner's `UserProfile` through `get_user_profile` and `encrypt_profile`. A session without `user_id` raises `PermissionError`.
3. **Validation**: `validate_session_cookie()` returns `False` for short/empty values and otherwise loads `/feed/` with the cookie, treating `login`/`authwall` redirects as expired.

## Deviations from Plan / Honest Gaps
- **The manager is dead code.** Nothing under `app/` calls `LinkedInAuthManager`, `login_and_capture_session` or `validate_session_cookie`. The only live LinkedIn path is the pasted-cookie sync in `app/ai/linkedin_analyzer.py`.
- Persistence is silently skipped when the owner has no `UserProfile` row (the `if profile:` branch), yet the method still reports success.
- Live login, 2FA and `/feed/` validation were not exercised (network blocked); only the blank-credentials and short-cookie branches are tested.

## Verification
- `tests/run_phase17.py tests/test_linkedin_auth.py ...`: `test_linkedin_auth_manager_validation` passes (blank credentials and short cookie only).

## Self-Check: PARTIAL
- `LinkedInAuthManager` FOUND
- Wiring into routes/UI NOT FOUND
