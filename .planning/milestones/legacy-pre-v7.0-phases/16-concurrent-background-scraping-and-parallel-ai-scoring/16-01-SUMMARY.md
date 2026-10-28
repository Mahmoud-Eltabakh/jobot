# Summary: Phase 16-01 — Decoupled Parallel Queue Worker

## Goal
Deliver a decoupled background worker architecture that separates scraping tasks from AI evaluation tasks into independent loops with safe task claiming.

## Decisions
- Split queue processing into dedicated scraper and evaluator loops instead of a single sequential worker.
- Add type-aware task claiming so each worker only takes its matching task category.
- Keep SQLite access safe under WAL mode with atomic row selection and retry behavior.

## Delivered
- `TaskQueue.claim_next_task()` supports filtering by task type and returns only eligible tasks for the current worker loop.
- `QueueWorker` now runs concurrent async loops for scraping and scoring tasks with graceful pause/resume handling.
- Worker failure domains are isolated so one loop’s exception does not crash the other loop.

## Verification
- Unit and integration tests verify type-specific queue claiming and parallel worker execution.
- The queue lifecycle remains stable under pause/resume and mixed task types.
