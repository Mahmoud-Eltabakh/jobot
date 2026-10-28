---
phase: 03-multi-source-scraping-engine-filter-pipeline-and-background-worker
plan: 05
subsystem: scheduler-api
tags:
  - apscheduler
  - background-worker
  - fastapi
  - pipeline-orchestrator
dependency_graph:
  requires:
    - "03-01"
    - "03-02"
    - "03-03"
    - "03-04"
  provides:
    - app.scrapers.scheduler
    - app.api.scrapers
  affects:
    - app.main
    - app.web
tech_stack:
  added:
    - apscheduler 3.10.x
key_files:
  created:
    - app/scrapers/scheduler.py
    - app/api/__init__.py
    - app/api/scrapers.py
    - tests/test_scheduler.py
  modified:
    - app/main.py
decisions:
  - Implemented `ScraperPipeline` orchestrating scraping, deduplication, pre-filtering, and AI evaluation sequentially.
  - Initialized `APScheduler` inside FastAPI async lifespan with configurable intervals loaded from `AppSettings`.
  - Exposed `POST /api/scrapers/run` for immediate on-demand scrape triggers from the web UI.
status: complete
---

# Phase 03 Plan 05: APScheduler Background Worker & Scraper API Summary

APScheduler periodic background worker, end-to-end pipeline orchestrator, and on-demand scrape REST API endpoints.

## What Was Done
1. **Pipeline Orchestrator & Scheduler (`app/scrapers/scheduler.py`)**:
   - `ScraperPipeline.run_full_pipeline()`: Orchestrates multi-source scraping (JobSpy + StepStone), deduplication, pre-filter rule screening, and automatic AI fit evaluation.
   - `JobotScheduler`: Asynchronous periodic task scheduler using `AsyncIOScheduler` hooked into FastAPI's startup/shutdown lifespan.
2. **Scraper REST API Router (`app/api/scrapers.py`)**:
   - `POST /api/scrapers/run`: Endpoint triggering an on-demand scrape cycle in the background with customizable keywords, location, and limit.
   - `GET /api/scrapers/status`: Returns current pipeline execution state, active search configs, and statistics of the last scrape cycle.
3. **Automated Test Suite (`tests/test_scheduler.py`)**:
   - Tested pipeline coordination with mock scrapers and AI client.
   - Tested status and on-demand trigger endpoints (2 passing tests).

## Deviations from Plan
- None - plan executed as specified.

## Verification
- `pytest tests/test_scheduler.py` passed 2/2 tests in 2.57s.
- Full test suite `pytest` passed all 35 tests in 7.02s.

## Self-Check: PASSED
- `app/scrapers/scheduler.py` FOUND
- `app/api/scrapers.py` FOUND
- `tests/test_scheduler.py` FOUND
