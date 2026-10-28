# Domain Pitfalls

**Domain:** Hosted SaaS for individual job seekers (private beta, managed AI)
**Researched:** 2026-10-28
**Overall confidence:** MEDIUM

Project findings are grounded in the current repository and planning documents. External source routing was unavailable for web search, and the GSD source classifier rated direct web fetches LOW even when the pages were official. Treat the vendor and platform notes below as due-diligence leads to recheck against current terms and the selected accounts. This is not a legal or compliance assessment; no geography is assumed.

## Critical Pitfalls

### Pitfall 1: Treating account-scoped queries as complete tenant isolation
**What goes wrong:** A missed ownership predicate in a route, cache, shared vector collection, background task, or operational endpoint can expose one seeker's data or activity to another. The current schema intentionally has nullable `user_id` fields for legacy records, vectors are held in shared Chroma collections, and the scraper status endpoint returns installation-wide `last_scrape_stats` and `is_running` to each authenticated caller.
**Why it happens:** Ownership checks are currently application conventions across many code paths, not a single enforced SaaS boundary. The v7 security review covered accounts in the existing deployment, not adversarial tenant access across every hosted surface.
**Consequences:** Resume/profile disclosure, cross-account generated materials, job-search privacy loss, and tenant-specific counts or activity leaking through aggregate status.
**Prevention:** Make server-verified account identity mandatory at each tenant-owned read/write and async enqueue/consume boundary. Inventory every tenant-owned table, vector, cache key, diagnostic, export, and admin path. Make ownership non-null for new hosted data; isolate any intentional global data explicitly. Scope status and metrics to the caller or expose only carefully reviewed aggregates.
**Detection:** Add two-account negative tests for every resource type and route, including guessed IDs, queue retries, exports, vectors, and cache reuse. Early warning signals include non-null legacy-owner rows after onboarding, unexplained cross-account 404/403 patterns, a tenant's request changing another tenant's result, or status counts changing with unrelated accounts.
**Roadmap prevention/verification:** Gate private-beta launch on a schema-derived ownership inventory, tenant-isolation regression suite, and manual review of all unscoped queries. Verify under the same database role, storage, and worker configuration used in production.

### Pitfall 2: Underestimating resume and candidate-profile sensitivity
**What goes wrong:** A CV contains more than skills: names, contact details, employment history, education, and potentially sensitive personal details. It can be copied into generated prompts, outputs, vectors, logs, support cases, and third-party AI processing even when the raw field is encrypted at rest.
**Why it happens:** Current encryption covers selected profile fields, including raw CV text and LinkedIn credentials, but fields such as `full_name`, `headline`, LinkedIn identifiers/URLs, jobs, notes, and generated materials are not all encrypted. Encryption keys are derived per owner from a deployment-wide master key, so compromise of that master key can expose every account's protected fields. The hosted managed-AI path is not the local Ollama privacy model described for self-hosting.
**Consequences:** High-impact personal-data disclosure through database access, key exposure, provider requests, backups, logs, or support tooling; users may upload more than the service needs.
**Prevention:** Minimize collection and prompt context, document which profile/job fields go to each provider, and make managed-AI processing explicit before upload or generation. Keep provider credentials and the encryption master key in a managed secret/key service with rotation and access audit. Define staff access, redaction, and support-session controls. Review derived vectors and generated materials as personal data too.
**Detection:** Alert on unexpected provider routing, decryption/key-access anomalies, prompt/log payload growth, and support access to user records. Review redacted production traces to ensure CV text, cookies, tokens, and generated materials are absent.
**Roadmap prevention/verification:** Before beta, create a field-to-store/provider/log data map and test with sentinel personal data through upload, extraction, scoring, generation, error paths, and support diagnostics. Test key rotation and a restore with the production key-management path.

