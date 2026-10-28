# Technology Stack

**Project:** Jobot v8.0 Production SaaS Foundation
**Researched:** 2026-10-28
**Recommendation confidence:** MEDIUM; the architecture direction is clear, but cloud region, scale, budget, AI provider, and service-level objective are undecided.

## Recommended Stack

### Core Framework

| Technology | Version / baseline | Purpose | Why |
|------------|--------------------|---------|-----|
| Python | Keep the production image's Python 3.11 baseline for beta; test upgrades before changing it | API, scraper, AI, queue worker | Existing dependencies and Playwright image are Python-native. Keep the current Python-first constraint and avoid a frontend runtime migration. |
| FastAPI + Uvicorn | Keep current compatible releases; freeze exact versions in a deployment lock | HTTP app and health endpoints | Existing routes, auth, Jinja templates, and HTMX workflows can remain. Run API and background consumers as separate container processes in hosted production. |
| SQLModel + SQLAlchemy | SQLModel's existing API; SQLAlchemy 2.0 series (official docs identify 2.0.55 as current on 2026-10-28) | Relational models and sessions | SQLModel is already built on SQLAlchemy and its session-per-request pattern supports the PostgreSQL dialect. Keep synchronous sessions initially; avoid an async ORM rewrite without measured need. |
| PostgreSQL | Managed PostgreSQL 18, or 17 if the selected provider/extension requires it | Hosted account, job, task, and usage data | A single managed relational system supports concurrent web/worker processes, transactions for account limits, backups/PITR, and a database-backed queue. PostgreSQL 18 is the current stable documentation target; do not choose a development release. |
| Alembic | Current compatible 1.x release, pinned in the lock | Versioned schema migrations | Replace startup-time `create_all` and hand-written SQLite column changes as the production schema authority. Keep migrations in the repository and run them as a release step, not concurrently from every API instance. |
| psycopg | Psycopg 3, using the SQLAlchemy PostgreSQL dialect | PostgreSQL driver | Supported by SQLAlchemy 2.x and avoids changing the current SQLModel application to an async database stack. |

### Database, Queue, and Vector Search

| Technology | Version / baseline | Purpose | Why |
|------------|--------------------|---------|-----|
| Managed PostgreSQL | Provider-supported PostgreSQL 17/18 patch release | Primary SaaS database | Do not put the hosted SQLite file on a shared or ephemeral container filesystem. Retain SQLite for local self-host installs and tests where practical. |
| PostgreSQL-backed `ScrapeTask` queue | Existing model, adapted to PostgreSQL row locking and leases | Initial hosted background queue | This is the least disruptive beta queue: task status, user ownership, retries, and UI controls remain in the database. PostgreSQL documents `FOR UPDATE SKIP LOCKED` specifically for queue-like competing consumers. Separate the worker from the web service and preserve heartbeat/lease recovery. |
| Managed broker, only if measured need appears | AWS SQS, Google Cloud Tasks, or Azure Service Bus | Future dispatch isolation and independent queue scaling | These reduce broker operations but add another state system and require transactional outbox/idempotency work. All require duplicate-safe handlers; retries, visibility/lock timeouts, dead-lettering, ordering, and per-tenant fairness differ. Defer until queue age, database contention, or scale justifies it. |
| pgvector | Upstream 0.8.7 observed on 2026-10-28; verify the selected managed service supports the extension/version | Hosted embedding persistence and nearest-neighbor search | Consolidates vectors and tenant filters with the database and its backups. Place vectors behind the current `VectorStore` boundary. Use owner filters on every operation; evaluate exact search first and add approximate indexing only after recall and performance measurements. |
| ChromaDB | Keep current embedded local implementation for self-hosting | Local vector store | Preserve the working local Ollama + Chroma workflow. Do not mount the current persistent directory into replicated SaaS containers as a shared database. Current Chroma product/deployment documentation could not be verified in this research run, so a Chroma server/cloud option remains an alternative to evaluate, not a production assumption. |

### AI and Usage Controls

