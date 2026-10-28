# Research: Concurrent Background Scraping & Parallel AI Scoring Engine

## Domain Overview
Scaling a self-hosted job search pipeline from sequential task execution to high-throughput parallel execution requires balancing two distinctly constrained workloads:
1. **Scraping Pipeline (Network I/O & Browser Bound)**: Involves HTTP requests to LinkedIn/Google Jobs via `python-jobspy` and headless browser instances via Playwright for StepStone. Constraints: anti-bot rate limits, browser memory usage, and connection latency.
2. **AI Evaluation Pipeline (Compute & LLM Bound)**: Involves calling Local Ollama (GPU/NPU VRAM bound) or Cloud APIs (concurrency/token rate limit bound) and ChromaDB vector queries. Constraints: Ollama context concurrency (`OLLAMA_NUM_PARALLEL`), token latency, and GPU memory saturation.
3. **Database Concurrency (SQLite WAL Mode)**: SQLite allows multiple simultaneous readers but serializes writers. With WAL mode enabled, concurrent worker tasks must use atomic claiming, short write transactions, and exponential backoff retry on `busy_timeout`.

---

## Key Architectural Patterns & Concurrency Design

### 1. Decoupled Concurrency Pools (Scraping vs. AI Scoring)
Instead of a single sequential queue worker claiming one task at a time, implement separate concurrent worker loops:
- **Scraper Worker Pool**: Handles `scrape_query` and `full_discovery` tasks with bounded concurrency (default: 2 concurrent scraping tasks) and staggered request intervals to avoid IP blocks.
- **Scorer Worker Pool**: Handles `evaluate_job` tasks with bounded concurrency (default: 3 concurrent AI evaluations) using `asyncio.Semaphore` to batch-process newly discovered jobs.
- **Non-Blocking Task Dispatching**: Scraping network requests do not block ongoing AI evaluations, and slow LLM generations do not delay newly incoming job discoveries.

### 2. Bounded Concurrency & Ollama Optimization
- **Local Ollama Concurrency**: Ollama 0.4+ supports parallel request handling via `OLLAMA_NUM_PARALLEL` (default: 4 on multi-core / GPU systems). Bounding concurrent AI evaluations to 2–4 prevents GPU out-of-memory (OOM) errors and keeps response latency low.
- **Cloud API Rate Limiting**: For OpenAI/Groq, concurrent async `httpx` calls utilize the provider connection pool while staying safely below per-minute request limits (RPM).
- **ChromaDB Thread Safety**: In-process ChromaDB SQLite collection reads/writes are wrapped in thread-safe async locks or lightweight sessions.

### 3. SQLite Concurrency & Contention Defense
- **Atomic Task Claiming**: Use `UPDATE scrape_tasks SET status='in_progress', updated_at=:now WHERE id IN (SELECT id FROM scrape_tasks WHERE status='pending' ORDER BY created_at LIMIT 1)` within immediate transactions.
- **Busy Timeout**: Ensure SQLite connections set `PRAGMA busy_timeout = 5000;` to transparently queue concurrent writes rather than raising immediate `database is locked` errors.
- **Short Transactions**: Worker tasks do not hold SQLite transactions open during network scraping or LLM calls; transactions are used strictly for claiming, saving jobs, and marking task completion.

### 4. Dynamic Concurrency Controls & UI Monitoring
- **Runtime Persistence in UserSettings / AppSettings**:
  - `concurrency_max_scrapers`: Maximum simultaneous active scraping queries (default: 2, range: 1–5).
  - `concurrency_max_evaluators`: Maximum simultaneous AI job evaluations (default: 3, range: 1–8).
  - `scraping_stagger_delay_seconds`: Delay between concurrent job board requests (default: 1.5s).
- **Real-Time Queue Dashboard**: The AI Queue View displays active parallel tasks categorized by worker type (`Scraping` vs `AI Scoring`) with live progress indicators.

---

## Risk Assessment & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Ollama GPU VRAM Exhaustion | Failed generations / OOM crash | Bounded `asyncio.Semaphore` initialized from user concurrency settings (default: 3). |
| Job Board Rate Limiting / IP Blocks | Scraper 429 / Captcha triggers | Staggered query dispatching, independent random jitter delays (1–3s), and platform-specific session isolation. |
| SQLite `database is locked` | Task claiming or status update failures | WAL mode, `PRAGMA busy_timeout=5000`, atomic batch claiming, and exponential backoff retries. |
| Starvation of Discovery vs Scoring | Pipeline imbalance | Dedicated concurrency slots for both scraping and evaluation rather than a shared FIFO queue. |