### Pitfall 3: Promising export or deletion without end-to-end lifecycle control
**What goes wrong:** An account can appear deleted while personal data remains in relational rows, application materials, vector collections, queued task payloads, logs, snapshots, replicas, caches, or a provider's retention systems. A user also has no complete export path if they leave the beta.
**Why it happens:** Current routes support queue-task deletion and clearing, and a helper can delete one user's CV vectors, but no account-wide export or deletion workflow was found. There is no documented retention schedule covering all stores. Shared backups complicate tenant-only restoration and deletion. The security policy itself warns that losing all decryption keys makes restored encrypted data irrecoverable.
**Consequences:** Orphaned sensitive data, incomplete user requests, accidental resurrection during restore, or loss of the ability to recover data after a key/database mismatch.
**Prevention:** Define an inventory and lifecycle for active DB rows, vectors, task payloads, object storage if added, logs, backups, provider-side state, and encryption keys. Deletion should first stop new work and revoke sessions/credentials, then remove or irreversibly anonymize owned records and vectors, and report any backup/provider retention window honestly. Export a complete, usable account archive. Keep retention exceptions restricted and auditable.
**Detection:** Run periodic deletion reconciliations and inspect for orphaned owner IDs, stale queue jobs, vectors, and expired backups. Early warning signals include deleted accounts reappearing after restore, a delete job with partial failures, or support being unable to explain where a profile remains.
**Roadmap prevention/verification:** Make export, deletion, and retention explicit acceptance criteria before inviting beta users. Exercise export/delete/restore against a fixture with two accounts; prove one account can be restored or deleted without exposing or overwriting another. Document backup expiry and provider retention separately.

### Pitfall 4: Assuming a managed AI provider is private, predictable, or cost-bounded by default
**What goes wrong:** The app sends CV/profile context and job descriptions to the selected generation provider. Provider data use, retention, eligible controls, rate limits, prices, and regional processing vary by product, endpoint, account tier, and configuration. Provider-level quotas are not per Jobot user, so one account can consume shared capacity or spend.
**Why it happens:** Provider routing and safe error categories exist, but the code has no visible per-user token/spend ledger or hosted quota enforcement. OpenAI's API docs describe default abuse-monitoring retention and eligibility requirements for stronger retention controls; Gemini's terms distinguish unpaid from paid services, including different data-use terms. These examples do not select a vendor or prove a contract is suitable.
**Consequences:** Surprise bills, rate-limit cascades, prolonged outages, unexpected human/provider processing, privacy disclosures that do not match user expectations, or a service-wide quota being exhausted by one account.
**Prevention:** Select one managed-AI account/service configuration only after reviewing its current terms, data processing agreement, retention, training/improvement use, region, subprocessors, breach notice, and deletion behavior. Prefer a production service tier with terms compatible with the intended CV data. Minimize prompts; cap jobs, tokens, retries, and spend per account and globally; configure hard provider spend limits where available and alert before them. Do not promise zero retention or regional processing unless the exact project, endpoint, and model qualify.
**Detection:** Track per-user requests/tokens/cost estimates, provider 429/5xx rates, retries, and quota headroom. Alert on abrupt usage spikes, repeated retries, a cost-per-active-user outlier, or a provider policy/configuration change.
**Roadmap prevention/verification:** Vendor and model selection is a pre-beta gate. Run load/cost scenarios using real task shapes and worst-case context sizes; verify caps fail closed, do not silently switch providers, and give users clear remaining-usage and outage messages.

### Pitfall 5: Calling prompt delimiters a complete defense against job-content injection
**What goes wrong:** A job posting can contain direct or hidden instructions that manipulate scoring, tailoring, or extracted profile facts. Delimiters, sanitizers, and structured response schemas can reduce risk but do not make the model reliably distinguish instructions from untrusted content.
**Why it happens:** The evaluator currently wraps descriptions in `<job_description>` tags and its system prompt instructs the model to ignore embedded instructions; the prior threat model marks prompt injection mitigated. OWASP's current guidance cautions that labels and prompt wording are not enforcement boundaries. The application does not currently auto-submit applications, which limits impact, but generated text and fit scores still affect user decisions.
**Consequences:** Misleading job ranking or application materials, leaked prompt/context, malicious links or markup in rendered output, and erosion of trust in recommendations.
**Prevention:** Treat job content, extracted profile text, provider output, and model output as untrusted. Keep generation read-only; validate output at the consuming boundary and preserve human review before external actions. Never allow job text to authorize tools, change account scope, or retrieve other users' data. Keep prompts lean and avoid sending unrelated profile fields.
**Detection:** Track unusual score distributions, suspicious output/markup, validator failures, and repeated prompt injection indicators without logging raw CVs or full prompts. Early warning signals include sudden perfect scores, output that repeats hidden instructions, or generated content unrelated to the candidate.
**Roadmap prevention/verification:** Test indirect injection in scraped descriptions and hidden/encoded text using harmless fixtures and instrumented outputs. Measure expected task completion and false positives as well as policy violations; do not claim prompt-injection immunity from passing a small smoke test.

