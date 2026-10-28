---
phase: 02-cv-parsing-and-pluggable-ai-matching-engine
verified: 2026-10-28T02:00:00Z
status: passed
score: 9/9 must-haves verified
verified_truths: 9
total_truths: 9
behavior_unverified: 0
overrides_applied: 0
gaps: []
deferred: []
human_verification: []
covered_files:
  - ".planning/phases/02-cv-parsing-and-pluggable-ai-matching-engine/02-01-PLAN.md"
  - ".planning/phases/02-cv-parsing-and-pluggable-ai-matching-engine/02-01-SUMMARY.md"
  - ".planning/phases/02-cv-parsing-and-pluggable-ai-matching-engine/02-02-PLAN.md"
  - ".planning/phases/02-cv-parsing-and-pluggable-ai-matching-engine/02-02-SUMMARY.md"
  - ".planning/phases/02-cv-parsing-and-pluggable-ai-matching-engine/02-03-PLAN.md"
  - ".planning/phases/02-cv-parsing-and-pluggable-ai-matching-engine/02-03-SUMMARY.md"
  - "app/ai/client.py"
  - "app/ai/cv_parser.py"
  - "app/ai/embeddings.py"
  - "app/ai/evaluator.py"
  - "app/ai/profile_extractor.py"
  - "tests/test_ai_client.py"
  - "tests/test_cv_parser.py"
  - "tests/test_embeddings.py"
  - "tests/test_evaluator.py"
covered_digest: "v3:sha256:dd2302f6b4594bd1c338c85d88f98147e356775a0bc431b005b332c487bf435e"
---

# Phase 2: CV Parsing & Pluggable AI Matching Engine Verification Report

**Phase Goal:** Parse PDF/DOCX CVs into a validated profile, embed it, and score jobs through a pluggable AI client.
**Verified:** 2026-10-28T02:00:00Z
**Status:** passed
**Re-verification:** No, initial verification.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | PDF and DOCX parse to structured text | VERIFIED | `cv_parser.py`; `test_cv_parser.py` passes. |
| 2 | Over 5 MB or bad magic bytes rejected | VERIFIED | `cv_parser.py:14-39` (`MAX_FILE_SIZE`, `%PDF-`, `PK\x03\x04`). |
| 3 | Normalized `ExtractedProfile` updates `UserProfile` | VERIFIED | `profile_extractor.py` wired to the parser and client. |
| 4 | Profile chunks embedded into `cv_profile` | VERIFIED | `embeddings.py:143-155`. Evolved: local-vector validation before upsert (atomic). |
| 5 | Cosine similarity job vs profile | VERIFIED | `compute_semantic_similarity` converts Chroma distance to similarity. |
| 6 | `BaseAIClient` unifies Ollama and cloud behind `generate()` and `embed()` | VERIFIED | `client.py` (701 lines, many providers); `test_ai_client.py` passes. |
| 7 | Evaluation returns validated 0-100 breakdown | VERIFIED | `evaluator.py` Pydantic fields `ge=0, le=100`; score clamped at line 220. |
| 8 | Prompt injection isolation via XML delimiters | VERIFIED | `evaluator.py:153,203` `<job_description>` with an ignore-instructions guard. |
| 9 | Evaluator updates `Job` fit fields | VERIFIED | `evaluator.py:662-` loads and persists per owner. |

**Score:** 9/9 truths verified (0 behavior-unverified).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase tests | `python tests/run_phase17.py <20 files> -q` | 424 passed in 35.55s | PASS |

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `app/ai/embeddings.py` | Fixed ids `profile_*`; no owner in id, metadata or query | Warning | Multi-user leak. Recorded as the Phase 15 gap; single-user behavior is correct. |

### Human Verification Required

None.

### Gaps Summary

No Phase 2 gaps. The shared `cv_profile` collection issue arrived with the multi-user model and is tracked in `15-VERIFICATION.md`.

---

_Verified: 2026-10-28T02:00:00Z_
_Verifier: the agent (gsd-verifier)_
