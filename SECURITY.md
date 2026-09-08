# Security Policy

## Supported Versions

Jobot actively supports security updates for the `main` branch and latest release tags.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a Vulnerability

We take the security and privacy of Jobot very seriously. Since Jobot handles local candidate CV data, credentials, and API keys, maintaining strict data boundaries is a core priority.

### How to Report

**Please do NOT open public GitHub issues for security vulnerabilities.**

If you discover a security vulnerability or prompt injection risk:
1. Email the project maintainers directly or send a private advisory via GitHub.
2. Include a detailed description of the vulnerability, steps to reproduce, and potential impact.
3. Allow up to 48 hours for an initial response from maintainers.

### Security Architecture Principles
Jobot's security posture is continually validated against a STRIDE threat model covering local and cloud boundaries.
- **Privacy-First**: Jobot operates 100% locally when configured with Ollama — no candidate data, resumes, or scraped job records leave your local machine.
- **Prompt Injection Defense**: Input job descriptions are sanitized, bounded with XML tags, and strictly validated before being passed to LLMs.
- **Rate Limiting**: Authentication endpoints and worker queues employ bounds and rate limits to mitigate brute-force and DoS risks.
- **Account Isolation**: Personal records and configurable preferences carry an owning `user_id`; protected routes resolve them only inside the authenticated account.
- **Password Storage**: Passwords are salted and hashed with scrypt. Jobot never stores or logs plaintext passwords.
- **Credential Storage**: CV/LinkedIn content, LinkedIn credentials, and provider API keys use authenticated encryption scoped to the owning account and are never reflected into HTML forms.
- **Session Lifecycle**: Login issues an opaque, expiring HTTP-only cookie backed by a revocable database session record.

## Encryption Keys and Recovery

- Production deployments must set `ENCRYPTION_KEY` through an external secret mechanism. Keep the key out of images, manifests, logs, and repository files.
- Production deployments should explicitly verify `DEBUG=false` in `.env` to prevent stack trace disclosures on error pages.
- Development installations may use the generated `data/.jobot-encryption-key` file.
- **Windows Users:** The local key file is protected via Windows ACLs (`icacls`), but we strongly recommend explicitly setting `ENCRYPTION_KEY` in your `.env` or system environment variables for production security.
- `ENCRYPTION_KEY_ID` identifies new ciphertext. `PREVIOUS_ENCRYPTION_KEYS` accepts comma-separated `key-id:key` entries while rotating existing data.
- Losing every key capable of decrypting a record is irreversible by design. Test restored database and key backups before relying on them.
- Legacy unowned records are claimed only when exactly one user exists; ambiguous multi-user data is left untouched for explicit operator recovery.
