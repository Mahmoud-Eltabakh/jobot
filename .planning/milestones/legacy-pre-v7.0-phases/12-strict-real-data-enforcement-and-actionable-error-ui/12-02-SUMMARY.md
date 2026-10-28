---
phase: 12-strict-real-data-enforcement-and-actionable-error-ui
plan: 02
subsystem: alert-ui
tags:
  - htmx
  - alerts
dependency_graph:
  requires:
    - "12-01"
  provides: []
  affects: []
key_files:
  created: []
  modified: []
status: complete
---

# Phase 12 Plan 02: Actionable UI Diagnostics & Alert Notification System Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
**None of the three planned tasks exist.**
- `templates/components/system_alerts.html`: file does not exist.
- `templates/base.html`: no alerts include or alerts polling.
- `GET /web/components/system-alerts`: no such route in `app/web/routes.py`; no reference to `system-alerts` or `system_alerts` anywhere in `app/`, `templates/` or `tests/`.

## Related Behaviour That Does Exist
- Per-action error fragments (`provider_failure` in `app/web/routes.py`, `role="alert"` blocks in settings and the job inspector) and a profile toast (`toast_message`). These are inline responses to a user action, not a polled banner for Ollama offline, LinkedIn re-login or rate limits.
- The scoring-weight sliders in `templates/components/settings.html` (ROADMAP groups them with this plan) work and are covered by `tests/test_web_routes.py`.

## Verification
- No tests reference the plan's artifacts.

## Closed 2026-10-28
`templates/components/system_alerts.html`, `GET /web/components/system-alerts` and a polling include in `templates/base.html` (signed-in only, every 15s and on `refreshView`) now exist. Alerts come from the caller's own failed queue tasks (provider unreachable, credentials/quota, rate limit, LinkedIn login, other task failures) and a paused queue, each with an Open button. Caveat: alerts reflect recorded failures only, no live probing, so an Ollama outage shows only after a task fails. Tests in `tests/test_real_data_enforcement.py`.

## Self-Check: PASSED
- `templates/components/system_alerts.html` FOUND
- `/web/components/system-alerts` FOUND
- `base.html` live-polling include FOUND
