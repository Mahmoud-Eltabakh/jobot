# Phase 2: CV Parsing & Pluggable AI Matching Engine - Research

## Overview
Phase 2 builds the candidate ingestion and AI matching engine for Jobot. It ingests candidate resumes in PDF and DOCX formats, performs structured skill and experience extraction using local/cloud LLMs, embeds profile segments into an embedded ChromaDB collection, and evaluates job postings against candidate profiles returning normalized 0–100% fit scores, strengths, concerns, and missing skill gap breakdowns.

## Technical Architecture & Design Decisions

### 1. Document Parsing & Text Normalization (`pdfplumber` + `pypdf`)
- **PDF Layout Handling**: Multi-column CV layouts cause text scrambling if parsed as flat streams. `pdfplumber` preserves spatial layout, line positions, and table columns. `pypdf` is used as an ultra-fast fallback for single-column resumes.
- **DOCX Parsing**: `docx2txt` / `python-docx` for extracting structured text from Word documents.
- **Security & DoS Protection (STRIDE T-02)**:
  - File size restricted to a maximum of 5MB.
  - Magic bytes inspection (`%PDF-` for PDFs, `PK\x03\x04` for DOCX).
  - Sanitization of non-printable ASCII and control characters before passing text to LLMs.

### 2. Pluggable AI Client Architecture (`app/ai/client.py`)
- **Abstract Provider Base**: `BaseAIClient` with standard async methods:
  - `generate(prompt: str, system_prompt: Optional[str], response_format: Optional[dict]) -> str`
  - `embed(text_or_texts: str | list[str]) -> list[float] | list[list[float]]`
  - `check_health() -> bool`
- **Supported Backends**:
  1. `OllamaAIClient`: Local asynchronous client utilizing `ollama.AsyncClient` targeting `http://localhost:11434` (Default models: `qwen2.5:7b` / `llama3.1:8b` for LLM, `nomic-embed-text` for embeddings).
  2. `OpenAICompatibleClient`: Async client utilizing `openai.AsyncOpenAI` targeting standard OpenAI endpoints or custom providers (Groq, DeepSeek, Together, OpenRouter).
- **Dynamic Configuration**: Resolves active provider, model names, base URLs, and API keys at runtime from the `AppSettings` table in SQLite, avoiding server restarts upon UI settings modifications.

### 3. Structured Output & Prompt Injection Defense (STRIDE T-01)
- **Prompt Fencing**: Strict delimiter fences (`<job_description>...</job_description>` and `<candidate_profile>...</candidate_profile>`) isolate untrusted scraped job text to defend against indirect prompt injections.
- **Pydantic Validation**:
  - `ExtractedProfile`: `full_name`, `summary`, `skills: list[str]`, `experience_years: float`, `target_titles: list[str]`, `target_locations: list[str]`, `target_salary_min: Optional[float]`.
  - `JobFitEvaluation`: `fit_score: int` (clamped between 0 and 100), `fit_summary: str`, `pros: list[str]`, `cons: list[str]`, `missing_skills: list[str]`, `recommendation: Literal["Strong Match", "Potential Match", "Not a Fit"]`.

### 4. Semantic Vector RAG Pipeline (`app/ai/embeddings.py`)
- **Profile Chunking Strategy**: Candidate profiles are chunked into three distinct semantic vector records:
  1. `summary`: General executive summary and years of experience.
  2. `skills`: Technical competencies and tool proficiencies.
  3. `experience`: Work history roles and responsibilities.
- **ChromaDB Collection**: Chunked vectors stored in `cv_profile` collection with cosine distance metric (`hnsw:space: cosine`).
- **Matching & Similarity Calculation**: Generates cosine similarity between incoming job descriptions and candidate profile vectors to serve as both an independent ranking signal and quantitative baseline for LLM evaluation.

## Validation Architecture
- Unit tests with mock files and synthetic text streams for CV parser (`tests/test_cv_parser.py`).
- Embedding generation and ChromaDB vector search tests (`tests/test_embeddings.py`).
- Pluggable AI Client unit tests and mocked fit evaluator tests (`tests/test_ai_client.py`, `tests/test_evaluator.py`).
- Expected test suite runtime: < 4 seconds.
