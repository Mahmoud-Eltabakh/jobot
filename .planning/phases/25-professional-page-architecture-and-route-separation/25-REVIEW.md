---
phase: 25-professional-page-architecture-and-route-separation
reviewed: 2026-10-28T21:15:00Z
depth: deep
files_reviewed: 13
files_reviewed_list:
  - app/web/routes.py
  - templates/base.html
  - templates/components/filter_bar.html
  - templates/pages/dashboard.html
  - templates/pages/jobs_board.html
  - templates/pages/jobs_table.html
  - templates/pages/queue.html
  - templates/pages/profile.html
  - templates/pages/settings.html
  - tests/phase25_browser.py
  - tests/test_page_routes.py
  - tests/test_profile_and_linkedin.py
  - tests/test_web_routes.py
findings:
  critical: 0
  warning: 3
  info: 0
  total: 3
status: issues_found
---

# Phase 25: Code Review Report

**Reviewed:** 2026-10-28T21:15:00Z
**Depth:** deep
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed Phase 25 commits `2afb724` and `31fc257`, including the canonical page shells, their HTMX fragment routes, and the focused regressions. All new complete-page and reused fragment routes require the current user, and the fragment data queries retain owner predicates; no confirmed authorization or tenant-isolation bypass was found. The browser acceptance runner does not execute HTMX, canonical table URLs discard valid query state, and the phase adds no cross-account regression coverage for its sensitive page composition.

## Narrative Findings (AI reviewer)

The route-to-fragment call chains were traced for dashboard, board, table, queue, profile, and settings. The page routes use `get_current_user`; their fragments independently require authentication and resolve tenant data using `current_user.id`. The findings below concern behavior and coverage that leave the new page architecture insufficiently protected from regressions.

## Warnings

### WR-01: Browser acceptance test disables the HTMX runtime it claims to verify

**File:** `tests/phase25_browser.py:77`
**Issue:** The route handler aborts every non-local request. Since `templates/base.html` loads HTMX from `https://unpkg.com`, the browser run never executes the `hx-get` requests that populate each page shell. The test only checks static `hx-get` attributes at lines 82-84 and never waits for a Kanban, table, queue, profile, or settings fragment to render. A broken or unavailable HTMX client would therefore pass the required Phase 25 browser verification while leaving every canonical page stuck on its loading placeholder.
**Fix:** Make the browser test load a local/pinned HTMX asset (or fulfill the CDN request with a known local fixture), then wait for and assert rendered fragment-specific content after each navigation. Exercise at least one filter/sort or queue/profile control through the live HTMX runtime.

### WR-02: Canonical jobs-table URLs discard valid filter and sort query state

**File:** `app/web/routes.py:345-356`
**Issue:** `/jobs/table` accepts no filter or sort parameters and its shell always loads the fixed `/web/views/table` URL in `templates/pages/jobs_table.html:5`. Consequently, a direct or refreshed canonical URL such as `/jobs/table?q=Python&sort_by=created_at&sort_order=asc` silently loads the default table rather than the established fragment semantics. This violates the phase requirement that the direct table page preserve filtering and sorting behavior and defeats bookmarkable/revisitable state.
**Fix:** Parse the supported table query parameters on the page route, preserve them in the shell's fragment `hx-get` URL (and populate the filter controls), and add route tests that verify filtered and sorted initial content after loading the canonical URL.

### WR-03: Phase 25 adds no two-account regression for page-to-fragment composition

**File:** `tests/test_page_routes.py:7-70`
**Issue:** The new route tests use one authenticated fixture and only verify shell markup. `tests/test_htmx_views.py` likewise creates data for that same owner and does not prove that a second authenticated account cannot see the first account's jobs, queue tasks, profile fields, or settings when a canonical page loads its fragment. The Phase 25 plans explicitly require two-account assertions for board/table and profile/settings composition, so a future loss of an owner predicate would not be caught by this phase's regression suite.
**Fix:** Create two users with distinct job, task, profile, and settings sentinel values; load each relevant canonical page and/or its fragment under both sessions; assert each response includes only the caller's sentinel values. Include inspector and queue mutation requests where IDs are exposed by the rendered fragment.

---

_Reviewed: 2026-10-28T21:15:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_