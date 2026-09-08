---
phase: 04-modern-web-dashboard-and-job-tracker-ui
plan: 04
subsystem: job-inspector
tags:
  - job-inspector
  - slide-over-drawer
  - ai-breakdown
  - notes-editor
dependency_graph:
  requires:
    - "04-01"
    - "04-02"
  provides:
    - templates.components.job_inspector
  affects:
    - app.web
tech_stack:
  added:
    - htmx
    - jinja2
key_files:
  created:
    - templates/components/job_inspector.html
decisions:
  - Implemented slide-over drawer showing full job description, AI match score breakdown (pros, cons, missing skills), external application link, and candidate notes editor.
  - Implemented `POST /api/jobs/{id}/notes` storing feedback notes with sentiment tags.
status: complete
---

# Phase 04 Plan 04: Job Inspector Drawer & Notes Editor Summary

Split-pane Job Inspector drawer displaying complete job descriptions, AI match breakdowns, external application buttons, and interactive candidate notes.

## What Was Done
1. **Job Inspector Drawer (`templates/components/job_inspector.html`)**:
   - Slide-over container with close triggers and dark backdrop.
   - AI Evaluation card displaying 0–100% score gauge, fit summary, strengths checklist, concerns list, and missing skill badges.
   - Full job description section.
   - Candidate notes editor with sentiment selection (Positive, Neutral, Negative) and live timeline updates.
2. **Backend Endpoints (`app/web/routes.py`)**:
   - `GET /web/job/{id}/inspect`: Fetches job details, parsed pros/cons, notes, and history.
   - `POST /api/jobs/{id}/notes`: Saves new `FeedbackNote` and re-renders note timeline.

## Verification
- `pytest tests/test_htmx_views.py` verified inspector rendering and notes submission.
