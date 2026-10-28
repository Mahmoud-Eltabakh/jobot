# Phase 20 Context — Tenant, Privacy, and Hosted Security Invariants

## Why this phase exists

Once the beta contract is known, the next requirement is proof that user data is isolated and protected. This is a prerequisite to any hosted work because the product stores CVs, profile data, job interest data, AI outputs, and potentially provider credentials.

## Key risks

- cross-account read or write access
- shared caches, vectors, tasks, or exports that bypass ownership checks
- leaked provider secrets or sensitive profile fields in logs or error output
- unsafe fallback paths that expose data or bypass guardrails

## Design principles

- fail closed on ownership mismatch
- owner-bound access for all reads, writes, tasks, exports, and deletion operations
- minimize exposure of sensitive values to logs, provider calls, and support artifacts
- treat every data store as an ownership boundary, not just the primary database

## Success signal

This phase is successful when tenant boundaries are proven with negative tests and every sensitive data flow has a documented owner and protection model.
