# Project Research Summary

**Project:** Jobot
**Domain:** Hosted job-search copilot and application tracker
**Researched:** 2026-10-28
**Confidence:** LOW for launch decisions; MEDIUM for the recommended direction

## Executive Summary

Jobot already combines job discovery, profile/CV-based fit explanations, application tracking, and editable AI-generated materials in a Python-first product. The v8.0 research explores a hosted private beta for individual job seekers, isolated personal workspaces, managed AI with hard per-user limits, and practical continuity for self-hosted users. These are provisional assumptions, not approved product or deployment decisions.

The recommended direction is to settle provider/data-processing, source-access, budget, support, and recovery policies before accepting real CVs. Then prove tenant boundaries, establish hosted persistence and separate web/worker/scheduler roles, and build the hosted workflow and AI controls on those foundations. Managed PostgreSQL, PostgreSQL-backed tasks, and pgvector are candidates, not selections; no cloud, region, AI provider, quota, or numeric SLO is approved.

The critical risks are cross-account data exposure, sensitive CV content in provider/log/backup paths, unbounded AI spend, source restrictions, and incomplete export, deletion, or restore behavior. A beta go/no-go should require tested isolation, clear provider disclosures and limits, an authorized source policy, data-lifecycle controls, and recovery evidence.

## Key Findings

### Recommended Stack

Keep the Python/FastAPI/Jinja/HTMX application and provider adapters. For hosted operation, evaluate managed PostgreSQL with reviewed Alembic migrations; initially keep task state and usage accounting in PostgreSQL, and separate web, worker, and scheduler processes. Evaluate pgvector for hosted embeddings and object storage for uploaded originals/exports only after validating tenant filtering, deletion, backup, and self-hosted compatibility. Keep SQLite, Chroma, and optional local Ollama for self-hosting where feasible.

**Core technologies:** Python and the current web stack; managed PostgreSQL; Alembic and Psycopg; a PostgreSQL-backed leased queue before adding a broker; pgvector as a candidate hosted vector store; provider-equivalent object storage and key management. Every hosted service remains undecided pending region, cost, operator-capacity, and data-policy review. See [STACK.md](STACK.md).

### Expected Features

**Must have for a hosted beta:**
- A private individual workspace and a guided, skippable route to a useful job result.
- Source-aware discovery, understandable fit reasons, and a user-controlled shortlist-to-application flow.
- Editable generated materials and explicit provider failures, not automatic submissions or silent fallback.
- Just-in-time AI processing disclosures, visible usage/cap/reset behavior, and clear exhaustion states.
- Defined data export and deletion, including honest treatment of files, vectors, logs, backups, and provider-side retention.
- Accessible status/error feedback and a support route with an assigned owner.

**Differentiators:** multi-source discovery, explainable fit, user-correctable adaptive search, and an optional self-hosted path.

**Defer provisionally:** billing/public paid launch, teams/coaches/employers, hosted BYO keys or multi-provider choice, auto-apply, broad autofill, and calendar/email integrations. Demand and beta success measures remain unvalidated. See [FEATURES.md](FEATURES.md).

### Architecture Approach

Use a Python modular monolith with stateless web, separate workers, and a single scheduler role. Resolve ownership from authenticated identity and enforce it through every query, mutation, task, vector operation, cache, export, and deletion. Add tenant-aware constraints and adversarial cross-account tests; decide whether database row-level security is warranted only after selecting the application database role model. Keep provider calls behind a policy boundary that reserves usage before calls and fails closed at limits. See [ARCHITECTURE.md](ARCHITECTURE.md); its confidence is LOW and the design needs validation against selected services.

**Major components:** web/API and tenant boundary; hosted/local persistence adapters; workers/scheduler and AI policy/usage ledger; key management and observable operations.

### Critical Pitfalls

1. **Tenant leaks:** legacy nullable ownership, global deduplication/status, vectors, tasks, and caches can bypass route-level checks. Inventory each surface and gate beta on two-account negative tests.
2. **CV/profile exposure:** encryption at rest does not prevent prompt, log, support, vector, provider, or backup exposure. Minimize data, map flows, disclose processing, and test sentinel data on success and failure paths.
3. **Incomplete data lifecycle:** define export, deletion, retention, and backup expiry across every store and provider; exercise export/delete/restore with multiple accounts.
4. **Unbounded AI costs:** enforce per-user reservations/caps and a global spend ceiling in Jobot, reconcile usage, and fail clearly at limits.
5. **Scraping and operations risk:** review each source's current access terms and provide source kill switches/backoff; prove backup restoration, incident handling, and service objectives before beta.

See [PITFALLS.md](PITFALLS.md). This research is not legal advice; source terms and jurisdictional obligations require current review.

