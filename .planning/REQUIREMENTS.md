# v8.0 Requirements — Production SaaS Foundation

## Milestone Goal

Define and validate the minimal production-ready SaaS foundation for a private beta aimed at individual job seekers, while preserving the existing self-hosted workflow as a parallel path. The milestone must establish product boundaries, privacy guarantees, usage controls, and deployment foundations before any hosted production release is approved.

## Product Scope

### In Scope

- A hosted private beta for individual job seekers.
- Per-user workspaces with account-scoped profiles, jobs, notes, generated materials, and AI settings.
- Managed AI access with explicit usage caps, provider disclosures, and failure states.
- Hosted persistence, queueing, and operational controls needed for safe beta use.
- Data export, deletion, and restore planning for real user content.
- Production observability, support routing, and incident handling procedures.
- Self-hosted compatibility as a supported alternative unless research proves incompatibility.

### Out of Scope

- Public paid launch or billing implementation.
- Team, coach, or employer workspaces.
- Multi-tenant shared workspaces or organization-level access control.
- BYO-key hosted AI offering.
- Full automation of employer application submission.
- Legal certification, privacy assurance, or regulated data processing commitments without selected jurisdiction and vendor review.

## Functional Requirements

### FR-01: Hosted Personal Workspace

The system shall support a hosted onboarding flow for an individual user that creates an isolated workspace and lets the user begin job discovery and tracking without a manual local setup.

Acceptance criteria:
- A user may sign up and create an account in the hosted beta.
- Account data is isolated by owner and not shared across users.
- Core discovery, profile, fit, and tracking flows work inside the user’s personal workspace.
- Hosted onboarding is skippable and does not block the user from reaching useful results.

### FR-02: Account Isolation and Ownership Enforcement

The system shall enforce ownership boundaries across all user data, tasks, config, AI-generated outputs, and exports.

Acceptance criteria:
- Every API read/write and background task is scoped to the authenticated user.
- Cross-account access attempts fail closed.
- Existing data model ownership edges are reviewed and fixed for null or legacy values.
- Negative tests cover at least two different accounts and a cross-user violation path.

### FR-03: Managed AI Usage Controls

The system shall reserve and enforce per-user AI usage limits with clear warnings and fail-closed behavior.

Acceptance criteria:
- Usage is tracked at the user and request level.
- A user can observe remaining quota and reset behavior.
- Hard caps block new AI work before a provider call occurs when limits are exhausted.
- Global service spend ceilings are enforced and visible to operators.
- Explicit provider failure messages are shown without silent fallback except where approved.

### FR-04: Data Lifecycle Controls

The system shall define and test real export, deletion, retention, and restore flows for hosted user content.

Acceptance criteria:
- Export covers user profile, jobs, notes, app materials, and relevant generated artifacts.
- Deletion removes or anonymizes the user’s data across primary stores and derivative artifacts.
- Retention and backup expiry rules are specified and reviewed.
- Restore or recovery drills are executed with test data and documented results.

### FR-05: Hosted Runtime Foundation

The system shall have a durable hosted runtime foundation with clear process boundaries for web, worker, and scheduler roles.

Acceptance criteria:
- Durable database state is separated from ephemeral local-only behavior.
- Background operations use idempotent task leases and recovery flows.
- Web and worker services are not implicitly coupled to a single host-only SQLite workflow.
- The design supports a single hosted deployment model while preserving the self-hosted local mode.

### FR-06: Source Access and Policy Controls

The system shall define the allowed source set, provider-specific access policy, and operational guardrails for job discovery.

Acceptance criteria:
- Source permissions and rate limits are documented and reviewed against terms.
- Dangerous or restricted providers are behind a kill switch or explicit disablement path.
- Provider and source failures are surfaced to users with clear guidance.
- The beta can run without violating approved source policy.

### FR-07: Observability, Support, and Recovery

The system shall provide actionable operational telemetry, support route, and incident handling for a private beta.

Acceptance criteria:
- Relevant metrics exist for queue health, provider failures, user AI usage, and service availability.
- Support ownership and escalation path are documented.
- Backup and restore validation, outage response, and rollback steps are defined.
- Service objectives and support expectations are recorded before the beta opens.

## Non-Functional Requirements

### NFR-01: Privacy and Data Protection

The hosted beta must treat CVs, profile data, and provider credentials as sensitive user content and minimize exposure across prompts, logs, support, backups, and provider requests.

### NFR-02: Security by Default

Defaults shall fail closed and avoid silent data leakage, broad fallback to synthetic data, or unbounded provider-side retention.

### NFR-03: Cost Control

The system shall detect, restrict, and explain AI cost risk before a user exceeds planned usage budgets.

### NFR-04: Reliability

The beta must include tested recovery and retention procedures for database, vector, queue, and user-content state.

### NFR-05: Accessibility and Usability

Hosted onboarding, status feedback, and error states must be understandable, actionable, and accessible to private beta users.

### NFR-06: Backward Compatibility

The hosted SaaS foundation must preserve the self-hosted local workflow where possible and avoid breaking the existing user experience for local installations.

## Open Decisions That Must Be Resolved in v8.0

These decisions are not product assumptions and remain open until explicitly decided:

- Target customer and initial geography for the private beta.
- Whether the beta is free or paid, and if pricing is introduced later.
- Primary hosting provider and region.
- Managed database choice and vector storage architecture.
- AI provider mix, model selection, and data processing disclosures.
- Support model and operating hours.
- Data retention, deletion, and backup expiry policy.
- Source policy for LinkedIn, Google Jobs, StepStone, and other providers.
- Numeric SLO/RPO/RTO values for the beta.
- Whether SaaS is the only supported path or if self-hosted remains first-class.

## Success Criteria for v8.0

The milestone is considered complete when:
- Requirements are documented and approved for the discovered SaaS scope.
- Policy decisions are captured or explicitly marked as deferred with owner and risk.
- Tenant-isolation and privacy invariants are validated by tests.
- Hosted runtime and persistence decisions are made with rollback evidence.
- AI cost, restore, and deletion controls are validated at the beta design level.
- The roadmap defines the next implementation phases with clear dependencies.

## Traceability

This requirements document is derived from the v8.0 research summary and the current project state in [.planning/PROJECT.md](PROJECT.md) and [.planning/research/SUMMARY.md](research/SUMMARY.md).
