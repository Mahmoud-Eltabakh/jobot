---
phase: "18"
slug: live-model-discovery-for-cloud-providers-and-ollama
status: verified
threats_open: 0
asvs_level: 1
created: "2026-10-28"
---

# Phase 18 - Security

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Authenticated owner to settings routes | Owner selects a provider, submits refresh/test forms, and receives a model list. | Provider ID, model ID, optional key and endpoint |
| Jobot to provider or Ollama endpoint | Server requests bounded model-list JSON using the selected owner's credential. | Credential header, provider listing request |
| Provider response to cache and UI | Untrusted model IDs are bounded, filtered, normalized, escaped, then cached per owner/provider/endpoint/key digest. | Model IDs and non-secret status hints |
| Test harness to storage and transport | Tests use isolated persistence paths and mock provider transports. | Disposable test records and sentinel credentials only |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-18-01 | Information Disclosure | Listing requests, errors, logs and HTML | high | mitigate | Credentials stay in headers; route posts credentials in the body; bounded AIProviderError messages and sentinel leak tests. | closed |
| T-18-02 | Spoofing / Tampering (SSRF) | User-supplied custom/Ollama endpoint | medium | accept | D-08 intentionally permits trusted private/LAN Ollama and Custom endpoints; authenticated owner configuration, HTTP(S) URL hygiene, no userinfo/query/fragment, redirects off, bounded requests, and filtered response fields. Private-network denylist is intentionally absent. | closed - accepted risk |
| T-18-03 | Denial of Service | Hostile or oversized listing | medium | mitigate | Request deadlines, 1 MiB body cap, 10-page/500-model caps, refresh cooldown and no retries; pagination cursors are validated. | closed |
| T-18-04 | Tampering | Model IDs rendered into HTML | high | mitigate | MODEL_ID_PATTERN filtering, deduplication and HTML escaping before datalist rendering. | closed |
| T-18-05 | Information Disclosure | Cross-owner cache hit | high | mitigate | Cache key includes owner, provider, normalized endpoint and credential fingerprint; two-account isolation tests. | closed |
| T-18-06 | Information Disclosure | Key material in memory or repr | high | mitigate | Catalog stores only a salted truncated key digest; sentinel key is absent from repr and stored keys. | closed |
| T-18-07 | Denial of Service | Refresh spam and provider quota | medium | mitigate | Five-second owner/provider cooldown, single-flight fetch and 256-entry cap. | closed |
| T-18-08 | Elevation of Privilege / Information Disclosure | Credential use in discovery, test and save | high | mitigate | Clients are built through owner-scoped provider configuration; no global-key fallback; changed unsaved endpoint cannot inherit a saved key. | closed |
| T-18-09 | Tampering (XSS) | Model warnings and Ollama hints | high | mitigate | Server-generated warnings, pattern-validated model names and escaped inert hint text; hostile-name tests. | closed |
| T-18-10 | Tampering (Command Injection) | Ollama pull hint | medium | mitigate | Pull command is display-only text; no command is executed or proxied; invalid model names are omitted. | closed |
| T-18-11 | Tampering | Silent configured-model rewrite | medium | mitigate | Validation is advisory; saves preserve the submitted model and tests assert no silent rewrite. | closed |
| T-18-12 | Tampering (XSS) | Datalist options and warning slots | high | mitigate | Escaped server fragments and client-side `textContent`; tests forbid `innerHTML` in the warning handler. | closed |
| T-18-13 | Information Disclosure | Refresh/test form transport | medium | mitigate | Refresh uses POST; password fields remain empty; test keys are not placed in URLs or rendered attributes. | closed |
| T-18-14 | Denial of Service | Accidental discovery storms | low | mitigate | Discovery is button-triggered only, refresh controls disable while pending, and server cooldown bounds repeated requests. | closed |
| T-18-15 | Information Disclosure | Cross-owner cache/credential reuse | high | mitigate | Authenticated two-account route tests require the second owner's own key and cache entry. | closed |
| T-18-16 | Information Disclosure | Test credentials or network leakage | medium | mitigate | Sentinel credentials, MockTransport and `tests/run_phase17.py` socket blocking with disposable storage. | closed |
| T-18-17 | Repudiation | Documentation overstates provider verification | low | mitigate | User documentation distinguishes advertised models from generation entitlement; completion status is updated after UAT. | closed |
| T-18-SC | Tampering | Dependency installation | high | mitigate | No package installs or dependency changes were made. | closed |

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-18-01 | T-18-02 | Private-network endpoints are required for self-hosted/LAN Ollama. Endpoint hygiene, owner authentication, bounded requests and redirect blocking reduce exposure; no private-address denylist is applied. | Project decision D-08 | 2026-10-28 |

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-28 | 18 | 18 | 0 | GitHub Copilot, ASVS L1 plan-register review |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-28. ASVS Level 1 plan-register review; no separate deep security-auditor run was performed.

## Security Audit 2026-10-28

| Metric | Count |
|---|---|
| Threats found | 18 |
| Closed | 18 |
| Open | 0 |
