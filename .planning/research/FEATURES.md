# Feature Landscape

**Domain:** Hosted personal job-search copilot and application tracker
**Researched:** 2026-10-28

## Scope and Evidence

The v8.0 brief targets individual job seekers in a hosted private beta with no billing, managed AI and usage limits, and practical continuity for the existing self-hosted workflow. Team, coach, employer, public paid-launch, and BYO-key workflows are explicitly out of scope for this beta [J1]. This is a product-scope assessment, not legal advice or proof of demand.

**Evidence** below means a behavior or commitment documented in Jobot's current project/workflows, or a feature described by an official product, regulator, or standards source. Competitor pages are vendor claims, not independent user research. **Inference** means a recommended beta feature or priority based on those sources and Jobot's stated goal.

Current Jobot already has account registration/login, account-scoped data and encrypted sensitive fields; CV/profile ingestion; multi-source job scraping; fit scores with strengths and gaps; a Kanban/table tracker with notes and status history; editable generated cover letters/resume bullets; adaptive feedback; and in-app queue/system alerts [J1][J2]. The login/register and current authenticated APIs provide the account entry points [J3]. The reviewed UI/API paths did not surface a user-facing data export or account-deletion flow, managed-AI usage meter/cap controls, scheduled reminders, or a help/support entry point. This is a bounded code-path observation, not a claim that no operational process exists outside the app.

## Table Stakes

Features below are recommended for beta readiness, even where an existing Jobot capability already covers most of the workflow. Complexity refers to hosted-beta product/engineering work, not the existing self-hosted implementation.

| Feature | Why Expected | Complexity | Beta recommendation; evidence vs. inference |
|---------|--------------|------------|---------------------------------------------|
| Individual account and private workspace | Job seekers upload highly personal career history and expect their saved jobs and drafts to remain private. | Medium | **Evidence:** v8 requires account isolation; Jobot already has registration/login and owner-scoped records. **Inference:** make the hosted workspace unambiguously personal, expose basic account controls, and test that cross-account access remains impossible [J1][J3]. |
| Guided first-run setup | Empty forms and settings-heavy configuration are a poor first experience for a job seeker who wants to reach a shortlist quickly. | Medium | **Evidence:** current profile, CV upload, search-preference and provider-setting forms exist. **Inference:** guide the user through profile/CV import, target roles/locations, AI/data disclosure, and first discovery, with a useful skip/manual-entry path. Do not require LinkedIn credentials or a complete profile before discovery [J2][J4]. |
| Job discovery with source context | The central workflow is finding relevant, actionable roles; users need the original posting and enough context to judge it. | High | **Evidence:** Jobot scrapes LinkedIn, Google Jobs and StepStone and displays source, job description and an external application link. **Inference:** hosted listings should also communicate source and freshness/last-checked state, distinguish unavailable/stale postings, and never imply scraper coverage is exhaustive [J1][J2]. |
| Searchable, controllable shortlist and fit rationale | A single high score is not enough to decide whether to apply; candidates need to see the reasons and correct mismatches. | Medium | **Evidence:** Jobot provides fit scores, matching strengths, potential concerns, missing skills and configurable profile/search preferences. **Inference:** preserve readable explanations and let the user adjust or dismiss fit judgments without treating AI scores as hiring outcomes or guarantees [J2][J5]. |
| Personal application pipeline | Job seekers need to remember what they saved, applied to, and heard back about, with their own notes attached. | Low-Medium | **Evidence:** Jobot already has Kanban/table views, lifecycle stages, job notes and status history. Teal and Huntr product pages independently describe stage-based tracking, job details, notes and activity timelines as tracker functions. **Inference:** retain the existing workflow in hosted mode and make stage/date updates easy on mobile and keyboard [J2][S1][S2]. |
| Reviewable, editable application materials | Candidates need to adapt generated text to their real experience and retain the version they intend to use. | Low-Medium | **Evidence:** Jobot generates tailored cover letters/resume bullets, supports editing/saving/copying, and does not submit applications. Teal and Huntr advertise tailored documents and generation in their job-seeker products. **Inference:** keep generation explicit, preserve edits across failures, and make the user the final reviewer [J2][S1][S2]. |
| Managed-AI transparency, usage limit and user control | Hosted inference sends career content to a provider and has operating cost; surprise processing or an invisible cap undermines trust. | Medium-High | **Evidence:** v8 requires managed AI with explicit per-user limits and provider/data-processing disclosures; official OpenAI API documentation distinguishes abuse-monitoring retention from endpoint application-state retention. **Inference:** before first AI use, say what profile/job text is sent and to whom; show usage, limit and reset behavior; notify before/at the cap; stop clearly rather than silently switching providers or implying generation entitlement. Avoid unsupported generic “zero retention” promises [J1][S4]. |
| Accessible completion and failure feedback | Scraping and AI run asynchronously; a job seeker must know whether discovery/generation worked and how to recover. | Low-Medium | **Evidence:** Jobot has queue status, retry controls and in-app alerts for provider/queue failures. W3C WCAG 2.2 specifies accessible authentication, consistent placement of help mechanisms and programmatically exposed status messages. **Inference:** use accessible in-app notices for completion, failure and quota states in beta; keep help/contact discoverable from the same predictable location. Email/push delivery can wait [J2][S5]. |
| Data export and account/data deletion | Users need an exit path and confidence that stored CVs, notes and generated materials are not trapped in a hosted service. | Medium-High | **Evidence:** the European Commission's GDPR explainer lists rights including information, access, erasure and portability; exact obligations depend on launch geography and processing context. **Inference:** beta should provide self-service export of user-authored/profile/search/application data and a confirmed deletion request/action, including clear treatment of provider-held data, operational logs and backup expiry. Do not equate removing an account with immediate erasure from every backup [S3][J1]. |
| Accessible, responsive UI and support | Job search is high-stress and often done in short sessions on different devices; users need accessible operation and a route to help. | Medium | **Evidence:** WCAG 2.2 covers web use across devices, keyboard operation, accessible authentication and consistent help. Jobot has a user manual and responsive web workflows, but no in-product support entry point was found in the reviewed shell. **Inference:** make the primary workflow usable with keyboard/screen reader and small screens; offer a stable help/contact link and a safe way to report a problem without attaching CVs or secrets by default [J2][S5]. |

