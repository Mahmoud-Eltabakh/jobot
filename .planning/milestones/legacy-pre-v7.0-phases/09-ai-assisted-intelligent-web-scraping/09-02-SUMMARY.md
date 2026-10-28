---
phase: 09-ai-assisted-intelligent-web-scraping
plan: 02
subsystem: query-strategy
tags:
  - query-generation
  - llm
  - blacklist
dependency_graph:
  requires:
    - "07-01"
    - "05-02"
  provides:
    - app.scrapers.query_strategist.AIQueryStrategist
  affects:
    - app.scrapers.scheduler
    - app.queue.worker
key_files:
  created:
    - app/scrapers/query_strategist.py
status: partial
---

# Phase 09 Plan 02: AI Query Strategist & Platform-Specific Search Optimizer Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. `AIQueryStrategist.generate_search_queries()` returns `(platform, keywords, location)` tuples. Active `SearchConfig` rows are authoritative unless a location override requests generation.
2. The prompt includes the candidate's headline, target titles, active skills, target locations, work preference, bio and the owner's active `FilterRule` patterns.
3. Output is validated strictly (platform in `all|linkedin|stepstone|google`, non-empty keywords, string location). A partly malformed batch fails whole.
4. It is used in production by `ScraperPipeline.run_full_pipeline()` (`scheduler.py` L169) and `QueueWorker._handle_full_discovery()` (`worker.py` L316).

## Deviations from Plan / Honest Gaps
- Platform tuning (Boolean strings for LinkedIn, keywords for StepStone and Google) is asked of the LLM in the prompt only. No code enforces or checks per-platform query syntax.
- **No caching.**
- **No fallback heuristics.** Later phases replaced the planned fallback with typed provider errors. This is intentional, but it differs from the plan.
- Blacklist patterns are passed as prompt text; nothing verifies that generated queries omit them.

## Verification
- `tests/run_phase17.py tests/test_ai_scraping.py`: passed, including `test_ai_query_strategist`, owner routing, queries-envelope parsing and provider-failure propagation. Phase 9 group: 24 passed.

## Self-Check: PARTIAL
- `app/scrapers/query_strategist.py` FOUND
- Production call sites FOUND
- Caching NOT FOUND