### Pitfall 6: Scraping into account bans, source blocks, or unstable product behavior
**What goes wrong:** A site's terms, robots instructions, access controls, or rate limits can change; automated access may be restricted regardless of request delay. LinkedIn's current User Agreement explicitly prohibits crawler/software scraping and bypassing limits. Google's Terms prohibit automated access that violates machine-readable instructions such as robots.txt. The StepStone terms page attempted during this research returned 404, so its applicable terms were not verified.
**Why it happens:** Jobot's current stack uses python-jobspy for LinkedIn/Google Jobs and Playwright for StepStone. Actual configured stagger delay defaults to 0.5 seconds, while the security policy describes 2–5 seconds; multiple queries/sites can fan out concurrently. A slow rate is not proof of permission.
**Consequences:** User account restrictions, source IP blocks, unstable ingestion, legal/vendor escalation, and dependence on an undocumented scraping path for the core experience.
**Prevention:** Review each source's current terms, machine-readable instructions, allowed access method, attribution/storage/display conditions, and rate constraints before enabling it in the hosted service. Obtain permission or use an authorized API/partner where required. Bound concurrency and request volume, honor backoff and block responses, and provide a per-source kill switch. Do not ask beta users to provide platform cookies or credentials without a separately approved product/security decision.
**Detection:** Monitor per-source 403/429/challenge rates, extraction yield, account restrictions, and terms/policy changes. Stop a source automatically on repeated block signals rather than retrying aggressively.
**Roadmap prevention/verification:** Treat source authorization and operational limits as a launch gate per source. Reconcile the documented and configured rate limits, test backoff/disable behavior, and retain a manual or authorized fallback when a source is unavailable.

### Pitfall 7: Exposing internal services through user-controlled URLs
**What goes wrong:** A request to a user-configurable provider endpoint can reach loopback, private networks, cloud metadata, or another internal service. Validating only URL syntax or turning off redirects does not stop that network access. The profile sync route also accepts a LinkedIn URL based on whether the string contains `linkedin.com`, which is not a canonical-host validation rule.
**Why it happens:** `_validated_url` explicitly allows custom/private HTTP endpoints for self-hosted use; settings expose a custom endpoint. That is reasonable locally but becomes a hosted SSRF boundary. The existing security model's allowed-domain statement does not match this custom-provider behavior.
**Consequences:** Cloud credential theft, access to internal control planes/databases, network scanning, or sensitive provider credentials sent to an attacker-controlled endpoint.
**Prevention:** Disable arbitrary custom/local endpoints in hosted managed-AI mode unless there is a tightly isolated, reviewed feature need. Use a fixed provider allowlist, strict canonical parsing for accepted URLs, DNS/IP validation bound to the connection, redirect denial, and outbound network policy that blocks internal and metadata ranges. Validate external profile URLs by parsed scheme/host and expected path, then revalidate every redirect/navigation.
**Detection:** Log bounded endpoint identifiers and rejected destination classes, not full credentials or URL query strings. Alert on attempts to target private/loopback/link-local addresses and unexpected outbound hosts.
**Roadmap prevention/verification:** Test URL parsing edge cases, IPv4/IPv6, DNS rebinding, redirects, proxy settings, and cloud metadata reachability from the deployed network. Verify egress policy independently of application checks.

### Pitfall 8: Unbounded beta usage turning into abuse, cost spikes, or noisy-neighbor outages
**What goes wrong:** Public registration, repeated scraping, large query fan-out, task enqueueing, model calls, and document parsing can consume shared CPU, network, storage, provider quota, and money. A per-request payload size limit does not cap total queued work or ongoing usage.
**Why it happens:** No general authentication/API rate limiter or per-user queue-depth/AI usage budget was found in the app paths inspected. The queue bounds an individual payload, but it does not cap task count; scrape `results_wanted` is caller-supplied, and profile query generation can produce an unbounded set. Shared worker pools use installation-wide concurrency settings.
**Consequences:** A single account can starve the rest of the beta, trigger provider billing, fill disks, or turn login and queue endpoints into denial-of-service surfaces.
**Prevention:** Apply layered registration/login/IP and account limits, per-user queue depth/concurrency, maximum query count/results/upload size, request deadlines, retry budgets, and global circuit breakers. Set provider hard spend limits and infrastructure CPU/memory/storage ceilings. Keep queue admission controls at the enqueue boundary and enforce them again in workers.
**Detection:** Dashboard queue age/depth, per-account scrape and model-call rates, provider spend, parser CPU/memory, disk growth, 429/5xx, and worker lease recovery. Early warning signals include queue age increasing while successful completions fall, unusually high per-account fan-out, or repeated retry cycles.
**Roadmap prevention/verification:** Set private-beta limits from measured capacity, then load-test worst-case accounts and concurrent uploads. Verify one account hitting its cap does not block another account or bypass the cap through multiple endpoints.

