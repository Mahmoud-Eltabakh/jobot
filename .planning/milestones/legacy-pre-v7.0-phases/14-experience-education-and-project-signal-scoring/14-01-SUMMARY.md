---
phase: 14-experience-education-and-project-signal-scoring
plan: 01
subsystem: scoring-model
tags:
  - evaluator
  - calibration
dependency_graph:
  requires: []
  provides:
    - app.ai.evaluator.JobEvaluator.compute_actual_skill_fit
    - app.api.settings.update_scoring_weights
  affects:
    - app.ai.evaluator
key_files:
  created: []
  modified:
    - app/ai/evaluator.py
    - app/db/models.py
    - app/api/settings.py
status: complete
---

# Phase 14 Plan 01: Profile Signal Model & Scoring Design Summary

Written retrospectively from a goal-backward audit (2026-10-28).

## What Was Verified
1. **Taxonomy** (`app/ai/evaluator.py`): `ScoringBreakdown` carries `historical_skills_score`, `education_score` and `project_score`. `compute_actual_skill_fit` derives them from `Experience History`, `Education` and `Projects` sections of the candidate summary. `UserProfile` has `education_json` and `projects_json`.
2. **Configurable weights**: `POST /api/settings/scoring-weights` persists `weight_history_skills`, `weight_education` and `weight_projects` per user via `set_user_setting`; the evaluator reads them with `get_user_setting`/`get_app_setting`. The `10/5/10` figures are only defaults.

## Deviations from Plan / Honest Gaps
- No separate "seniority progression" signal. Seniority is only the title/seniority factor vs. required years.
- Project terms are all word tokens of project values, so history and project scores overlap on the same tokens.
- **Closed 2026-10-28:** see 14-VERIFICATION.md Gap Closure; remaining caveats listed there.

## Verification
- `tests/test_evaluator.py` and `tests/test_web_routes.py` pass; the weights route is asserted for the first five weights only, not the three new ones.

## Self-Check: PASSED
- Signal fields and weights FOUND
- Seniority-progression signal NOT FOUND
