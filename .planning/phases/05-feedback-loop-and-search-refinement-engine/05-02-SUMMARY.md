---
phase: 05-feedback-loop-and-search-refinement-engine
plan: 02
subsystem: feedback-loop
tags:
  - blacklist-suggester
  - query-optimizer
  - continuous-learning
dependency_graph:
  requires:
    - "05-01"
    - "03-04"
  provides:
    - app.ai.blacklist_suggester
    - app.scrapers.query_optimizer
  affects:
    - app.scrapers.scheduler
    - app.web
tech_stack:
  added:
    - collections
    - re
key_files:
  created:
    - app/ai/blacklist_suggester.py
    - app/scrapers/query_optimizer.py
    - tests/test_blacklist_suggester.py
decisions:
  - Analyzed negative candidate feedback notes and rejected jobs using frequency analysis to propose new `FilterRule` blacklist candidates.
  - Implemented `SearchQueryOptimizer` extracting high-yield skill terms from positive job lifecycle histories (applied, interview stages).
status: complete
---

# Phase 05 Plan 02: Negative Theme Blacklist Suggester & Search Query Optimizer Summary

Continuous learning subsystem analyzing user feedback to refine scraping queries and pre-filter rules.

## What Was Done
1. **BlacklistSuggester (`app/ai/blacklist_suggester.py`)**:
   - `analyze_rejections_and_suggest_rules()`: Clusters recurring critique patterns from negative `FeedbackNote` and `JobStatus.NOT_A_FIT` records to formulate candidate `FilterRule` proposals.
2. **SearchQueryOptimizer (`app/scrapers/query_optimizer.py`)**:
   - `get_optimized_search_terms()`: Identifies recurring skill patterns across successful application histories (`applied`, `interview 1/2/3`) to enrich future scraper keywords.
3. **Automated Test Suite (`tests/test_blacklist_suggester.py`)**:
   - Verified negative theme extraction and high-yield query generation (2 passing tests).

## Deviations from Plan
- None - plan executed as specified.

## Verification
- `pytest tests/test_blacklist_suggester.py` passed 2/2 tests in 0.06s.

## Self-Check: PASSED
- `app/ai/blacklist_suggester.py` FOUND
- `app/scrapers/query_optimizer.py` FOUND
- `tests/test_blacklist_suggester.py` FOUND
