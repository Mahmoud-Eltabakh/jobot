---
phase: 18-live-model-discovery-for-cloud-providers-and-ollama
plan: "04"
subsystem: settings-ui
status: complete
tags: [htmx, datalist, aria-live, settings-template]
requires:
  - phase: 18-03
    provides: server OOB fragments (model-warning-*, ollama-requirements-hint, embedding-hint, model-save-warning)
provides:
  - "Refresh models button per provider card (hx-post, key in body, refresh=1)"
  - "Task model inputs bound to the selected provider's datalist; onchange rebinds without a request"
  - "aria-live slots for every server fragment from Plan 03 plus client-side 'Not in provider list' warning"
affects: [18-05]
key-files:
  modified: [templates/components/settings.html, tests/test_web_routes.py]
key-decisions:
  - Client check is one `jobotModelWarn` function (textContent only, no network); it is silent when the bound datalist is empty.
  - "`model-save-warning` and `embedding-hint` slots sit outside the `ai_routing` block so routing swaps do not duplicate them; `model-warning-task-<stage>` slots are inside it."
requirements-covered: [REQ-HYB-07, REQ-HYB-08]
requirements-completed: []
actuals:
  tokens: null
  tasks: 3
  commits: 0
actuals-basis: Token cost not measured.
completed: 2026-10-28
---

# Phase 18 Plan 04: Settings UI Summary

The unresolved Plan 03 item is closed: all four server fragment targets now exist in the template, so the already-built fragments render.

## Completed Tasks

1. **Tracer.** Each of the eight provider cards gained Refresh models (`hx-post=/api/settings/provider-models`, target `#provider-status-<p>`, `hx-disabled-elt`, parameters built in `hx-on::config-request`), helper text, `aria-describedby`, and `model-warning-<p>`. No load or focus triggers.
2. **Task inputs.** `task-<stage>-model` uses `list="provider-models-<selected provider>"`; the provider select's `onchange` rebinds the list and reruns the check. Ids and names unchanged.
3. **Warnings and slots.** `ollama-requirements-hint` (Ollama card), `embedding-hint`, `model-save-warning`, `model-warning-task-<stage>`. Save buttons are never disabled.

## Verification

Full suite with `tests/run_phase17.py tests -q`: **670 passed** (see 18-05 summary). New tests: Refresh button/secret-free render for all eight cards, slot presence and `aria-live`, no `innerHTML` in the handler, task list binding and preset retention.

## Deviations from Plan

- Edited a Plan 03 assertion in `test_save_warns_from_cached_list_without_blocking_or_rewriting`: it searched for the substring `provider-models-ollama`, which now legitimately appears in the routing block's `list=` attributes; it now checks for `id="provider-models-ollama"`.
- Client JS is a shared function in the template's existing `<script>` rather than inline per-element code; handlers are short `oninput`/`onchange` calls (existing template style).
- Warning slot tests inspect rendered HTML; no browser execution of the JS.

## Known Stubs

None.

## Remaining Risks

- The inline JS handler was not executed in a browser; keyboard operation and screen-reader announcements are unverified (human_needed).
- A server `model-warning-<p>` swap replaces the slot element without the original `min-h`/`text-amber` classes beyond what the server supplies (cosmetic).
- Task-row warning for a provider whose datalist is not yet loaded stays silent by design.

No commits, installs, network, or `data/` access.

## Self-Check: PASSED
