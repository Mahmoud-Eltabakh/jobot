# Research: Account Login and Per-User Encrypted Data

## Outcome
Add a secure account layer so each user can log in, keep their own profile and job data isolated, and protect sensitive information at rest with strong encryption.

## Core requirements
- User accounts with secure authentication and session management.
- Each user has isolated job history, profile state, filters, AI settings, notes, and queue state.
- Sensitive fields must be encrypted before storage, including CV content, LinkedIn session cookies, API keys, and other personal data.
- The local app remains the trust boundary; no data should be exposed publicly.

## Recommended approach
### Authentication
- Use a local email/password flow or OAuth-based provider with explicit user consent.
- Hash passwords with a modern password hashing algorithm such as bcrypt or Argon2.
- Store only the password hash and metadata; never store raw password data.
- Create stateless or server-side session tokens with expiration and revocation support.

### Data isolation
- Add a `user_id` foreign key to all user-owned tables: jobs, profile data, settings, notes, queue tasks, and embedding metadata.
- Scope queries by authenticated user so data cannot spill across accounts.
- Use per-user storage paths or encrypted container names when designing local data boundaries.

### Encryption at rest
- Encrypt all sensitive user content before writing to SQLite or file storage.
- Prefer a per-user encryption key derived from a master secret and user-specific salt or key ID.
- Use an authenticated encryption mode such as AES-GCM to avoid tampering.
- Store key metadata separately from the ciphertext and never in plaintext alongside user content.

### Sensitive fields to protect
- CV text and uploaded file metadata.
- LinkedIn session cookies and access tokens.
- API keys and provider credentials.
- Notes, cover letters, and any stored personal job-search details.
- User-specific AI prompt context and profile vectors when they contain personal data.

### Open-source implementation guidance
- Keep the auth and encryption logic in dedicated modules under `app/auth/` and `app/security/`.
- Add tests for login, password hashing, session lifecycle, encryption/decryption round-trips, and user isolation.
- Do not hard-code secret values; read secrets only from environment variables or OS key storage.
- Document recovery, rotation, and backup-safe handling of encryption keys.

## Risks and mitigations
- Risk: Cross-user leakage from unscoped database queries.
  Mitigation: add a strict `user_id` filter at the repository layer and integration tests for isolation.
- Risk: Weak password handling.
  Mitigation: bcrypt/Argon2 with cost tuning and session expiration.
- Risk: Broken encryption keys during upgrades.
  Mitigation: key versioning and migration tooling before re-encrypting data.
- Risk: UI confusion on multi-user context.
  Mitigation: rely on a clear login/logout flow and user-scoped dashboard state.

## Planned milestone impact
This milestone should introduce the first production-grade multi-user security layer without compromising the privacy-first, self-hosted nature of Jobot. The user account layer should support secure login, local-only operation, encrypted storage, and isolated user data while preserving the current project architecture.
