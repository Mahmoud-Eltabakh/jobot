# Phase 10: Persistent SQLite Task Queue & Continuous Scraping Worker

## Executive Summary
Provides a persistent SQLite async job queue for scraping targets, AI fit evaluations, and feedback tuning. Ensures continuous, resilient job discovery that persists across application restarts with zero external dependencies (no Redis/Celery required).

## Architecture & Workflows
1. **Queue Schema (`ScrapeTask`)**:
   - `id`, `task_type` (`scrape_query`, `evaluate_job`, `feedback_tune`), `payload_json`, `status` (`pending`, `in_progress`, `completed`, `failed`), `retries`, `max_retries`, `error_message`, `created_at`, `updated_at`, `completed_at`.
2. **Continuous Async Worker Loop**:
   - Background daemon polling `ScrapeTask` queue every few seconds with concurrency limiting and backoff.
3. **Queue Monitoring UI & API**:
   - `GET /api/queue/status` & `POST /api/queue/retry-failed`
   - Real-time queue activity indicator in top navigation bar and dashboard.
