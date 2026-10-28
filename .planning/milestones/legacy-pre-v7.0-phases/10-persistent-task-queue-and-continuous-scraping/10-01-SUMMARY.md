---
phase: 10-persistent-task-queue-and-continuous-scraping
plan: 01
subsystem: task-queue
tags:
  - sqlite
  - sqlmodel
  - queue
dependency_graph:
  requires:
    - "01-02"
  provides:
    - app.db.models.ScrapeTask
    - app.queue.task_queue.TaskQueue
  affects:
    - app.queue.worker
    - app.api.queue
key_files:
  created:
    - app/queue/task_queue.py
  modified:
    - app/db/models.py
    - app/db/database.py
status: complete
---

# Phase 10 Plan 01: ScrapeTask Data Model & SQLite Queue Storage Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. **Model** (`app/db/models.py`): `ScrapeTask` (`scrape_tasks`) has `user_id`, `task_type`, `payload_json`, `status`, `retries`, `max_retries`, `error_message`, timestamps and `completed_at`. `user_id`, `task_type` and `status` are indexed.
2. **Schema** (`app/db/database.py`): `init_db()` creates the table via `create_all`; `migrate_sqlite_columns()` adds `user_id` to existing `scrape_tasks`.
3. **TaskQueue** (`app/queue/task_queue.py`): `enqueue` (task-type allowlist, 64 KiB payload cap, owner id), `claim_next_task` (oldest pending, atomic conditional `UPDATE ... WHERE status='pending'`, backoff on "database is locked", honours pause), `mark_completed`, `mark_failed` (back to pending until `max_retries`, or terminal), `retry_task`, `retry_all_failed`, `delete_task`, `clear_*`, `get_stats`.

## Deviations from Plan / Honest Gaps
- **No recovery of stranded `in_progress` tasks.** Probe in disposable storage: after claiming a task, a fresh session's `claim_next_task` returned `None` while stats showed `in_progress: 1`. A crash or shutdown mid-task leaves the row stuck indefinitely until a manual retry.
- State transitions are not guarded (`mark_completed` and `mark_failed` do not check the current status).
- `feedback_tune` is in the allowlist but has no handler (see 10-02).
- **Closed 2026-10-28:** see 10-VERIFICATION.md Gap Closure; remaining caveats listed there.

## Verification
- `tests/run_phase17.py tests/test_task_queue.py tests/test_parallel_execution.py tests/test_htmx_views.py`: 21 passed (disposable DB, network blocked). `test_task_queue_lifecycle`, `test_queue_control_methods` and `test_provider_failure_never_commits_claimable_task` cover the manager.

## Self-Check: PASSED
- `ScrapeTask` FOUND
- `TaskQueue` FOUND
- Stale `in_progress` recovery NOT FOUND
