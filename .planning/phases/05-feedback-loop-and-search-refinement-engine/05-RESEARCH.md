# Phase 5: Feedback Loop & Search Refinement Engine - Research

## Overview
Phase 5 implements the self-improving intelligence layer of Jobot. It listens to user status updates (`applied`, `interview 1/2/3` vs. `not a good fit`, `rejected`) and candidate notes, encodes positive/negative feedback vectors in ChromaDB, applies adaptive fit score re-weighting, generates automatic blacklist suggestions (`FilterRule`), and refines scraper search parameters.

## Technical Architecture & Feedback Loops

### 1. Feedback Vector Encoding (`app/ai/feedback.py`)
- **Collection**: `VectorStore.COLLECTION_USER_FEEDBACK` ("user_feedback").
- **Embedding Strategy**:
  - Positive Vectors: Jobs progressing to `applied` or `interview` stages along with positive candidate notes.
  - Negative Vectors: Jobs transitioned to `not a good fit` or `rejected` with candidate feedback notes (e.g., "Salary too low", "Requires on-site presence", "Requires Java/Spring").
- **Vector Metadata**:
  - `job_id`: int
  - `sentiment`: "positive" | "negative"
  - `status`: str
  - `rejection_reason`: Optional[str]

### 2. Adaptive Score Re-Weighting & Similarity Penalty
- **Cosine Similarity Feedback Adjustment**:
  $$\text{Adjusted Score} = \text{Base LLM Score} + (\alpha \cdot \text{Sim}_{\text{pos}}) - (\beta \cdot \text{Sim}_{\text{neg}})$$
  where $\alpha \approx 0.05$ (positive reinforcement boost) and $\beta \approx 0.15$ to $0.25$ (negative misalignment penalty).
- If an incoming job has high cosine similarity ($\ge 0.82$) to previously rejected jobs with negative comments, its fit score is penalised and a warning tag is appended (e.g., *"Similar to previously rejected job: Requires on-site"*).

### 3. Automatic Blacklist Rule Generation (`app/ai/blacklist_suggester.py`)
- When recurring rejection patterns emerge (e.g., 3+ jobs rejected due to "German C1" or "Staff level"), an LLM summarizer extracts candidate rejection themes and suggests new `FilterRule` entries (rule_type: `title`, `keyword`, `company`).
- Candidates can review, accept, or dismiss suggested blacklist rules in the Settings panel.

### 4. Search Query Optimizer (`app/scrapers/query_optimizer.py`)
- Analyzes high-match and positive jobs to extract top-performing keywords and titles.
- Recommends or updates active `SearchConfig` keywords to maximize discovery of high-fit roles.

### 5. End-to-End Workflow Verification
- Integration test suite running the complete loop:
  1. Scrape raw jobs
  2. Apply Pre-Filter pipeline
  3. Deduplicate and store in SQLite
  4. Generate ChromaDB embeddings and LLM fit scores
  5. User marks job `not a good fit` with feedback note
  6. Feedback vector stored in ChromaDB
  7. Subsequent similar job receives penalty score and blacklist rule is suggested.

## Validation Strategy
- Unit tests for feedback vector storage and retrieval (`tests/test_feedback.py`).
- Adaptive score adjustment and penalty tests (`tests/test_score_tuning.py`).
- Automatic blacklist suggestion tests (`tests/test_blacklist_suggester.py`).
- Full End-to-End integration test suite (`tests/test_e2e_workflow.py`).
- Expected test suite runtime: < 4 seconds.
