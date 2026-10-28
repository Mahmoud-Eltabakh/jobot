---
phase: 09-ai-assisted-intelligent-web-scraping
plan: 01
subsystem: ai-extraction
tags:
  - html-cleaning
  - llm-extraction
  - pydantic
dependency_graph:
  requires:
    - "03-02"
  provides:
    - app.scrapers.ai_extractor.AIScraperExtractor
  affects:
    - app.scrapers.stepstone
key_files:
  created:
    - app/scrapers/ai_extractor.py
status: complete
---

# Phase 09 Plan 01: AI DOM & HTML Structured Job Extractor Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. `AIExtractedJobListing` (`app/scrapers/ai_extractor.py`) has all planned fields: title, company, location, is_remote, salary_min/max/currency, description, required_skills, visa_sponsorship, language_requirement, is_legitimate_job.
2. `clean_html_to_markdown_text()` strips script, style, nav, footer, svg, noscript and iframe and caps output at 8000 characters.
3. `extract_from_html()` resolves the owner's scraping-stage client, validates the JSON, returns `None` for `is_legitimate_job: false`, and raises a typed provider error for empty, malformed or identity-less output.
4. `_fallback_heuristic_extractor()` exists as the offline regex parser.

## Deviations from Plan / Honest Gaps
- **`extract_from_html()` has no production caller.** Only tests call it. The scraping paths never send listing HTML through the LLM extractor.
- Provider failures deliberately do not use the heuristic parser (later phases' real-data rule), so the "offline/mock fallback for non-AI runs" is reachable only from StepStone's CSS-miss path (see 09-03).

## Verification
- `tests/run_phase17.py tests/test_ai_scraping.py`: passed, including clean-and-extract, spam filter, owner-routing and invalid-response cases. Phase 9 group: 24 passed.

## Self-Check: PARTIAL
- `app/scrapers/ai_extractor.py` FOUND
- `extract_from_html` production call site NOT FOUND
