# Phase 25 Context - Professional Page Architecture and Route Separation

## Objective

Make each primary Jobot workspace area directly addressable and refresh-safe:
dashboard, jobs board, jobs table, queue, profile, and settings. Preserve the
current authenticated ownership boundaries and HTMX partial workflows.

## Locked Decisions

- Canonical authenticated pages use dedicated URLs: `/dashboard`, `/jobs/board`,
  `/jobs/table`, `/queue`, `/profile`, and `/settings`.
- Existing `/web/views/*` routes remain as fragment endpoints for HTMX actions
  and existing integrations; page routes compose these existing components.
- Navigation uses standard links for direct URLs and browser history, with HTMX
  enhancement only where it preserves the same URL and fallback behavior.
- `/` remains a compatibility entry point and redirects authenticated users to
  `/dashboard`; anonymous users retain the existing login/register behavior.
- Page shells live in focused templates under `templates/pages/`; reusable
  domain widgets stay under `templates/components/`.
- Existing POST/DELETE endpoints, authorization dependencies, tenant-scoped
  queries, popup notifications, and API routes are unchanged unless a page
  shell needs a strictly presentational adaptation.
- LinkedIn remains a manual PDF import workflow. Page architecture does not
  restore LinkedIn sign-in, OIDC controls, cookie sync, or automated analysis.
- Mobile navigation must remain usable without horizontal overflow; dashboard
  data views retain their existing filters and job-inspector behavior.

## Acceptance Criteria

- Refreshing each canonical URL returns its full authenticated page instead of
  losing the current view or redirecting to a fragment.
- Direct navigation and browser back/forward work for each primary workspace
  page.
- Existing fragment endpoints continue to return their current partial HTML and
  all state-changing operations remain owner-scoped.
- Route and browser tests cover authenticated page access, anonymous redirects,
  fragment compatibility, and responsive navigation.

## Deferred Ideas

- A client-side router or SPA rewrite.
- Moving domain logic from `app/web/routes.py` into new services.
- Changes to Jobot API contracts, database schema, or task queue behavior.