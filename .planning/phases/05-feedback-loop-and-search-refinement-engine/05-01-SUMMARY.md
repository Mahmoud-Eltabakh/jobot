---
phase: 05-feedback-loop-and-search-refinement-engine
plan: 01
subsystem: feedback-loop
tags:
  - feedback-vectors
  - chromadb
  - score-adjustment
  - sentiment
dependency_graph:
  requires:
    - "01-03"
    - "02-03"
  provides:
    - app.ai.feedback
  affects:
    - app.ai.evaluator
    - app.web
tech_stack:
  added:
    - chromadb
    - numpy
key_files:
  created:
    - app/ai/feedback.py
    - tests/test_feedback.py
decisions:
  - Encoded positive reactions (`applied`, `interview 1/2/3`) and negative rejections (`not a good fit`, `rejected`) in ChromaDB `user_feedback`.
  - Implemented `compute_feedback_score_adjustment()` applying positive fit bonuses (up to +10%) and negative similarity penalties (up to -25%).
status: complete
---

# Phase 05 Plan 01: Feedback Vector Recording & Adaptive Re-weighting Summary

ChromaDB candidate feedback vector recording and dynamic fit score re-weighting module.

## What Was Done
1. **FeedbackManager (`app/ai/feedback.py`)**:
   - `record_job_feedback()`: Composes semantic text from job attributes and candidate feedback notes, embeds via `ai_client.embed()`, and upserts into `VectorStore.COLLECTION_USER_FEEDBACK` with metadata.
   - `compute_feedback_score_adjustment()`: Evaluates cosine similarity against stored feedback vectors to calculate positive bonuses and negative score penalties.
2. **Automated Test Suite (`tests/test_feedback.py`)**:
   - Verified feedback vector insertion, collection counting, and penalty delta computation against disliked role traits (2 passing tests).

## Deviations from Plan
- None - plan executed as specified.

## Verification
- `pytest tests/test_feedback.py` passed 2/2 tests in 0.30s.

## Self-Check: PASSED
- `app/ai/feedback.py` FOUND
- `tests/test_feedback.py` FOUND
