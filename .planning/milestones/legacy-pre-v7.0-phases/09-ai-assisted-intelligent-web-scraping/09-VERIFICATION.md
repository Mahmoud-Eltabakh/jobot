---
phase: 09-ai-assisted-intelligent-web-scraping
verified: 2026-10-28T01:15:00Z
status: human_needed
score: 10/10 must-haves verified offline (1 override); live extraction not exercised
verified_truths: 9
total_truths: 10
behavior_unverified: 0
overrides_applied: 1
overrides:
  - must_have: "Query strategist adds caching and fallback heuristics"
    reason: "Fallback heuristics are deliberately replaced by typed provider errors (REQ-DAT-01 real-data policy). A cache is not implemented: queries depend on profile, blacklist and feedback state, so staleness risk outweighs the saved model call."
    accepted_by: "gap-closure 2026-10-28"
requirements_verified: []
requirements_with_gaps: []
gaps: []  # closed 2026-10-28 (see Gap Closure); strategist cache is an accepted deviation (see override)
deferred: []
human_verification:
  - test: "With a throwaway account, enable the AI extraction toggle and scrape StepStone with a local scraping model."
    expected: "A card-less page yields one real listing or nothing; spam pages are discarded; model outage fails the task visibly."
    why_human: "Only mocked Playwright/AI were exercised; no live page or model output was checked."
covered_files:
  - ".planning/phases/09-ai-assisted-intelligent-web-scraping/09-01-PLAN.md"
  - ".planning/phases/09-ai-assisted-intelligent-web-scraping/09-01-SUMMARY.md"
  - ".planning/phases/09-ai-assisted-intelligent-web-scraping/09-02-PLAN.md"
  - ".planning/phases/09-ai-assisted-intelligent-web-scraping/09-02-SUMMARY.md"
  - ".planning/phases/09-ai-assisted-intelligent-web-scraping/09-03-PLAN.md"
  - ".planning/phases/09-ai-assisted-intelligent-web-scraping/09-03-SUMMARY.md"
  - ".planning/phases/09-ai-assisted-intelligent-web-scraping/09-04-PLAN.md"
  - ".planning/phases/09-ai-assisted-intelligent-web-scraping/09-04-SUMMARY.md"
  - "README.md"
  - "app/db/models.py"
  - "app/queue/worker.py"
  - "app/scrapers/ai_extractor.py"
  - "app/scrapers/query_strategist.py"
  - "app/scrapers/scheduler.py"
  - "app/scrapers/stepstone.py"
  - "docs/USER_MANUAL.md"
  - "templates/components/settings.html"
  - "tests/test_ai_scraping.py"
  - "tests/test_stepstone.py"
covered_digest: "v3:sha256:3c5c7d01cbbc9f3d18b6ec410f2f160f11079f9320790300533bd03b0c85f523"
audit_acknowledged:
  milestone: v7.0
  at: 2026-10-28
  status: human_needed
---

# Phase 9: AI-Assisted Intelligent Web Scraping Verification Report

**Phase Goal:** Implement AI-assisted web scraping with dynamic DOM/HTML extraction, intelligent Boolean search query generation, and spam filtering.
**Verified:** 2026-10-28T01:15:00Z
**Status:** human_needed
**Re-verification:** No, initial independent verification. The plans carry no `must_haves` frontmatter, so truths come from plan Objectives and Tasks plus the ROADMAP goal.

## Verdict

Query generation is live and tested. **Dynamic DOM/HTML extraction and spam filtering exist as a tested library but are not used by any scraping path**, and the planned toggle does not exist. Two of the three goal clauses are therefore not delivered in the running product.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `AIScraperExtractor` parses HTML/text into a structured listing with the planned schema | VERIFIED | `ai_extractor.py` `AIExtractedJobListing` and `extract_from_html`; tests pass. |
| 2 | HTML-to-clean-text preprocessing reduces tokens | VERIFIED | `clean_html_to_markdown_text` strips script/style/nav/footer/svg/noscript/iframe, caps 8000 chars; tested. |
| 3 | Spam/promotional listings are discarded | VERIFIED (function level) | `is_legitimate_job == false` returns `None`; `test_ai_scraper_extractor_spam_filter`. Not reached in production (truth 7). |
| 4 | `AIQueryStrategist` generates platform-tuned queries from skills, titles and blacklist | VERIFIED | `query_strategist.py`; used at `scheduler.py` L169 and `worker.py` L316. Platform tuning is prompt-only. |
| 5 | Strategist caching and fallback heuristics | PARTIAL | No cache; fallback intentionally replaced by typed errors. |
| 6 | StepStone uses `AIScraperExtractor` on CSS failure | FAILED | Heuristic regex only; see gap 1. |
| 7 | `ScraperPipeline` runs AI extraction on detail pages | FAILED | No call to `extract_from_html` outside tests. |
| 8 | `use_ai_scraping` toggle in settings | FAILED | Not present anywhere. |
| 9 | Backward compatibility with JobSpy and fast-path selectors | VERIFIED | Override-keyword path unchanged; `tests/test_stepstone.py` and scheduler tests pass. |
| 10 | Settings UI toggle and tests/docs | PARTIAL / FAILED (toggle) | `tests/test_ai_scraping.py` exists and passes; settings card is static; no USER_MANUAL section; README mentions the strategist. |