| Technology | Version / baseline | Purpose | Why |
|------------|--------------------|---------|-----|
| Existing `BaseAIClient` provider adapters | Retain interface; hosted beta allows one approved server-side provider configuration initially | Managed scoring, search assistance, and application-material generation | Preserve the tested provider abstraction, but do not expose cloud credentials or arbitrary endpoints to hosted accounts. Keep the current local Ollama route available in self-hosted mode. Select the beta model only after workload-quality and cost evaluation. |
| Managed embeddings | Same initial vendor where quality, region, and pricing are acceptable; otherwise a separately approved embedding service | Hosted vector creation | The existing embedding route is local-only. A cloud service cannot rely on each hosted user's workstation Ollama. Version embedding model and vector dimensions; changing models requires a re-embedding/reindex plan. |
| PostgreSQL usage ledger | New persisted reservations and actual-usage records, keyed by account and request/task ID | Enforce hard per-user budgets and limits | Provider rate and spend limits are organization/project scoped, not per job seeker. Reserve estimated cost before an outbound call, cap input/output tokens and operation counts, then reconcile reported usage. Use provider spend alerts as a second-level guard, not the tenant limit. Exact caps and reset periods remain product decisions. |
| Provider privacy controls | Per-provider endpoint/model configuration with explicit data-processing disclosure | Control where profile/CV material is sent and processed | Provider terms differ by endpoint, model, retention setting, and region. OpenAI documents default API no-training use alongside abuse-log retention, endpoint state exceptions, and eligibility limits for ZDR. Anthropic documents inference-geography controls only for supported models. These facts are not a legal conclusion or a residency promise; obtain current provider terms and legal review before beta invitations. |

### Infrastructure and Operations

| Technology | Version / baseline | Purpose | Why |
|------------|--------------------|---------|-----|
| OCI container image | Keep `Dockerfile` as the build source; pin base image by supported tag or digest at release | Repeatable deployment | Existing image is non-root and includes Playwright Chromium. Separate production dependencies from pytest/ruff and produce a locked, reproducible image. Keep the current Compose/Ollama path for self-hosting. |
| Managed container platform | Choose after region and operator capability are known; candidate mappings below | Web, worker, scheduler, and isolated scraper execution | Need persistent service processes, private access to PostgreSQL/AI endpoints, health checks, bounded scaling, and predictable outbound egress for Playwright/JobSpy. Do not run API and all background loops as one scaled web container. |
| Object storage | Provider-native private object storage behind a small Python storage interface | Original CV/DOCX/PDF uploads, exports, and generated files | Hosted container filesystems can be disposable. Store object metadata and owner in PostgreSQL; authorize every read/delete and use short-lived download/upload links when appropriate. Keep local filesystem storage in the self-hosted profile. |
| Secret manager + KMS | Provider equivalent; keep master encryption material out of image, database, and ordinary configuration | Database credentials, AI key, session/encryption key management | Current production encryption refuses to start without `ENCRYPTION_KEY`, and supports key IDs/rotation. Inject it from a managed secret service and design rotation plus restore procedures. Managed at-rest encryption does not replace Jobot's owner-scoped application encryption. |
| Secret manager + KMS | Provider equivalent; keep master encryption material out of image, database, and ordinary configuration | Database credentials, AI key, session/encryption key management | Current production encryption refuses to start without `ENCRYPTION_KEY`, and supports key IDs/rotation. Inject it from a managed secret service and design rotation plus restore procedures. Managed at-rest encryption does not replace Jobot's owner-scoped application encryption; verify actual CV/profile write paths because the inspected models contain raw-text columns. |
3. **Harden shared tenancy before loading hosted users.** Make deduplication unique per owner instead of relying on the current globally unique `dedup_hash`; audit every query, vector operation, task, object key, export, and delete for owner scoping. The models currently include nullable `user_id` columns for legacy compatibility, so hosted paths need fail-closed ownership and migration checks. Verify field-level encryption on CV/profile write paths before carrying forward broad encryption claims.
| OpenTelemetry + provider monitoring | OpenTelemetry instrumentation with the chosen cloud's metrics, logs, traces, and alerting | Beta operations and SLO evidence | Instrument API latency/errors, worker task age/retries, provider latency/429/quota/cost, DB pool saturation, backups, and scraper failures. Redact prompts, CV/profile content, cookies, and secrets from telemetry. Define the numeric SLO after beta usage and support expectations are known. |

### Hosted Platform Candidates

| Candidate | Example mapping | Strengths | Tradeoffs / verify |
|-----------|----------------|-----------|--------------------|
| AWS | ECS on Fargate (API + worker services), RDS PostgreSQL, SQS if/when needed, S3, Secrets Manager/KMS, CloudWatch | Direct fit for existing Docker image; distinct API/worker services and mature managed database, object storage, queue, and telemetry options. | More networking/IAM surface; confirm region, fixed scraper egress IP/NAT cost, queue semantics, and restore procedure. Not selected. |
| Azure | Container Apps, Azure Database for PostgreSQL Flexible Server, Service Bus, Blob Storage, Key Vault, Azure Monitor | Managed containers support HTTP apps and background jobs; Service Bus offers message locking/dead-lettering; official PostgreSQL docs describe PITR and selectable backup retention. | Service Bus adds broker contracts and lock renewal; verify Python client support, PostgreSQL extension availability, region and outbound egress. Not selected. |
| Google Cloud | Cloud Run service for the UI/API, Cloud Tasks for HTTP-target background dispatch, Cloud SQL PostgreSQL, Cloud Storage, Secret Manager, Cloud Monitoring | Cloud Run supports Python containers and distinct services/jobs/worker pools; Cloud Tasks exposes queue dispatch and retry controls. | Cloud Run filesystems are disposable; continuously running worker pools have separate scaling/cost behavior. Some Cloud SQL pages were unavailable in this research fetch, so validate backup/PITR, connection, and extension details before selection. Not selected. |

