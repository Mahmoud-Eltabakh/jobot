# Phase 21 Context — Hosted Persistence and Runtime Foundation

## Why this phase exists

The private-beta design depends on a durable runtime model that can survive service restarts, worker restarts, and transient failures without silently losing user work or queue state.

## Product boundary

This phase is not a public SaaS expansion. It is a controlled hosted runtime foundation for the invitation-based beta, while preserving the self-hosted local mode as a supported parallel path.

## Key risks

- queue loss during worker restart or lease expiry
- unsafe assumptions about SQLite/local-only state when moving to multi-instance hosting
- hidden divergence between local and hosted data models
- missing backup/restore and rollback evidence for user-owned artifacts

## Success signal

This phase is complete when the hosted storage and runtime model is durable, recoverable, and explicitly differentiated from the self-hosted path.
