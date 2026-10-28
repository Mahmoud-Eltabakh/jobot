# Phase 19 Summary — Beta Contract and Policy Decisions

## Outcome

The private-beta contract is defined as a limited, invitation-based beta for individual job seekers. The product remains intentionally narrow and does not assume public billing, team workspaces, or employer workflows.

## Decisions captured

- Initial user cohort: individual job seeker in a controlled beta.
- Scope boundary: personal-workspace beta only, no employer or team management.
- Public launch: explicitly deferred until retention, security, and cost evidence exists.
- Source policy: each source must be reviewed and classified as allowed, restricted, or deferred.
- AI usage policy: user quotas and operator ceilings are required before hosted AI is enabled.
- Data lifecycle: export, deletion, retention, and restore behavior are required before real beta usage.
- Support model: a named owner and escalation path are required for the private cohort.

## Residual risks

- source terms can change and must be rechecked before production rollout
- AI cost assumptions need measured beta evidence
- jurisdiction-specific privacy obligations still require explicit review before broader launch

## Transition to next phase

These decisions feed directly into the tenant isolation and privacy work in the next phase. Without this beta contract, the security and persistence design would be built on assumptions rather than policy.
