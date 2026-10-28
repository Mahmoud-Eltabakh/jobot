---
phase: 14-experience-education-and-project-signal-scoring
plan: 03
subsystem: scoring-pipeline
tags:
  - evaluator
  - rescoring
  - settings
dependency_graph:
  requires:
    - "14-01"
    - "14-02"
  provides:
    - app.ai.evaluator.JobEvaluator.rescore_all_jobs
  affects: []
key_files:
  created: []
  modified:
    - app/ai/evaluator.py
    - app/api/settings.py
    - app/web/routes.py
    - templates/components/settings.html
status: complete
---

# Phase 14 Plan 03: Scoring Pipeline & Calibration Wiring Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. **Calibration UI**: `templates/components/settings.html` has sliders for all eight weights including history, education and projects. `/web/views/settings` loads them per user, and `/api/settings/scoring-weights` saves them.
2. **Deterministic scorer** `compute_actual_skill_fit` aggregates all eight weighted factors. Direct calls with custom weights pass (`test_history_education_and_project_signals_raise_fit_score`, `test_normalized_scoring_with_custom_weights`).
3. **Rescore**: `POST /web/profile/rescore-filter` runs `rescore_all_jobs` and `purge_non_matching_jobs`.

## Deviations from Plan / Honest Gaps
- **The saved weights do not change any stored fit score.** `evaluate_and_update_job` builds a `scoring_weights` dict and never uses it. It calls `evaluate_job`, which stores the LLM's `fit_score`. `compute_actual_skill_fit` is called only inside `evaluate_job` to fill a missing breakdown, with default weights and no semantic or feedback inputs, and its score is discarded. The history, education and project factors therefore reach neither the persisted `fit_score` nor filtering, except through the profile text in the LLM prompt.
- The evaluator test asserts `>= 75` but never compares against a profile without history, and no test drives `evaluate_and_update_job` with changed weights.
- The `/api/settings/scoring-weights` test covers only the first five weights.
- **Closed 2026-10-28:** see 14-VERIFICATION.md Gap Closure; remaining caveats listed there; only history/education/project weights are applied to the stored score.

## Verification
- `tests/test_evaluator.py` and `tests/test_web_routes.py` pass; they do not cover the wiring gap.

## Self-Check: PASSED
- Sliders and persisted weights FOUND
- Weights applied to stored `fit_score` NOT FOUND