### Pitfall 9: Mistaking a single-process local stack for a recoverable hosted service
**What goes wrong:** A restart, database lock, corrupted file, worker duplication, or lost encryption key can interrupt service or make user data inaccessible. A healthy HTTP process does not prove that the database, vector store, queue, AI provider, or restore path is healthy.
**Why it happens:** Defaults use SQLite and embedded persistent Chroma; the FastAPI lifespan starts scheduler and queue-worker loops inside the application process. The public `/health` endpoint always returns `ok`; a separate authenticated diagnostics route checks only selected dependencies. No numeric SLO, RPO/RTO, or production topology is approved yet.
**Consequences:** Lost or duplicated background work, prolonged outages, unrecoverable encrypted data, or false green health checks during dependency failure. Multiple app replicas may multiply in-process schedulers/workers and intensify SQLite contention.
**Prevention:** Choose a production database/queue/storage topology and explicit worker ownership before scaling replicas. Define SLO, RPO, RTO, and failure modes. Back up relational and vector data consistently with encryption-key versions; keep key recovery separate and access-controlled. Add readiness/liveness signals that distinguish process health from dependency health, and provide operator runbooks and a kill switch.
**Detection:** Alert on failed DB/vector checks, oldest queue age, stale leases, replica worker count, backup age, restore failures, and SLO burn. Early warning signals include persistent SQLite lock retries, missing key IDs after restore, or a process-level health check passing while task completion stops.
**Roadmap prevention/verification:** Do not advertise availability until a production-like restore drill meets the chosen RPO/RTO, including a two-account restore check. Test restart, provider outage, database failover, key rotation/loss, and duplicate-worker startup.

### Pitfall 10: Logging enough to debug while leaking enough to harm users
**What goes wrong:** Logs and support records can become a shadow copy of CVs, provider prompts, session tokens, searches, job history, or scraped content. Conversely, logs that are too sparse or not monitored leave incidents and outages undiscovered.
**Why it happens:** Logging currently writes a plain text stream to stdout. Some scraper paths log search terms, URLs, or raw exception messages; the public security policy warns against logging secrets but there is no documented tenant-aware operations/support model for the hosted service.
**Consequences:** Sensitive data spreads into longer-lived third-party log systems and backups, or operators cannot investigate tenant isolation failures and abuse in time.
**Prevention:** Use structured, redacted events with request/task correlation IDs and verified account IDs; explicitly exclude CV text, prompts, outputs, cookies, API keys, and raw provider bodies. Separate security/audit events from debug logs, restrict staff access, define retention, and give support a documented least-privilege workflow. Establish incident ownership and customer communication procedures.
**Detection:** Automated sentinel scans of logs and traces, logging-drop alerts, access audits, and periodic support-case reviews. Early warning signals include raw URLs in logs, provider response bodies, uncorrelated queue errors, or support requests asking users to attach CVs.
**Roadmap prevention/verification:** Before beta, run sentinel data through success and failure paths, prove it is absent from logs/traces, and rehearse a cross-account incident using the support runbook. Set a support response commitment only after staffing and escalation are defined.

## Moderate Pitfalls

### Pitfall 1: Overstating security, privacy, or compliance readiness
**What goes wrong:** Local-only Ollama language, prior STRIDE status, encryption claims, or generic statements such as “compliant,” “private,” “zero retention,” or “data stays in-region” get reused in hosted marketing despite managed AI and unresolved hosting/provider choices.
**Prevention:** Distinguish self-hosted and hosted data flows in product copy. Make specific, testable statements about what is collected, sent to which provider, stored where, and retained for how long. Do not claim certification or legal compliance before the relevant scope, controls, evidence, and review exist.
**Early warning signals:** Copy that says “100% local” for hosted users, an unqualified “encrypted” claim that ignores logs/backups, or a geography/retention promise not supported by the selected provider configuration.

