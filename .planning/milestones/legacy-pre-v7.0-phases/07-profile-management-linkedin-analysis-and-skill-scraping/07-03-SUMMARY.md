---
phase: 07-profile-management-linkedin-analysis-and-skill-scraping
plan: 03
subsystem: scraper-queries
tags:
  - scheduler
  - query-builder
  - skills
dependency_graph:
  requires:
    - "07-01"
  provides:
    - app.scrapers.scheduler.ScraperPipeline.build_profile_search_queries
  affects:
    - app.scrapers.scheduler
key_files:
  modified:
    - app/scrapers/scheduler.py
status: complete
---

# Phase 07 Plan 03: Dynamic Skill-Driven Scraping Query Builder Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. `ScraperPipeline.build_profile_search_queries()` (`app/scrapers/scheduler.py` from L66) returns an explicit override, else active `SearchConfig` rows, else role and role+skill combinations from the profile's target titles and active skills (via `extract_keywords_from_profile`), using the first target location.
2. Unit test `test_skill_driven_scraper_query_builder` passes.

## Deviations from Plan / Honest Gaps
- **The builder is not called by any production code.** `run_full_pipeline()` and the queue worker call `AIQueryStrategist.generate_search_queries()` (LLM-based, Phase 9) instead. The skill-driven matrix is therefore delivered through the AI strategist; the deterministic builder is an orphaned helper kept alive by one test.
- Selected active skills do influence queries, but via the strategist prompt (`extract_keywords_from_profile`), not the deterministic matrix.
- Dispatch to `JobSpyScraper` and `StepStoneScraper` happens in `run_full_pipeline()` and the worker with strategist-produced queries.

## Verification
- `tests/run_phase17.py tests/test_profile_and_linkedin.py tests/test_scheduler.py`: passed (Phase 7 group 42 passed, Phase 9 group 24 passed).

## Self-Check: PARTIAL
- `build_profile_search_queries` FOUND (no production caller)
- Strategist-driven query path FOUND (`scheduler.py` L169, `worker.py` L316)
