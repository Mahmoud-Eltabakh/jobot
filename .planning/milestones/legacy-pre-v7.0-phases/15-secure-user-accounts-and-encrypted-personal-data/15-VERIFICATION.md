---
phase: 15-secure-user-accounts-and-encrypted-personal-data
verified: 2026-10-28T02:00:00Z
status: passed
score: 9/9 must-haves verified
verified_truths: 9
total_truths: 9
behavior_unverified: 0
overrides_applied: 0
gaps: []
deferred: []
human_verification: []
covered_files:
  - ".planning/phases/15-secure-user-accounts-and-encrypted-personal-data/15-01-PLAN.md"
  - ".planning/phases/15-secure-user-accounts-and-encrypted-personal-data/15-01-SUMMARY.md"
  - ".planning/phases/15-secure-user-accounts-and-encrypted-personal-data/15-02-PLAN.md"
  - ".planning/phases/15-secure-user-accounts-and-encrypted-personal-data/15-02-SUMMARY.md"
  - ".planning/phases/15-secure-user-accounts-and-encrypted-personal-data/15-03-PLAN.md"
  - ".planning/phases/15-secure-user-accounts-and-encrypted-personal-data/15-03-SUMMARY.md"
  - "app/ai/embeddings.py"
  - "app/api/auth.py"
  - "app/auth/dependencies.py"
  - "app/auth/security.py"
  - "app/db/models.py"
  - "app/db/ownership.py"
  - "app/db/vector.py"
  - "app/security/encryption.py"
  - "tests/test_auth_security.py"
  - "tests/test_db.py"
covered_digest: "v3:sha256:31b40c926d0fb06aaadb0315da6a23fde63428f7de97b91b9075405a45c58aac"
---

# Phase 15: Secure User Accounts and Encrypted Personal Data Verification Report

**Phase Goal:** Local multi-user accounts, account-scoped data, encrypted personal data and keys.
**Verified:** 2026-10-28T02:00:00Z
**Status:** passed
**Re-verification:** No, initial verification.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Create accounts and sign in with secure password handling | VERIFIED | `security.py` scrypt with random salt and `hmac.compare_digest`; `test_auth_api_endpoints`. |
| 2 | Sessions explicit and revocable | VERIFIED | `UserSession` (token, expiry, `revoked`); `validate_session_token`, `revoke_session`; HttpOnly, SameSite=lax cookies. |
| 3 | Relational data owner-scoped | VERIFIED | `user_id` FK on Job, UserProfile, SearchConfig, FeedbackNote, FilterRule, ApplicationMaterial, ScrapeTask, UserSetting; `test_user_data_isolation`; owner-checked evaluator (`evaluator.py:662`); dedup hash includes owner. |
| 4 | Sensitive data encrypted before persistence | VERIFIED | `database.py:246-247` encrypts sensitive settings; `ownership.py:65-77` encrypts profile fields; Fernet, per-owner derived key. |
| 5 | Key rotation and migration | VERIFIED | Key ring with `previous_encryption_keys`, `rotate_text` (`encryption.py:161`), key id envelope. |
| 6 | No plaintext secrets in DB or default config | VERIFIED | `k8s/secrets.yaml` has an empty `OPENAI_API_KEY`; default key lives in a restricted local key file (`encryption_key_file`), Windows ACL helper. Provider vault keys always encrypted (`database.py:225`). |
| 7 | UX supports sign-in, sign-out, account-scoped state | VERIFIED | `routes.py:146-262` login, register, logout; templates `login.html`, `register.html`. |
| 8 | No cross-user leakage in dashboard or API | FAILED | CV vectors global; see gap 1. Relational API paths are isolated. |
| 9 | Ready for local self-hosted multi-user flow | PARTIAL | Blocked by truth 8; cookie `secure` inconsistency (gap 2). |

**Score:** 7/9 truths verified.

### Key Link Verification

| From | To | Status |
|------|----|--------|
| `get_current_user` | web and API routes | WIRED |
| `encrypt_text` / `decrypt_text` | settings vault, profile fields | WIRED |
| `embed_and_store_profile` / `compute_semantic_similarity` | owner | NOT_WIRED (`user_id` used only to choose the AI client) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Auth and DB tests | `python tests/run_phase17.py <20 files> -q` | 424 passed in 35.55s | PASS |
| Vector scoping | code read of `embeddings.py`, `vector.py` | No owner key or filter | FAIL |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `app/ai/embeddings.py` | Constant ids in a shared collection | Blocker | Overwrite and leak across accounts. |
| `app/web/routes.py` | Cookie lacks `secure=` | Warning | Weaker TLS posture. |

### Human Verification Required

None.

### Gaps Summary

Relational isolation and encryption hold. Isolation breaks in the vector layer: the CV profile embeddings are shared by all users, so a second account changes the first account's semantic scores and its CV vectors are replaced. The web login cookie also misses the `secure` flag that the API path sets.

---

_Verified: 2026-10-28T02:00:00Z_
_Verifier: the agent (gsd-verifier)_

## Gap Closure (2026-10-28)

- CV vectors: ids are `u<user_id>:profile_*` with `user_id` metadata; similarity and count filter by `where={"user_id": ...}`; stale owner chunks are deleted on re-upload; `ProfileEmbedder.delete_user_profile` removes only one owner's chunks. Calls without `user_id` keep the legacy unscoped behavior.
- Legacy fixed-id vectors: `backfill_legacy_cv_vectors` runs at startup and re-keys them (no re-embedding, upsert before delete) only when exactly one account exists, or, with several accounts, when exactly one account's decrypted profile (name, headline, bio) reproduces the stored `profile_summary` text exactly. Otherwise (no match, several matches, or an edited profile) they stay unreachable to every owner rather than leak; that residual case needs an operator re-upload.
- Cookies: web `/login` and `/register` now set `secure` under the same production rule as `api/auth.py`.
- Tests: two-user CV isolation, backfill rules and cookie flags added. Full suite 560 passed (adds multi-account exact-match and ambiguous backfill tests). `covered_digest` was recomputed with `verification.fingerprint` on 2026-10-28 after the last edits to the covered files.