## Differentiators

| Feature | Value Proposition | Complexity | Evidence vs. inference |
|---------|-------------------|------------|-----------------------|
| Multi-source discovery plus fit scoring | Reduces the manual work of searching several sources and comparing roles against a real candidate profile. | High | **Evidence:** Jobot combines three scraper sources with profile-based scoring and match reasons. **Inference:** make source transparency and user-correctable fit signals part of the product story; do not claim superior coverage or accuracy without beta measurements [J1][J2]. |
| Local-first / self-hosted continuity | Gives privacy- and cost-conscious users an alternative to hosted managed AI, instead of forcing a single cloud-only workflow. | Medium-High | **Evidence:** local Ollama, owner-level routing, encrypted provider settings and local-only embeddings are existing commitments; preserving self-hosted use is an active v8 requirement. **Inference:** keep the self-hosted install path and document how it differs from hosted processing, rather than trying to make every hosted feature work offline [J1][J2]. |
| User-approved adaptive search | Search and scoring can improve from outcomes and feedback without handing control of the job hunt to automation. | Low-Medium | **Evidence:** Jobot learns from status/notes and proposes search terms/blacklist rules that users approve or dismiss. **Inference:** make this opt-in and explainable in hosted beta; never silently alter profile preferences or hide jobs based on opaque feedback [J2]. |
| Honest model and failure semantics | Clear distinctions between a model being listed, reachable and able to generate help users make informed choices. | Low-Medium | **Evidence:** Jobot's Phase 18 model suggestions are advisory, failures are explicit, and existing generation does not silently retry with another provider. **Inference:** reuse those principles for managed AI limits and outage states so users are not shown fabricated success [J1][J2]. |

## Deferred Features and Anti-Features

| Feature | Why Defer or Avoid | What to Do Instead |
|---------|--------------------|--------------------|
| Auto-apply or employer-form submission | Explicitly out of scope; creates accidental-submission, account-ban, CAPTCHA and correctness risks. | Open the employer application page and let the person review/copy materials and submit themselves [J1][J5]. |
| Team workspaces, coach/client management, recruiter/employer tools | Not the provisional customer and creates additional permissions, sharing and data-boundary decisions. | Keep one private individual workspace per account; revisit only after beta evidence changes the audience [J1]. |
| Billing, subscription plans and public paid launch | v8 is a private beta without billing; pricing and AI unit costs need validation first. | Apply a non-billable, explicit usage cap and measure demand/cost without collecting payment data [J1]. |
| BYO AI keys and hosted multi-provider choice | Explicitly deferred; expands credential support, settings and support burden before the managed-AI model is validated. | Use the selected managed provider for hosted accounts with clear disclosures and limits; retain provider choice in self-hosted installs [J1]. |
| Browser extension, universal job clipping and application autofill | Competitor products offer capture/autofill, but Jobot already discovers jobs from configured sources and this adds browser permissions plus broad site-maintenance risk. | Prioritize reliable source-based discovery and a manual save/import path; validate demand before an extension [S1][S2]. |
| Full resume-design suite, templates and PDF document builder | Larger adjacent product with rendering, formatting and export requirements; Jobot currently tailors text rather than owning a complete resume editor. | Keep generated bullets/letters editable and copyable; users continue their preferred document workflow [J2]. |
| Calendar/email integrations, recruiter CRM and automated outreach | Useful in some job trackers but require access to sensitive third-party accounts, notification consent and ongoing integration support. | Start with in-app status/queue alerts and user-entered interview/follow-up dates; add opt-in reminders only after the workflow is validated [S1][S2][S5]. |
| Opaque automated ranking, rewriting, deletion or provider fallback | Undercuts trust and can cause users to miss roles or lose saved work. | Explain fit reasons, preserve manual control, make changes reversible, and report provider failure as failure [J2][S4]. |

