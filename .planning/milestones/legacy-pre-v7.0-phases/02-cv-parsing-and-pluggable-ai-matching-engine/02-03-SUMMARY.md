---
phase: 02-cv-parsing-and-pluggable-ai-matching-engine
plan: 03
subsystem: ai-evaluator
tags:
  - ollama
  - openai
  - job-evaluator
  - prompt-engineering
  - structured-output
dependency_graph:
  requires:
    - "01-02"
  provides:
    - app.ai.client
    - app.ai.evaluator
  affects:
    - app.ai.embeddings
    - app.web
tech_stack:
  added:
    - ollama 0.4.x
    - openai 1.57.x
    - pydantic 2.9.x
key_files:
  created:
    - app/ai/client.py
    - app/ai/evaluator.py
    - tests/test_ai_client.py
    - tests/test_evaluator.py
decisions:
  - Abstracted AI providers under `BaseAIClient` supporting local `ollama.AsyncClient` and cloud `openai.AsyncOpenAI`.
  - Implemented dynamic database configuration resolution via `AppSettings` in SQLite.
  - Implemented `JobFitEvaluation` schema ensuring 0-100% score bounds, pros, cons, and missing skill gap lists.
  - Hardened prompts with XML delimiter fences (`<job_description>`, `<candidate_profile>`) against prompt injection attacks (STRIDE T-01).
status: complete
---

# Phase 02 Plan 03: Pluggable AI Client & Job Fit Evaluator Summary

Unified multi-provider AI client supporting Local Ollama and OpenAI-compatible Cloud APIs, coupled with a hardened Job Evaluator agent returning structured fit scoring (0–100%).

## What Was Done
1. **Pluggable AI Client (`app/ai/client.py`)**:
   - `BaseAIClient`: Abstract interface with async `generate()`, `embed()`, and `check_health()`.
   - `OllamaAIClient`: Async client for local Ollama instances (`qwen2.5:7b`, `nomic-embed-text`).
   - `OpenAICompatibleClient`: Async client for OpenAI / Groq / custom endpoints.
   - `MockAIClient`: Deterministic mock client for offline tests.
   - `get_ai_client()`: Dynamic factory resolving active settings from SQLite `AppSettings`.
2. **Job Fit Evaluator Agent (`app/ai/evaluator.py`)**:
   - `JobFitEvaluation`: Pydantic schema with integer fit score (0–100), summary, pros, cons, missing skills, and recommendation category.
   - `JobEvaluator.evaluate_job()`: Enforces XML delimiter fences for prompt injection defense (STRIDE T-01).
   - `JobEvaluator.evaluate_and_update_job()`: Updates `Job` record in SQLite with fit score, pros, cons, and missing skills JSON.
3. **Automated Test Suite**:
   - `tests/test_ai_client.py`: Tests client resolution, healthchecks, and embeddings.
   - `tests/test_evaluator.py`: Tests evaluation validation, mock client scoring, and SQLite updates (5 passing tests).

## Deviations from Plan
- None - plan executed as specified.

## Verification
- `pytest tests/test_ai_client.py tests/test_evaluator.py` passed 5/5 tests in 2.10s.

## Self-Check: PASSED
- `app/ai/client.py` FOUND
- `app/ai/evaluator.py` FOUND
- `tests/test_ai_client.py` FOUND
- `tests/test_evaluator.py` FOUND
