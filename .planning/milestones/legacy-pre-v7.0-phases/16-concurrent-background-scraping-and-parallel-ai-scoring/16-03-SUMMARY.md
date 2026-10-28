# Summary: Phase 16-03 — Concurrency Controls & Monitoring

## Goal
Let users tune resource usage and observe live parallel activity in the queue dashboard without sacrificing reliability.

## Decisions
- Expose runtime concurrency settings through the Settings API and UI.
- Show active scraping and AI-scoring counts in the queue dashboard to make parallel workloads visible.
- Cover the new behavior with a focused regression suite.

## Delivered
- Settings now persist `concurrency_max_scrapers` and `concurrency_max_evaluators` values and render interactive sliders in the UI.
- The AI Queue view renders active scraping vs. AI scoring counts and concurrency limits.
- Regression tests cover settings persistence, queue dashboard rendering, and parallel execution constraints.

## Verification
- The focused Phase 16 suite passes: `tests/test_parallel_execution.py`.
- The project test suite remains green after the milestone update.