## Feature Dependencies

```text
Account + private workspace
  -> Profile/CV import + target preferences
  -> Job discovery + source/freshness context
  -> Fit score + explanation + user feedback
  -> Personal application stages + notes/history
  -> Review/edit/copy application materials
  -> Optional user-scheduled interview/follow-up reminders

Managed AI provider + data-processing terms + cost telemetry
  -> Per-user usage limits + usage/reset UI + quota/outage notices

Data inventory + retention/back-up policy
  -> User data export + account deletion workflow

Accessible onboarding/authentication/status patterns + stable help channel
  -> End-to-end beta workflows users can recover from
```

## MVP Recommendation

Prioritize:

1. **Personal onboarding through first useful result:** create an account, import or manually enter a profile, set roles/locations, understand AI data use, and run discovery. Preserve an easy manual path for users who do not want LinkedIn ingestion.
2. **Private shortlist-to-application loop:** source-aware discovery, understandable fit reasons, editable status/notes/history, and reviewable/copyable application materials. Add at least in-app completion/failure/quota feedback and user-entered interview/follow-up dates; keep external notifications opt-in and simple.
3. **Hosted trust controls:** clear managed-AI usage caps and processing disclosure, accessible help/contact, export and deletion flows with honest retention/back-up timing, and a documented self-hosted route.

Defer billing, BYO keys, teams/coaches/employers, universal autofill, calendar/email integrations, full resume layout tools and auto-submission. Treat quantitative activation/retention thresholds as beta questions; the project brief explicitly says these have not been set [J1].

## Unresolved Questions

- Which launch geography and user age range define applicable privacy/accessibility obligations, and who will review the privacy notice and deletion/retention language?
- Which managed AI vendor/models will process profile, CV and job text? What are the actual retention, region, subprocessors, usage/cost units and outage behaviors for the chosen endpoints?
- What are the per-user cap, reset period, and notice/appeal behavior when a user reaches the cap? Which actions count as billable/limited usage?
- What exactly must an export contain (including job descriptions, status history, materials, profile, settings, feedback and user-uploaded files), and what export formats are most useful?
- What deletion completion time can the product operationally meet across active stores, logs, provider-side state and backups?
- Are reminders needed in private beta, and if so which minimal in-app/email events and consent controls matter most? No delivery provider or support model is selected yet.
- How much self-hosted compatibility is required for v8 features, and should hosted/self-hosted have identical UI or clearly distinct capabilities?
- Which job sources are reliable and permitted for the chosen hosted market, and how should users report stale listings or coverage failures?

## Sources

### Jobot evidence

- [Project scope, requirements and v8 assumptions](../PROJECT.md)
- [Current milestone scope](../MILESTONES.md)
- [User Manual: account setup, discovery, tracking, materials, providers and recovery](../../docs/USER_MANUAL.md)
- [Auth API](../../app/api/auth.py), [Profile API](../../app/api/profile.py), [Application API](../../app/api/applications.py), and [Queue API](../../app/api/queue.py)
- [Registration and login screens](../../templates/register.html), [profile workflow](../../templates/components/profile.html), [settings](../../templates/components/settings.html), and [job inspector](../../templates/components/job_inspector.html)

### External product and official references

- [Teal Job Application Tracker](https://www.tealhq.com/tools/job-tracker) — vendor-described job bookmarking, stages, insights, checklists, notes, follow-ups and contacts.
- [Huntr Job Application Tracker](https://huntr.co/product/job-tracker) — vendor-described Kanban stages, activity/interview timeline, per-job materials, contacts and metrics.
- [Teal Privacy Policy](https://www.tealhq.com/privacy-policy) — updated 2026-08-12; describes career content, third-party AI processing, data export/deletion request routes and retention. This is an example of one vendor's policy, not a universal product rule.
- [European Commission: Information for individuals](https://commission.europa.eu/law/law-topic/data-protection/information-individuals_en) — GDPR rights overview; applicability to Jobot depends on jurisdiction and context.
- [OpenAI Platform: Data controls](https://developers.openai.com/api/docs/guides/your-data) — official, endpoint-specific API data use and retention details; not a claim about the yet-unselected Jobot provider.
- [W3C Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/) — official criteria include keyboard access, accessible authentication, consistent help and status messages.