### Supporting Libraries

| Library | Version / baseline | Purpose | When to use |
|---------|--------------------|---------|-------------|
| `psycopg[binary]` | Psycopg 3, lock an exact compatible build | PostgreSQL driver distribution | Add only for hosted PostgreSQL deployment; test SSL, pooling, and runtime image compatibility. |
| `alembic` | Current compatible 1.x release | Schema migration tooling | Add before moving any hosted data or deploying multiple app instances. Autogenerate is a draft aid; review each migration. |
| `pgvector` Python adapter | Match managed extension | SQLAlchemy vector type and queries | Add if pgvector is selected; keep extension/version pinned and check provider support first. |
| Provider SDKs | Only SDK for the selected queue, storage, and AI provider | Managed-service integration | Add on provider selection; avoid installing all cloud SDKs into the local/self-hosted runtime if optional extras can keep the image smaller. |
| `opentelemetry-*` | Current stable compatible release set, locked together | Portable traces and metrics | Add instrumentation at the API/worker boundary; export to the selected backend. |

## Alternatives Considered

| Category | Recommended | Alternative | Why not / when to choose alternative |
|----------|-------------|-------------|--------------------------------------|
| Hosted relational database | Managed PostgreSQL 17/18 | Keep SQLite; use MySQL; adopt a document database | SQLite remains appropriate for one-device self-hosting, but current WAL, file paths, and queue claims assume a local file and single deployment unit. MySQL/doc-store adds migration friction without a demonstrated Jobot need. |
| Initial task transport | PostgreSQL task table | SQS, Cloud Tasks, Service Bus, Redis/Celery | Start with the existing durable task record and PostgreSQL claim semantics. Choose a managed broker only when observed throughput, independent scaling, or failure-isolation benefits justify outbox, broker state, and idempotency work. Redis/Celery adds another managed service and migration surface without current scale evidence. |
| Hosted vector store | pgvector in managed PostgreSQL; Chroma stays local | Chroma server/cloud or a dedicated vector database | One managed database simplifies backup and owner-scoped joins for beta. A dedicated vector service may suit substantially larger vector volume or specialized retrieval, but adds tenant policy, separate backup/deletion, and vendor cost. Chroma current hosted product guarantees were not verifiable here; re-evaluate from current official docs before selecting it. |
| Web UI | FastAPI + Jinja + HTMX | Node/React frontend | No evidence justifies a second language/build system; the existing UI and Python-first constraint are established. Revisit only if product research shows interaction needs the current UI cannot meet. |
| AI integration | One hosted provider behind the current interface, plus local Ollama in self-host mode | Multiple SaaS providers, BYO keys, self-hosted SaaS inference | Multiple choices multiply privacy, cost accounting, support, and reliability combinations. BYO keys are explicitly deferred. Add a second provider only after cost/quality/privacy tests show a real benefit. |

## Migration Path

1. **Keep the local profile intact.** Keep Docker Compose with SQLite, embedded Chroma, and optional local Ollama as the supported self-host path. Add hosted configuration rather than turning the local default into a cloud dependency.
2. **Make schema evolution explicit.** Add Alembic and baseline the existing schema. Replace production `create_all` / SQLite-only `PRAGMA table_info` migrations with versioned migrations. Build a repeatable SQLite-to-PostgreSQL import with row counts, owner checks, and rollback/restore evidence.
3. **Harden shared tenancy before loading hosted users.** Make deduplication unique per owner instead of relying on the current globally unique `dedup_hash`; audit every query, vector operation, task, object key, export, and delete for owner scoping. The models currently include nullable `user_id` columns for legacy compatibility, so hosted paths need fail-closed ownership and migration checks.
4. **Separate web and workers.** Deploy the existing API as one service and scraper/scoring/scheduler loops as separately scaled processes. Keep queue records in PostgreSQL initially; use leases, idempotency keys, bounded concurrency, and task-level cost reservations. Add a managed broker only after observing queue/database metrics.
5. **Replace file-local hosted state.** Put CV originals and exports in private object storage; migrate Chroma data through the vector adapter to pgvector or a separately selected hosted vector store. Version the embedding model and re-embed when hosted embedding dimensions/provider differ from local `nomic-embed-text`.
6. **Enable managed AI with limits.** Hold provider credentials server-side. Implement tenant-level operation/token/cost reservations in PostgreSQL before calls, reconcile actual response usage afterward, and define explicit behavior at cap (reject or defer; no unmetered fallback). Maintain org-level spend alerts and a kill switch.
7. **Prove recovery and operations.** Configure managed backups/PITR, separately back up object data and encryption-key metadata, perform restore and deletion drills, add alerting and redactable telemetry, then establish numeric RPO/RTO and availability SLOs from beta needs.

