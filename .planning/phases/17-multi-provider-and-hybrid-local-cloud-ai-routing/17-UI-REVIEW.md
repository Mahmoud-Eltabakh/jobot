---
phase: 17-multi-provider-and-hybrid-local-cloud-ai-routing
reviewed: 2026-10-28
overall_score: 17/24
findings: 1
status: advisory
---

# Phase 17 UI Review

**Evidence:** Reviewed the ten saved Playwright screenshots for Settings, routing, provider failure, rescore failure and queue at 375x812 and 1440x900. These are disposable-preview captures with mocked providers, not a live-service or assistive-technology audit. No new browser session was started.

## Scores

| Pillar | Score | Assessment |
|--------|-------|------------|
| Copywriting | 3/4 | Settings labels and recovery commands are direct. Provider diagnostics use technical terms, but include actionable context. |
| Visuals | 3/4 | The dashboard remains work-focused, with clear navigation and well-separated repeated provider controls. |
| Color | 3/4 | Success and failure states use both color and text. The established dark slate and blue/violet accent palette is consistent, though visually dominant. |
| Typography | 3/4 | Headings, labels and controls have a useful hierarchy. Long diagnostic strings wrap; long model values remain editable in their inputs. |
| Spacing | 2/4 | Desktop layouts have comfortable separation. The mobile rescore failure region is crowded and gives its diagnostic/actions too little width. |
| Experience Design | 3/4 | Routing, explicit status, and separate switch/retry actions are understandable. The narrow mobile recovery layout slows scanning and action selection. |

## Findings

### UI-01 — Mobile rescore failure controls are cramped

**Severity:** P2
**Evidence:** `rescore-failure-375.png` shows the error message and recovery controls squeezed into a narrow column between the Rescore All and Save Scoring Scales controls. Diagnostic text and button labels wrap repeatedly, making the error harder to scan and actions harder to distinguish.
**Recommendation:** At the mobile breakpoint, place the error region on its own full-width row and move the recovery buttons below the diagnostic. Keep Switch to Local Ollama and Retry as distinct actions.

## Limits

- The Phase 17 UAT recorded user acceptance of the Settings, Inspector and Queue flow at mobile and desktop sizes.
- Screenshot review does not establish exhaustive keyboard navigation, screen-reader announcements, contrast ratios, or live-provider behavior.
- No production UI changes are requested or made by this advisory review.