---
phase: 02-cv-parsing-and-pluggable-ai-matching-engine
plan: 01
subsystem: cv-ingestion
tags:
  - pdfplumber
  - pypdf
  - profile-extractor
  - pydantic
  - security
dependency_graph:
  requires:
    - "01-02"
  provides:
    - app.ai.cv_parser
    - app.ai.profile_extractor
  affects:
    - app.ai.embeddings
    - app.api
tech_stack:
  added:
    - pdfplumber 0.11.x
    - pypdf 5.1.x
    - pydantic 2.9.x
key_files:
  created:
    - app/ai/__init__.py
    - app/ai/cv_parser.py
    - app/ai/profile_extractor.py
    - tests/test_cv_parser.py
decisions:
  - Enforced a strict 5MB upload size limit and magic bytes inspection (`%PDF-`, `PK\x03\x04`) for security (STRIDE T-02).
  - Used `pdfplumber` layout extraction to prevent multi-column word scrambling, with `pypdf` fallback.
  - Implemented `ExtractedProfile` Pydantic schema with regex-based heuristic fallback for offline operation.
  - Added database persistence helper `save_profile_to_db()` for SQLite `UserProfile`.
status: complete
---

# Phase 02 Plan 01: CV Document Parsing & Profile Extraction Summary

Secure PDF/DOCX CV text parser, structured candidate profile extractor (`ExtractedProfile`), and SQLite persistence layer.

## What Was Done
1. **CV Document Parser (`app/ai/cv_parser.py`)**:
   - Implemented `CVParser` with file size validation (max 5MB) and header magic bytes check.
   - Text extraction using `pdfplumber` for multi-column layout preservation with `pypdf` fallback.
   - XML-based DOCX paragraph extraction without external C dependencies.
   - Whitespace and non-printable control character sanitization.
2. **Structured Profile Extractor (`app/ai/profile_extractor.py`)**:
   - Defined `ExtractedProfile` schema (`full_name`, `summary`, `skills`, `experience_years`, `target_titles`, `target_locations`, `target_salary_min`).
   - Async `extract_profile_from_text()` with LLM extraction and regex heuristic fallback.
   - Database persistence in `save_profile_to_db()` storing profile fields and raw text in SQLite `UserProfile`.
3. **Automated Test Suite (`tests/test_cv_parser.py`)**:
   - Tested valid TXT/PDF parsing, file size limit rejection, corrupted magic byte rejection, heuristic fallback, and database persistence (7 passing tests).

## Deviations from Plan
- None - plan executed as specified.

## Verification
- `pytest tests/test_cv_parser.py` passed 7/7 tests in 1.44s.

## Self-Check: PASSED
- `app/ai/cv_parser.py` FOUND
- `app/ai/profile_extractor.py` FOUND
- `tests/test_cv_parser.py` FOUND
