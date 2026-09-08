---
phase: 02
slug: 02-cv-parsing-and-pluggable-ai-matching-engine
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-09-07
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_cv_parser.py tests/test_embeddings.py tests/test_ai_client.py tests/test_evaluator.py -q` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick test suite
- **After every plan wave:** Run full test suite `pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | REQ-CV-01 | T-02 | Validate PDF magic bytes & 5MB file limit | unit | `pytest tests/test_cv_parser.py` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | REQ-CV-03 | T-01 | Normalize profile to ExtractedProfile schema | unit | `pytest tests/test_cv_parser.py` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | REQ-CV-04 | T-05 | Chunk and embed candidate profile | unit | `pytest tests/test_embeddings.py` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | REQ-DB-02 | T-01 | ChromaDB cosine similarity ranking | integration | `pytest tests/test_embeddings.py` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 1 | REQ-AI-01 | T-07 | BaseAIClient multi-provider resolution | unit | `pytest tests/test_ai_client.py` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 1 | REQ-AI-02 | T-01 | Evaluate job fit with prompt fencing | unit | `pytest tests/test_evaluator.py` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cv_parser.py` — unit tests for CVParser and ExtractedProfile
- [ ] `tests/test_embeddings.py` — unit tests for ProfileEmbedder and ChromaDB RAG
- [ ] `tests/test_ai_client.py` — unit tests for BaseAIClient, OllamaAIClient, OpenAICompatibleClient
- [ ] `tests/test_evaluator.py` — unit tests for JobEvaluator and JobFitEvaluation schema

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
