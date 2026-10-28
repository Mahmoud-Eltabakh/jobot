---
phase: 12-strict-real-data-enforcement-and-actionable-error-ui
plan: 01
subsystem: real-data-enforcement
tags:
  - scrapers
  - ai
  - error-propagation
dependency_graph:
  requires:
    - "09-01"
  provides:
    - provider-error-propagation
  affects:
    - app.scrapers.ai_extractor
    - app.scrapers.stepstone
    - app.ai.linkedin_analyzer
    - app.ai.evaluator
key_files:
  created: []
  modified:
    - app/scrapers/ai_extractor.py
    - app/scrapers/stepstone.py
    - app/ai/linkedin_analyzer.py
    - app/ai/evaluator.py
    - app/ai/client.py
status: complete
---

# Phase 12 Plan 01: Runtime Mock Elimination & Strict Live Data Enforcement Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. **AI extractor / evaluator / LinkedIn analyzer**: `AIScraperExtractor.extract_from_html`, `JobEvaluator.evaluate_job`, `LinkedInProfileAnalyzer.analyze_profile_text` and the generation clients re-raise `AIProviderError` or wrap other failures in a sanitized `_provider_error`; none substitutes synthetic output. `MockAIClient` exists but is not reachable from `get_ai_client` or any `app/` caller.
2. **LinkedIn analyzer** raises actionable `ValueError`s for a missing cookie, an invalid URL and an authwall/privacy gate.
3. `test_scraping_provider_failure_is_not_synthetic_success` passes.

## Deviations from Plan / Honest Gaps
- **StepStone still fabricates a listing.** When card parsing finds nothing, `app/scrapers/stepstone.py` calls `AIScraperExtractor._fallback_heuristic_extractor`, which takes the first two text lines as title and company (or the search term as title) and returns a `ScrapedJob`. The "invalid title" filter only blocks a few phrases.
- `extract_from_html` uses `https://example.com/job` when no source URL is given.
- **Closed 2026-10-28:** `_fallback_heuristic_extractor` and the StepStone call to it were removed (no cards means no jobs, with a warning log); the `https://example.com/job` default was removed (`url` is now the real source URL or empty). Covered by `tests/test_real_data_enforcement.py`; `test_stepstone_unstructured_markup_yields_no_fabricated_job` replaces the old fallback test. See 12-VERIFICATION.md.
- Remaining: `extract_profile_from_text` still has a regex fallback when `ai_client=None` (no app caller does this). An empty URL from the extractor is not rejected downstream.

## Verification
- `tests/run_phase17.py tests/test_stepstone.py tests/test_ai_scraping.py tests/test_evaluator.py ...`: passed. No test covers the StepStone heuristic fallback.

## Self-Check: PASSED
- Provider-error propagation FOUND
- Removal of synthetic job generation FOUND (verified by test)
