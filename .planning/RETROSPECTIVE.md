# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v7.0 — Multi-Provider & Hybrid Local/Cloud AI Routing Engine

**Shipped:** 2026-10-28
**Phases:** 2 | **Plans:** 10 | **Tasks:** 30 | **Sessions:** not tracked

### What Was Built
- Added encrypted provider credentials and independent AI routes for scraping, scoring, and application generation, with embeddings pinned to local Ollama.
- Added bounded model discovery, owner-scoped caching, cooldowns, and advisory model validation for Ollama and cloud providers.
- Added Settings controls and regressions for pagination, owner isolation, model availability, and provider error handling.

### What Worked
- Disposable database, vector-store, and key-storage setup kept the full test suite isolated from user data.
- Focused review findings were converted into regression tests and re-reviewed before closeout.
- Explicitly separating mock verification from live-service and browser acceptance kept the evidence honest.

### What Was Inefficient
- Historical verification reports remained human-needed and required explicit acknowledgement during closeout; future milestones should distinguish code verification from operator-only checks earlier.
- UI review screenshots were not captured for Phase 18, and Python 3.10 was unavailable for the compatibility run.
- Requirement-completion metadata and comment-coverage measurement were incomplete in legacy phase summaries.

### Patterns Established
- Keep provider model discovery advisory: it must not rewrite a user's selection or imply generation entitlement.
- Scope provider caches and credentials to the owning account, and test cross-account boundaries with sentinel data.
- Run Python tests through `tests/run_phase17.py` so database/vector fixtures and service-socket restrictions are applied before imports.

### Key Lessons
1. Record live-provider, browser, and environment-dependent acceptance as explicit operator checks; mocks cannot close those verification gaps.
2. Close and archive a milestone only after verification, audit, and archive checks are complete, and retain deferred items as deferred rather than marking them passed.
3. Capture milestone attribution and verification metadata when phase work is completed; reconstructing it from a shared dirty checkout is unreliable.

### Cost Observations
- Model mix: not tracked
- Sessions: not tracked
- Notable: no reliable per-milestone cost or session attribution was available.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v7.0 | Not tracked | 2 | Added owner-scoped multi-provider AI routing and bounded live model discovery. |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v7.0 | 690 passed, 4 existing warnings | Not measured | Not tracked |

### Top Lessons (Verified Across Milestones)

1. Keep test storage isolated from user data and block unintended service-network access during automated tests.
2. Preserve a clear distinction between automated evidence and operator-only live-service acceptance.
