# Summary: Phase 15-01 — Account and Session Model

## Goal
Introduce a first-class user account model with secure authentication and strict data scoping.

## Decisions
- Use a dedicated `User` model with a unique identity and password hash.
- Add a `UserSession` record for revocable access tokens or session cookies.
- Scope every user-owned table by `user_id` to ensure account isolation.
- Protect all routes that operate on personal data behind authentication checks.

## Delivered
- Added `User` and `UserSession` models with unique email identities and revocable opaque session tokens.
- Added scrypt password hashing and constant-time verification.
- Added first-run registration, returning-user login, logout, and authenticated navigation.
- Added ownership columns and authenticated query boundaries across jobs, profiles, notes, filters, search configurations, materials, settings, and queue tasks.

## Verification
- Auth lifecycle, registration, login, logout, session revocation, and cross-user isolation are covered by the automated suite.
