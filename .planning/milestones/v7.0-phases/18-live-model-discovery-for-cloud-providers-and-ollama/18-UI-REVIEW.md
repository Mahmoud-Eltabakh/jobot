# Phase 18 - UI Review

**Audited:** 2026-10-28  
**Baseline:** Phase 17 UI contract (`17-UI-SPEC.md`) and abstract six-pillar standards  
**Screenshots:** Not captured; no integrated browser/screenshot tool was available in this session.  
**Interaction captures:** Off (interaction capture is not enabled in `.planning/config.json`). The disposable preview evidence below is user-provided; the direct Refresh action was inconclusive.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 4/4 | Action labels and non-blocking model guidance are specific and truthful. |
| 2. Visuals | 3/4 | Responsive structure is present; no screenshot was available for independent visual confirmation. |
| 3. Color | 4/4 | Save, test, and warning states use the contract's semantic palette and text/symbol cues. |
| 4. Typography | 3/4 | Task model controls do not explicitly use the contract's 14px input size. |
| 5. Spacing | 3/4 | Model-warning slots and their server replacements do not preserve the specified stable 24px status area. |
| 6. Experience Design | 3/4 | Good native controls and live feedback; OOB warning replacements drop `role="status"`, and pending buttons lack `aria-busy`. |

**Overall: 20/24**

## Top 3 Priority Fixes

1. **Preserve status semantics and height on OOB warning fragments** - Refresh/test/save feedback can lose the template slot's status role and reserved space after a swap - include `role="status"` and the stable minimum-height class in the server fragments.
2. **Normalize task model control typography** - Routing inputs/selects can render at the inherited body size rather than the specified 14px - apply `text-sm` consistently to the routing controls.
3. **Expose pending state accessibly** - HTMX disables Refresh while pending, but there is no `aria-busy` state - set and clear `aria-busy` for the pending action while retaining the existing live status text.

## Detailed Findings

### Pillar 1: Copywriting (4/4)

- **Positive:** `Refresh models`, `Test Connection`, and `Save Credentials` name their actions; "Models are suggestions; type any ID." makes the free-text behavior clear (`templates/components/settings.html:117-130`).
- **Positive:** The client warning says the model is not listed, that saving remains possible, and that generation may fail; it is not framed as a hard validation error (`templates/components/settings.html:609-616`).
- No generic “Submit”, “OK”, or “Click Here” copy was found in the Phase 18 controls.

### Pillar 2: Visuals (3/4)

- **WARNING:** Provider cards use a one-column default and two-column `lg` layout; action groups wrap and controls use `min-w-0`, which supports narrow layouts (`templates/components/settings.html:101-105`, `120-130`, `141-148`). The UAT records mobile/desktop review as passed, but no screenshots were captured here, so spacing, overlap, and rendered hierarchy were not independently checked.
- **WARNING:** The server warning fragment replaces its template slot with a different class set, so its vertical footprint may change after the first response (`app/api/settings.py:298`). See the spacing finding below.

### Pillar 3: Color (4/4)

- **Positive:** Save uses emerald, Test Connection uses sky, and warning states use amber; these match the design contract's declared action/status palette (`templates/components/settings.html:118`, `121-130`, `148`, `162`).
- **Positive:** The unlisted-model warning includes a warning symbol and words, not color alone. The server fragment retains an amber tone for the unlisted state (`templates/components/settings.html:615`, `app/api/settings.py:294-298`).
- No new arbitrary color literals or registry-provided components were found. `components.json` is absent and the UI spec declares no third-party registries, so registry safety audit was not applicable.

### Pillar 4: Typography (3/4)

- **WARNING:** Provider cards set `text-sm` on the form, but the routing form does not; its select and model input also omit `text-sm` (`templates/components/settings.html:105`, `140-148`). With the page body inheriting the base font size, these task controls may render at 16px instead of the UI contract's 14px body/input size. Apply the same explicit sizing to the routing controls.
- **Positive:** Provider headings use 14px semibold, the section heading uses 16px semibold, and helper/warning text uses 12px, matching the contract's hierarchy (`templates/components/settings.html:100`, `105-106`, `117-118`).

### Pillar 5: Spacing (3/4)

- **WARNING:** The client-side warning slots reserve only 16px, while the UI contract calls for a stable 24px status area. More importantly, the OOB provider fragment replaces the original slot without any minimum-height class, and the save-warning fragment also has no reserved height (`templates/components/settings.html:118`, `148`, `159-162`; `app/api/settings.py:298`, `716`). A warning appearing or clearing can shift nearby card content. Preserve a 24px minimum on both slot and replacement fragments.
- **Positive:** Provider cards have 16px padding, card gaps are 16px, and the new action controls meet the contract's 36px minimum height (`templates/components/settings.html:101-105`, `120-130`).

### Pillar 6: Experience Design (3/4)

- **WARNING:** Initial client warning slots have `role="status"`, but the server OOB replacement includes `aria-live="polite"` without restoring `role="status"` (`templates/components/settings.html:118`, `148`; `app/api/settings.py:298`). The live-region attribute remains, and UAT reports that warning announcements passed, but preserving the role makes the state consistent across updates.
- **WARNING:** Refresh disables itself during the request and updates a polite status message, but no `aria-busy` attribute is present for the pending action (`templates/components/settings.html:122-125`).
- **Positive:** Discovery is an explicit POST action, not triggered on page load or focus. Datalists preserve free-text entry; changing a task provider rebinds its model list; warning updates use `textContent` and do not block Save (`templates/components/settings.html:115-125`, `143-148`, `609-616`).
- **Verification limit:** `18-UAT.md` records all four operator checks as passed, including live provider/Ollama checks and browser accessibility. The disposable preview showed eight provider cards, three task assignments, and Scoring rebinding to `provider-models-gemini`; its direct-fragment Refresh action did not complete. These mocked preview observations do not establish real-provider behavior. `18-VERIFICATION.md` still marks truth 9 `HUMAN_NEEDED` and says browser/live shapes were not performed, so that artifact conflicts with the later accepted UAT. Treat UAT results as operator-attested, not independently reproduced in this audit.

## Files Audited

- `templates/components/settings.html`
- `app/api/settings.py` (model-warning and save-warning fragments)
- `.planning/phases/17-multi-provider-and-hybrid-local-cloud-ai-routing/17-UI-SPEC.md`
- `.planning/phases/18-live-model-discovery-for-cloud-providers-and-ollama/18-04-PLAN.md`
- `.planning/phases/18-live-model-discovery-for-cloud-providers-and-ollama/18-04-SUMMARY.md`
- `.planning/phases/18-live-model-discovery-for-cloud-providers-and-ollama/18-UAT.md`
- `.planning/phases/18-live-model-discovery-for-cloud-providers-and-ollama/18-VERIFICATION.md`