**Score:** 5/10 truths verified (1, 2, 3, 4, 9). Truth 5 is partial; truths 6, 7, 8, 10 are failed or partial and not counted.

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `app/scrapers/ai_extractor.py` | ORPHANED | Substantive; no production caller of the LLM path. |
| `app/scrapers/query_strategist.py` | VERIFIED | Wired and tested. |
| `app/scrapers/stepstone.py` | VERIFIED (unchanged fast path) / STUB for AI fallback | Heuristic only. |
| `templates/components/settings.html` card | STUB | Static markup, not a control. |
| `tests/test_ai_scraping.py` | VERIFIED | 394 lines, passing. |

### Key Link Verification

| From | To | Status | Details |
|------|----|--------|---------|
| `ScraperPipeline` / `QueueWorker` | `AIQueryStrategist` | WIRED | |
| `StepStoneScraper` | `AIScraperExtractor.extract_from_html` | NOT_WIRED | Calls the heuristic private method only. |
| Scrape path | `AIScraperExtractor.extract_from_html` | NOT_WIRED | |
| Settings UI | `use_ai_scraping` | NOT_WIRED | Setting does not exist. |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data? | Status |
|----------|------|--------|-----------|--------|
| Strategist queries | LLM output validated against profile and rules | Owner-scoped scraping client | Yes | FLOWING |
| Extracted job listings | LLM extraction | None in production | n/a | DISCONNECTED |
| StepStone CSS-miss job | regex over page text, title = search term | Heuristic | Not real extraction | STATIC/synthetic risk |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 9 tests | `python tests/run_phase17.py tests/test_ai_scraping.py tests/test_stepstone.py tests/test_scraper_pipeline.py tests/test_scheduler.py -q` | 24 passed in 7.20s | PASS |
| Full suite | `python tests/run_phase17.py tests -q` | 496 passed in 60.30s | PASS |

Disposable storage and a network guard were used; production `data/` was not touched. Test mocks do not prove model behavior; no live provider was called.

### Requirements Coverage

No `requirements:` frontmatter in the Phase 9 plans and no Phase 9 section in REQUIREMENTS.md. The relevant cross-cutting rule is REQ-DAT-01 (no synthetic fallbacks). The StepStone heuristic is a risk against it (see Anti-Patterns).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/scrapers/stepstone.py` | 123-137 | Heuristic job built from page text, titled with the search term | Warning to Blocker for REQ-DAT-01 | Can store a fabricated listing on a non-results page. |
| `templates/components/settings.html` | ~302-325 | Static "Active" badge, overstated copy | Warning | UI claims a capability that is not live. |
| `app/scrapers/ai_extractor.py` | `extract_from_html` | Orphaned LLM path | Warning | Central deliverable unused. |

### Deferred Items

None. No later roadmap phase schedules wiring of the extractor or the toggle.

### Gaps Summary

The AI query half of the phase is real. The extraction half stopped at library code plus tests. Fix by wiring `extract_from_html` into detail-page or CSS-miss handling with the owner's scraping client (which also removes the fabricated-job risk), adding a real `use_ai_scraping` setting and control, and correcting the Settings copy and docs. The strategist's missing cache and removed fallback need an override or a decision.

---

_Verified: 2026-10-28T01:15:00Z_
_Verifier: the agent (gsd-verifier)_

## Gap Closure (2026-10-28)

Closed in code, with tests in `tests/test_ai_scraping.py` (Playwright and AI mocked):

- The regex heuristic cited in gap 1 had already been removed (card miss returned no jobs). `StepStoneScraper.scrape` now takes `ai_client`; on a card miss it calls `AIScraperExtractor.extract_from_html` (first production caller). Spam is discarded; provider failure propagates as `AIProviderError` instead of an empty success.
- `use_ai_scraping` is a per-user setting (default off), saved by `POST /api/settings/ai-scraping`; `QueueWorker._handle_scrape_query` and `ScraperPipeline.run_full_pipeline` pass the owner's scraping client to StepStone only when it is on.
- The Settings card is a real toggle with a badge that reflects the saved value; the overstated "Dynamic DOM Extractor" copy was replaced.

Still open: extraction covers only StepStone with a single-listing result per page (no multi-card AI extraction), and AI output quality on live pages is unverified (human check above). Residual closure 2026-10-28: `docs/USER_MANUAL.md` section 9 now documents the toggle; the strategist cache is recorded as an accepted override (frontmatter).