### Pitfall 2: Treating support and security contacts as operational coverage
**What goes wrong:** The existing security policy asks for private reporting and says maintainers allow up to 48 hours for initial response, but this does not establish a staffed SaaS incident, privacy-request, or customer-support service.
**Prevention:** Define support hours, escalation ownership, security-report handling, incident communications, privacy request handling, and evidence retention before beta onboarding. Avoid an availability or response-time promise that has no on-call coverage.
**Early warning signals:** Unowned alerts, security reports arriving at an unattended mailbox, or requests to access production records without an approval trail.

## Minor Pitfalls

### Pitfall 1: Allowing operational dashboards to expose cross-account activity
**What goes wrong:** Aggregate status can reveal activity even when the underlying job rows are scoped.
**Prevention:** Review whether each metric is truly safe to share; prefer per-account views and deliberate aggregate thresholds. The existing scraper status returns global run state/statistics and should be treated as a tenant-isolation item, not a harmless UI detail.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Tenant/data architecture | Relying on developer discipline for every owner predicate | Decide database isolation and ownership enforcement; derive tests from the schema and test all async/cache/vector paths |
| CV and AI onboarding | Users do not understand provider processing | Field-level data map, just-in-time disclosure, minimal prompt context, provider-specific configuration review |
| Export/deletion | Data remains in vectors, queue, logs, or backups | Make lifecycle inventory and two-account export/delete/restore tests launch blockers |
| Scraping integrations | Blocking or contract changes arrive after beta launch | Review each source separately, use authorized access, enforce per-source caps/backoff/kill switches |
| SaaS abuse and spend | Shared provider/account quotas are mistaken for user quotas | Per-user metering/admission controls plus global spend and capacity limits |
| Production operations | App health is mistaken for service health | Define SLO/RPO/RTO, dependency-aware health, incident runbooks, and witnessed restore drills |
| Privacy/compliance claims | Local-mode claims are carried into managed-AI SaaS | Publish only verified data-flow and retention statements; select target geographies and seek appropriate review before launch |

## Sources

### Project evidence
- [Project scope and v8.0 assumptions](../PROJECT.md)
- [Milestone history](../MILESTONES.md)
- [Existing security policy](../../SECURITY.md)
- [Existing threat model](../SECURITY.md)
- [Ownership/encryption boundary](../../app/db/ownership.py)
- [Data models](../../app/db/models.py)
- [Provider routing](../../app/ai/client.py)
- [Task queue](../../app/queue/task_queue.py)
- [Scraper status API](../../app/api/scrapers.py)
- [Application startup and health endpoint](../../app/main.py)
- [Logging configuration](../../app/core/logging.py)

### External primary sources
- [OWASP Multi-Tenant Application Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html) — tenant isolation, async work, noisy neighbors, offboarding, backups, and monitoring.
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) — URL validation, destination allowlists, redirects, DNS, and network-layer controls.
- [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) — indirect injection, limits of delimiters, and verification guidance.
- [OWASP API4:2023 Unrestricted Resource Consumption](https://api-security.owasp.org/editions/2023/en/0xa4-unrestricted-resource-consumption) — request/resource bounds, throttling, and provider spending limits.
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — security events, sensitive-data exclusions, retention, and monitoring.
- [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data) and [rate limits](https://developers.openai.com/api/docs/guides/rate-limits) — service/endpoint retention controls, eligibility, and account/project-level limits.
- [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms) and [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) — paid/unpaid data-use differences, usage tiers, and quota variability.
- [LinkedIn User Agreement](https://www.linkedin.com/legal/user-agreement) — current restrictions on scraping/crawlers and access-limit circumvention.
- [Google Terms of Service](https://policies.google.com/terms?hl=en) — automated access restrictions tied to machine-readable instructions.
- [NIST SP 800-34 Rev. 1](https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final) — contingency planning.
- [NIST SP 800-61 Rev. 3](https://csrc.nist.gov/pubs/sp/800/61/r3/final) — incident response and cybersecurity risk management.
- [NIST Privacy Framework](https://www.nist.gov/privacy-framework) — voluntary privacy risk-management framework.
- [NIST SP 800-88 Rev. 2](https://csrc.nist.gov/pubs/sp/800/88/r2/final) — media sanitization.

**Source gaps:** Anthropic's data-use page did not fetch successfully in this run; the attempted StepStone terms URL returned 404. No conclusions are drawn about those terms. Recheck all vendor/platform pages and account-specific controls when selecting the managed AI provider, hosting region, and source integrations.