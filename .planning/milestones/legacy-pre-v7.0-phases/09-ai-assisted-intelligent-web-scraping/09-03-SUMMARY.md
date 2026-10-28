---
phase: 09-ai-assisted-intelligent-web-scraping
plan: 03
subsystem: scraper-integration
tags:
  - stepstone
  - scheduler
  - settings
dependency_graph:
  requires:
    - "09-01"
    - "09-02"
  provides:
    - app.scrapers.scheduler.ScraperPipeline
  affects:
    - app.scrapers.stepstone
key_files:
  modified:
    - app/scrapers/stepstone.py
    - app/scrapers/scheduler.py
status: complete
---

# Phase 09 Plan 03: Hybrid Scraper Pipeline Integration Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. `ScraperPipeline.run_full_pipeline()` generates queries with `AIQueryStrategist` and still runs `JobSpyScraper` and `StepStoneScraper` unchanged when an override keyword is given.
2. The StepStone fast path (CSS selectors on `article` cards) is intact. `tests/test_stepstone.py` passes.

## Deviations from Plan / Honest Gaps
- **StepStone's "AI" fallback is heuristic, not LLM.** `parse_cards_from_html()` (`stepstone.py` L123-137) calls `AIScraperExtractor._fallback_heuristic_extractor()` when no cards parse. That is a regex parser, so no model is invoked. It can create one job from arbitrary page text, titled with the search term, when the page matches words like "developer" or "salary". This conflicts with the later real-data rule (REQ-DAT-01) and should be reviewed.
- **`ScraperPipeline` does not run AI extraction on job detail pages.** `AIScraperExtractor.extract_from_html()` is never called.
- **`use_ai_scraping` toggle was not added.** There is no such key in `AppSettings` (`app/db/models.py`), `Settings`, or seeded defaults. Strategist use is unconditional.
- Backward compatibility with JobSpy and CSS fast paths holds.

## Verification
- `tests/run_phase17.py tests/test_stepstone.py tests/test_scraper_pipeline.py tests/test_scheduler.py tests/test_ai_scraping.py`: passed. Phase 9 group: 24 passed.
- `test_stepstone_ai_dom_fallback` passes but exercises only the heuristic path.

## Self-Check: PARTIAL
- `AIQueryStrategist` wired in scheduler FOUND
- LLM extraction in StepStone/pipeline NOT FOUND
- `use_ai_scraping` NOT FOUND