## Installation

Existing local/self-hosted runtime remains the base. For a PostgreSQL/pgvector hosted profile, the likely Python additions are:

```bash
pip install "psycopg[binary]" alembic pgvector
```

Keep test and lint tools in development dependencies rather than the production image. Lock all direct and transitive dependencies after selecting the runtime and managed database; this repository currently uses lower-bound ranges and the production Dockerfile installs the broad `requirements.txt` set.

## Open Decisions Before Implementation

- Cloud vendor, data region, and whether outbound scraper traffic needs a stable IP or dedicated egress.
- Expected beta signups, concurrent sessions, scrape cadence, retention, support coverage, and budget.
- PostgreSQL provider/version, high-availability tier, backup retention, tested RPO/RTO, and pgvector extension support.
- Whether to retain a PostgreSQL-backed queue throughout beta or use a cloud broker from first deployment.
- Vector implementation and hosted embedding provider/model; embedding data-processing terms and user disclosure.
- AI provider/model, endpoint-level retention/residency eligibility, pricing, request limits, usage units, and hard-cap policy.
- Whether uploaded originals are retained, for how long, and how export/deletion propagates through object storage, database rows, vectors, backups, and provider state.
- Numeric SLO, SLO measurement window, incident response/support expectations, and restore-test cadence.
- Legal/privacy review for target jurisdictions, scraping platform terms, data-processing agreements, and user-facing disclosures. This research makes no legal/compliance determination.

## Sources

Official documentation and primary project references checked 2026-10-28. Confidence labels describe the supporting evidence, not a guarantee of fit for Jobot.

- SQLModel FastAPI session dependency: https://sqlmodel.tiangolo.com/tutorial/fastapi/session-with-dependency/ (MEDIUM)
- SQLAlchemy PostgreSQL dialect and connection pooling: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html and https://docs.sqlalchemy.org/en/20/core/pooling.html (MEDIUM; SQLAlchemy 2.0.55 docs dated 2026-10-16)
- Alembic migration environment/tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html (MEDIUM)
- PostgreSQL `SKIP LOCKED` queue-like use: https://www.postgresql.org/docs/current/sql-select.html (MEDIUM; PostgreSQL 18 is current stable documentation)
- pgvector installation, indexing, tenancy, and scaling notes: https://github.com/pgvector/pgvector (MEDIUM; upstream 0.8.7 observed 2026-10-28)
- AWS ECS/Fargate, SQS standard queue semantics, SQS visibility timeout, and RDS backups: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html, https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues.html, https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html, https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_WorkingWithAutomatedBackups.html (MEDIUM)
- Azure Container Apps, Service Bus delivery/settlement, PostgreSQL backups, and Blob Storage: https://learn.microsoft.com/en-us/azure/container-apps/overview, https://learn.microsoft.com/en-us/azure/service-bus-messaging/message-transfers-locks-settlement, https://learn.microsoft.com/en-us/azure/postgresql/backup-restore/concepts-backup-restore, https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-introduction (MEDIUM)
- Google Cloud Run, Cloud Tasks queue retries/limits, Cloud Storage encryption, and Secret Manager: https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run, https://docs.cloud.google.com/tasks/docs/configuring-queues, https://docs.cloud.google.com/storage/docs/encryption, https://docs.cloud.google.com/secret-manager/docs/overview (MEDIUM; Cloud SQL backup/connection pages could not be retrieved in this run)
- OpenAI API data controls, rate limits, and pricing: https://developers.openai.com/api/docs/guides/your-data, https://developers.openai.com/api/docs/guides/rate-limits, https://developers.openai.com/api/docs/pricing (MEDIUM; endpoint/model eligibility and terms can change)
- Anthropic model pricing and data residency controls: https://platform.claude.com/docs/en/about-claude/pricing, https://platform.claude.com/docs/en/manage-claude/data-residency (MEDIUM; current model and geography support must be checked at selection)
- Local implementation evidence: `pyproject.toml`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `app/db/database.py`, `app/db/models.py`, `app/db/vector.py`, `app/queue/task_queue.py`, `app/queue/worker.py`, `app/core/config.py`, `app/security/encryption.py`, and `app/main.py` (HIGH for the inspected code paths)