## Implications for Roadmap

The following is a dependency-ordered proposal, not an approved launch scope:

### Phase 19: Beta Contract and Policy Decisions
**Rationale:** Data flow, source access, costs, support, and recovery constraints drive architecture.
**Delivers:** Decisions or explicit open items for cohort/geography, provider/data disclosures, per-source access policy, quota units, retention, export/deletion scope, support ownership, and candidate SLO/RPO/RTO.

### Phase 20: Tenant, Privacy, and Hosted Security Invariants
**Rationale:** Isolation is a prerequisite for every hosted user workflow and data migration.
**Delivers:** Ownership inventory, fail-closed hosted paths, tenant-scoped constraints, cross-account tests, sensitive-data flow map, hosted endpoint/egress policy, and key-management design.

### Phase 21: Hosted Persistence and Runtime Foundation
**Rationale:** Shared durable state and explicit process roles are needed before scaling beyond one host.
**Delivers:** Selected database and migrations, hosted/local storage adapters, separated web/worker/scheduler roles, task leases/idempotency, and migration/rollback evidence.

### Phase 22: Hosted Personal Workflow and Managed-AI Controls
**Rationale:** Build the beta experience on tested tenant and persistence foundations.
**Delivers:** Onboarding, source-aware discovery, fit explanations, tracker/material workflows, provider disclosures, server-enforced quotas, usage UX, and defined export/deletion controls.

### Phase 23: Production Gates and Private-Beta Readiness
**Rationale:** Beta access should follow operational proof, not a healthy-process demo.
**Delivers:** Redacted telemetry/alerts, rate and queue limits, encrypted backup/restore drills, deletion/retention drills, incident/support runbooks, load/cost tests, measurable service objectives, and an invitation-cohort go/no-go.

**Phase ordering:** resolve policy before infrastructure; prove tenant/privacy invariants before migration; make hosted persistence and process roles durable before user-facing quotas; gate real CV use on deletion and recovery evidence. Keep self-hosted compatibility as a parallel constraint where practical.

**Research flags:** Phase 19 needs current vendor/source/legal review. Phase 20 needs code-grounded ownership and sensitive-data tracing. Phase 21 needs provider-specific database/vector/worker validation. Phase 22 needs model cost/quality and lifecycle UX decisions. Phase 23 needs operator-approved numeric objectives and recovery exercises.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Direction fits the existing Python system; hosting, region, AI vendor, cost, and SLO are open. |
| Features | MEDIUM | Current capabilities are code-grounded; beta demand and success metrics are unvalidated. |
| Architecture | LOW | Recommendations fit inspected code, but tenant strategy, stores, RLS, capacity, and vendors are undecided. |
| Pitfalls | MEDIUM | Concrete risks are code-grounded; legal/vendor details must be rechecked for chosen sources and regions. |

**Overall confidence:** LOW for product/cloud/launch choices; MEDIUM for sequencing and risk controls.

## Gaps to Address

- Confirm customer segment, beta geography, support capacity, and whether beta is non-billing.
- Select cloud/region and managed AI/model only after provider terms, cost, data processing, and operator capacity are reviewed.
- Decide per-source scraping permissions and operating limits; LinkedIn is a material risk and StepStone terms were not verified.
- Define usage units, per-user hard caps, reset behavior, global spend ceiling, and outage behavior.
- Set data inventory, retention, export/deletion scope, backup expiry, and privacy-review ownership.
- Set measurable availability, recovery, and support targets after the operating model is chosen.
- Define which v8 features must remain available in self-hosted mode.
- Validate product activation, retention, quality, and cost targets with beta evidence.

## Sources

### Primary
- [PROJECT.md](../PROJECT.md), [MILESTONES.md](../MILESTONES.md), current repository code, and the four detailed research artifacts establish project facts and research inputs.
- [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html), [PostgreSQL SELECT / SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html), [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html), and [Alembic migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html) document candidate behaviors, not a final design.
- Cloud platform docs in [STACK.md](STACK.md), including [AWS ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html), [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/overview), and [Google Cloud Run](https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run), are comparison sources only.
- [OWASP multi-tenant guidance](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Application_Security_Cheat_Sheet.html) and [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) inform security and accessibility gates.

### Secondary and Low Confidence
- Provider data-control references and product comparison sources are listed in [FEATURES.md](FEATURES.md) and [PITFALLS.md](PITFALLS.md); vendor terms vary by endpoint, model, account, and date.
- Feature differentiation, beta success measures, legal applicability, and operating targets remain hypotheses pending user/operator validation.

---
*Research completed: 2026-10-28*
*Ready for roadmap: yes, as a discovery and decision roadmap, not an approved SaaS launch specification.*