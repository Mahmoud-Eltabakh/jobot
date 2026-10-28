---
phase: 10-persistent-task-queue-and-continuous-scraping
plan: 02
subsystem: queue-worker
tags:
  - asyncio
  - worker
  - lifespan
dependency_graph:
  requires:
    - "10-01"
  provides:
    - app.queue.worker.QueueWorker
  affects:
    - app.main
key_files:
  created:
    - app/queue/worker.py
  modified:
    - app/main.py
status: complete
---

# Phase 10 Plan 02: Async Continuous Queue Worker Loop Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. **Loops** (`app/queue/worker.py`): `QueueWorker.start()` creates a scraper loop (claims `scrape_query` and `full_discovery`) and an evaluator loop (claims `evaluate_job` and `feedback_tune`). Each polls every 2s, opens a session per claim, and survives per-iteration exceptions.
2. **Handlers**: `scrape_query` runs JobSpy sites and StepStone concurrently (with a configurable stagger delay), dedups, filters and enqueues `evaluate_job` per approved job. `evaluate_job` checks job ownership, resolves the scoring client and calls `JobEvaluator`. `full_discovery` asks `AIQueryStrategist` for queries and enqueues owner-scoped `scrape_query` tasks.
3. **Failures**: typed provider errors store a bounded diagnostic and mark the task terminal; other errors store `"Task execution failed."` and retry until `max_retries`.
4. **Lifespan** (`app/main.py`): the worker starts on startup and `stop()` runs on shutdown, skipped when `PYTEST_CURRENT_TEST` or `JOBOT_TESTING` is set.

## Deviations from Plan / Honest Gaps
- **In-flight safety is not met.** `stop()` cancels the loops. `CancelledError` bypasses `except Exception` in `_process_task`, so a running task stays `in_progress` and is never re-queued (probe in 10-01).
- **`feedback_tune` has no handler.** A probe enqueued one; `_process_task` logged an unknown type and then marked it `completed`. Unknown work is silently reported as done.
- **Concurrency settings are not enforced by the worker.** It runs exactly one scraper loop and one evaluator loop. `concurrency_max_scrapers/evaluators` are shown in queue stats and used only for the evaluator semaphore in `ScraperPipeline`.
- Rate limiting is limited to the `scraping_stagger_delay_seconds` delay before StepStone and the 2s poll.
- Lifespan wiring is not exercised by tests (guarded off in testing).
- **Closed 2026-10-28:** see 10-VERIFICATION.md Gap Closure; remaining caveats listed there.

## Verification
- `tests/run_phase17.py tests/test_task_queue.py tests/test_parallel_execution.py`: passed, including `test_queue_worker_task_execution` and the parallel-loop claim tests. Phase 10 group: 21 passed.

## Self-Check: PASSED
- `app/queue/worker.py` FOUND
- Lifespan start/stop FOUND
- Cancellation-safe in-flight handling NOT FOUND
