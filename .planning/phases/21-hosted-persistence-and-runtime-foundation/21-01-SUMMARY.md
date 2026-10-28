# Phase 21 Summary — Hosted Persistence and Runtime Foundation

## Outcome

The runtime foundation for the hosted beta is defined around durable state, explicit worker boundaries, and a documented recovery model rather than a silent “works on one machine” assumption.

## Decisions captured

- hosted task and user state must be durable across restarts
- queue safety must include leasing, retries, and idempotency protections
- the self-hosted local mode remains supported as a parallel path with documented differences
- backup and restore expectations are required before user-facing hosted workflow begins

## Transition to next phase

Phase 22 can proceed once the persistence model is accepted and the hosted runtime has a clear contract for data durability and recovery.
