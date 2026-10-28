# Phase 19 Context — Beta Contract and Policy Decisions

## Why this phase exists

Jobot has a strong technical foundation, but the hosted SaaS direction is still a loose set of assumptions. This phase converts those assumptions into an explicit beta contract so the engineering team knows what is in scope, what is deferred, and what cannot be treated as default behavior.

## Product intent

The initial hosted product is a private beta for individual job seekers. It is not a general public SaaS launch, not a team workspace, and not a billing-based product. The goal is to validate retention, AI cost, and operational safety before broader availability.

## Decision areas

- customer segment: individual users in a limited-cohort beta
- geography or launch cohort: narrow, controlled rollout
- hosting posture: private beta, not public SaaS launch
- pricing: free/private beta first, paid launch deferred
- source policy: source-by-source permission matrix
- AI usage policy: per-user quotas, global caps, and disclosure language
- retention and deletion: full lifecycle policy for user content
- support model: documented owner, escalation path, duties

## Risks if not closed

- unbounded AI spend
- unclear data retention or deletion policy
- legal exposure from source terms and user data processing
- unclear customer and support model for private beta launch
- engineering work based on assumptions rather than approved product contract

## Success signal

This phase is successful when the beta contract is explicit, easy to apply in technical decisions, and clear enough to proceed to hosted security and runtime design in later phases.
