---
phase: "17"
slug: multi-provider-and-hybrid-local-cloud-ai-routing
status: draft
shadcn_initialized: false
preset: none
created: "2026-10-27"
---

# Phase 17 UI Design Contract

Autonomous planning assumptions based on existing Settings/queue/inspector templates and D-09. No independent UI researcher/checker or human acceptance claimed. Follow autonomous-ui-design-contract: frontend=true, no UI-SPEC at entry, autonomous generation non-blocking. This draft supplies the missing implementation contract; no redesign or frontend implementation is authorized in this planning run.

## Design System

| Property | Value |
|----------|-------|
| Tool / component registry | none; existing server-rendered Jinja |
| Styling / interactions | Existing Tailwind CDN and HTMX 1.9.12 |
| Font | Inherit current font-sans and font-mono; no global typography change |
| Icons | Reuse current inline outline icon convention; accessible labels/tooltips for icon-only commands |
| Surfaces | Extend only AI Settings section, inspector failure area and queue_view diagnostics |

No installed component-library inventory applies. Reuse actual templates, not a new design system. Settings sections remain unframed/within the existing page container; repeated provider items may have borders with at most 8px radius, no nested decorative cards or hero sections.

## Spacing Scale

4px icon gaps; 8px control gaps/padding; 16px provider-item padding and form groups; 24px section spacing; 32px major separation where the existing page uses it. New controls use 36px minimum height and stable status area min-height 24px. Preserve unrelated existing spacing, including 12px gaps where already established. No viewport-scaled fonts or negative letter spacing.

## Typography

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body / input / status | 14px | 400 | 1.5 |
| Label / metadata | 12px | 500 | 1.5 |
| Section heading | 16px | 600 | 1.5 |
| Provider heading | 14px | 600 | 1.5 |

Use inherit at page boundary, font-mono only for identifiers/endpoints. No display/hero typography. Wrap long text, use min-w-0/w-full and overflow-wrap:anywhere where needed; never hide actionable errors in tooltips.

## Color

Preserve established slate surfaces (#020617/#0f172a), readable slate text (#e2e8f0), emerald success/action (#34d399), sky links (#38bdf8), amber warning (#fbbf24) and rose failure (#fb7185). Existing design preservation takes precedence over introducing a new theme. Status always has words, not color alone. Accent reserved for Save/Test/preset actions, focus and explicit status states; no ornamental gradients or new illustrations.

## Layout and Controls

- Settings navigation remains the entry point; no new page. Eight provider items in a one-column mobile/two-column desktop grid, stable DOM IDs and individually labeled password/model/endpoint fields. Native details/summary may collapse configured non-active providers without removing their form state.
- A provider Test Connection form sends only provider, api_key, base_url and model for that provider; Save Credentials uses provider_{provider}_key naming in the owner save form. No nested forms; test commands associate via form/hx-include scoped to the current item. Every secret value attribute is empty; saved state uses has_key only. Ollama token is optional.
- Three stage rows: Scraping, Scoring, Applying; native provider selects plus editable model fields/datalist. Seven cloud/local choices plus custom are available independently per stage. Task model hints never force an unrequested swap. Embeddings is read-only Ollama / nomic-embed-text.
- Routing block ID ai-routing-controls; feedback ID ai-routing-feedback; provider statuses provider-status-{provider}. Test status and routing feedback are aria-live=polite; failures role=alert. Pending buttons disabled/aria-busy until completion, other provider items remain usable.
- All provider tests are explicit. Settings GET shows saved config without network probing. A cloud models-list success is not a verified-generation badge.
- Successful preset swaps only the routing block/feedback, preserves credential entries and focus, and displays persisted six-field values. 422 errors need explicit HTMX handling and must be visible without clearing choices. Do not rely on HTMX default swapping non-2xx bodies.
- Manual Switch to Local Ollama posts preset=local and changes all three assignments; it never retries a task or regenerates material. Existing Retry/Generate controls are separate explicit actions, bound to the owned task/job. No combined action or automatic request replay.

## Copywriting Contract

| Element | Copy |
|---------|------|
| Section title | AI Providers |
| Credential save | Save Credentials |
| Routing save | Save Routing |
| Provider test | Test Connection |
| Secret empty / saved state | Not configured / Saved |
| Health untouched / pending | Unchecked / Testing... |
| Health success | Connected (only verified reachability/auth aspects) |
| Unverified credential state | Reachable; credentials unverified |
| Missing key | API key required for {provider}. |
| Auth rejection | Authentication failed for {provider}. |
| Rate/quota/timeout | Rate limit reached. / Provider quota exhausted. / Provider request timed out. |
| Preset rejection | Save an OpenAI key before applying this preset. |
| Local unavailable | Ollama unavailable. |
| Local embedding row | Ollama / nomic-embed-text / Local |
| Presets | 100% Free / Local; Cost-Optimized Hybrid; Max Quality Cloud |
| Manual switch / subsequent retry | Switch to Local Ollama / Retry |
| Switch saved status | Local routing saved. |

Use concise operational text only; guidance belongs in manuals. The three requested labels do not imply measured quality/cost. No new destructive action is introduced; existing clear/delete confirmations remain unchanged.

## UI Considerations

Applicable state considerations resolved as explicit implementation criteria below, with visual evidence still pending. These are authored state contracts from inspected surfaces, not a claim that the separate UI probe/checker ran.

| Category | Element(s) | Status | Resolution / Reason |
|----------|------------|--------|---------------------|
| empty | Provider forms | covered (explicit) | Password values remain empty, show only Not configured/Saved; no keys reflected. |
| loading | Test commands/status | covered (explicit) | Each provider test updates only its own aria-live status and never returns saved credential values. |
| populated | Stage assignment form | covered (explicit) | Preset success refreshes persisted provider/model values for scraping, scoring and applying. |
| error | Preset and generation fragments | covered (explicit) | Missing-key preset rejection preserves saved assignments and displays a visible error; successful presets refresh saved selectors. |
| partial | Mixed credential state | covered (explicit) | Eight providers remain independently configurable and testable when only some have saved keys. |
| zero-one-many | Ollama models select | covered (explicit) | Zero discovered models leaves an editable model field; one/many retain the chosen value without selecting a different model automatically. |
| overflow / long-text / focus | Whole touched UI | covered (explicit) | Loading, empty, saved, error and partial states remain keyboard reachable; no control or diagnostic overflows at 375px and 1440px. |

Plan 04 must lift each explicit criterion into must_haves and verify it through API/template tests plus execution-time Playwright DOM/screenshot assertions. No unsupported visual check is silently passed.

## Registry Safety

No registries/packages/assets added. Keep current HTMX/Tailwind loading; no npm, shadcn or remote component installation. Provider secrets never enter query strings, localStorage or rendered hidden values.

## Checker Sign-Off

- [ ] Copywriting, visuals, color, typography and spacing independently checked.
- [ ] Registry safety and inventory non-applicability independently checked.
- [ ] Desktop/mobile browser evidence obtained during execution.

Approval: pending independent UI check; autonomous authoring is not human approval.