# Summary: Phase 15-02 — Encryption and Key Management

## Goal
Protect personal job-search data before it is persisted to the local database.

## Decisions
- Use authenticated encryption for sensitive fields.
- Encrypt CV content, API keys, LinkedIn cookies, user notes, and other account-sensitive values.
- Keep the master key outside the repository, using environment variables or OS key storage.
- Add key-version metadata so rotation and migration are manageable.

## Delivered
- Added user-scoped Fernet authenticated encryption for CV/LinkedIn profile fields and provider credentials.
- Added key IDs, previous-key configuration, rotation helpers, and an owner-restricted local development key file.
- Production mode fails closed when `ENCRYPTION_KEY` is absent.
- Legacy single-user records are claimed only when ownership is unambiguous and are re-encrypted during migration.
- Stored API keys and LinkedIn cookies are no longer rendered into HTML forms.

## Verification
- Round-trip, wrong-owner, secret non-reflection, blank-key preservation, and legacy migration behavior are covered by tests.
