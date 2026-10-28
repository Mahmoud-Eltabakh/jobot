# Phase 3: Multi-Source Scraping Engine, Filter Pipeline & Background Worker - Research

## Overview
Phase 3 builds the automated job acquisition engine for Jobot. It coordinates multi-source job extraction from **LinkedIn**, **Google Jobs**, and **StepStone**, passes raw listings through a **Title & Keyword Pre-Filter Pipeline** to eliminate unwanted roles, deduplicates positions via normalized SHA-256 hashes, stores records in SQLite, triggers AI scoring, and orchestrates periodic executions using **APScheduler**.

## Technical Architecture & Scraping Strategies

### 1. Multi-Source Scraping Pipeline
- **JobSpy (`python-jobspy`)**:
  - Handles **LinkedIn** and **Google Jobs** (plus optional Indeed/Glassdoor) out-of-the-box.
  - Automatically manages user agents, proxy support, pagination, request throttling, and anti-blocking headers.
  - Returns structured pandas `DataFrame` / dict records (`title`, `company`, `location`, `job_url`, `description`, `min_amount`, `max_amount`, `currency`, `is_remote`, `date_posted`).
- **Dedicated StepStone Playwright Scraper (`app/scrapers/stepstone.py`)**:
  - Headless Chromium crawler targeting StepStone (`stepstone.de` / `stepstone.com`).
  - Handles cookie consent dialogs (`#ccmgt_explicit_accept`), dynamic job card traversal, pagination buttons, salary badges, and full job detail description scraping.
  - Uses stealth headers and humanized jitter delays (2–5 seconds) to prevent anti-bot blocking (STRIDE T-06).

### 2. Normalized Deduplication & Storage (`app/scrapers/dedup.py`)
- **Deduplication Hash Algorithm**:
  $$\text{dedup\_hash} = \text{SHA256}(\text{normalize}(\text{company}) + "|" + \text{normalize}(\text{title}) + "|" + \text{normalize}(\text{location}))$$
- Prevents database duplicate records across different platforms or repeated search runs.

### 3. Title & Keyword Pre-Filter Pipeline (`app/scrapers/filter_pipeline.py`)
- **Purpose**: Fast regex and substring evaluation against active `FilterRule` records in SQLite *before* calling the LLM evaluation agent.
- **Rule Types**:
  1. `title`: Blacklists terms like `"Senior Staff"`, `"Lead"`, `"Director"`, `"Intern"`, `"Principal"`.
  2. `company`: Blacklists specific companies/agencies.
  3. `keyword`: Blacklists terms in description like `"C1 German"`, `"No Remote"`, `"PHP"`, `"Unpaid"`.
- **Action**: Matched jobs are marked as `JobStatus.NOT_A_FIT` with reasons logged without consuming LLM inference tokens.

### 4. Background Scheduling & Manual Trigger (`app/scrapers/scheduler.py`)
- **APScheduler**: `AsyncIOScheduler` executing background scrape cycles at configurable intervals (e.g., 6, 12, or 24 hours loaded from `AppSettings`).
- **Orchestration**:
  1. Scrape jobs from configured `SearchConfig` entries across LinkedIn, Google Jobs, and StepStone.
  2. Deduplicate and filter out blacklisted jobs.
  3. Insert valid jobs into SQLite database.
  4. Automatically queue and run AI evaluation (`JobEvaluator.evaluate_and_update_job()`) for new positions.
- **On-Demand "Scrape Now"**: REST API endpoint `POST /api/scrapers/run` allowing instant trigger from the dashboard.

## Validation Architecture
- Unit tests with mock HTML and responses for JobSpy wrapper (`tests/test_scrapers.py`).
- Dedicated StepStone parser and DOM extraction tests (`tests/test_stepstone.py`).
- Pre-filter pipeline rule matching tests (`tests/test_filter_pipeline.py`).
- Deduplication and SQLite persistence tests (`tests/test_scraper_pipeline.py`).
- Background scheduler lifecycle tests (`tests/test_scheduler.py`).
- Expected test suite runtime: < 4 seconds.
