---
phase: "17"
slug: multi-provider-and-hybrid-local-cloud-ai-routing
status: verified
threats_open: 0
asvs_level: 1
created: "2026-10-28"
---

# Phase 17 — Security

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Account settings to provider adapters | Authenticated owner settings select credentials and endpoints for AI requests. | Encrypted provider keys, model IDs, endpoint configuration |
| Provider responses to application state and UI | External response bodies and failures are normalized before persistence or rendering. | Generated text, status/category diagnostics, provider metadata |
| Profile and job pipelines to vector storage | Sensitive profile/job text is embedded through the owner's configured Ollama endpoint and fixed model. | Profile, job and feedback text; local embedding vectors |
| Test harness to persistence and transport | Tests exercise real application paths with disposable storage and mocked provider transports. | Synthetic test records and fake credentials only |

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-17-01 | Information Disclosure | Factory credential lookup | high | mitigate | Owner-scoped credential resolution and two-account/global-key regression coverage in `test_ai_client.py` and `test_auth_security.py`. | closed |
| T-17-02 | Information Disclosure | Adapter exceptions | high | mitigate | Bounded normalized errors exclude keys, raw bodies, credential URLs and chained request exceptions; adversarial adapter tests. | closed |
| T-17-03 | Denial of Service | Provider HTTP clients | medium | mitigate | Bounded timeouts/retries, cancellation propagation and no automatic provider switching; mocked timeout/quota tests. | closed |
| T-17-04 | Information Disclosure | Vault and legacy routes | high | mitigate | Owner-only encrypted settings, blank-secret retention and cross-account route tests. | closed |
| T-17-05 | Tampering | Preset transaction | medium | mitigate | Validate before writes and commit atomically with rollback; injected persistence-failure tests. | closed |
| T-17-06 | Information Disclosure | Custom endpoint and diagnostic HTML | high | mitigate | Fixed provider hosts, validated custom URLs, no redirects or credential-bearing URL fields, escaped normalized diagnostics. | closed |
| T-17-07 | Information Disclosure | Worker/application/profile call sites | high | mitigate | Owner identity carried through authenticated generation paths; cross-owner and three-stage routing tests. | closed |
| T-17-08 | Information Disclosure | Profile/job/feedback embeddings | high | mitigate | Dedicated owner Ollama resolver with fixed `nomic-embed-text`; tests assert cloud generation clients are not used for embeddings. | closed |
| T-17-09 | Tampering | Failure catches and vector dimensions | high | mitigate | Typed provider failures bypass synthetic success; failure and dimension tests preserve prior records and vectors. | closed |
| T-17-10 | Information Disclosure | Settings view | high | mitigate | Render safe owner metadata only; blank password inputs and two-account non-reflection tests. | closed |
| T-17-11 | Tampering | Error fragments | high | mitigate | Escape bounded provider diagnostics and generated content; hostile response and HTML rendering tests. | closed |
| T-17-12 | Elevation of Privilege | Switch and retry | high | mitigate | Owner-checked switch and retry are distinct operations; authenticated foreign-record tests. | closed |
| T-17-13 | Tampering | Pytest fixture database clearing | high | mitigate | Every verification run uses `tests/run_phase17.py`, which establishes disposable DB/Chroma/key paths before imports and blocks service sockets. | closed |
| T-17-14 | Information Disclosure | Regression fixtures and documentation | high | mitigate | Fake credentials, secret non-reflection assertions, mocked transports and no credential disclosure in documentation. | closed |
| T-17-SC | Tampering | Dependency installation | high | mitigate | No dependency or package changes were made; new adapters use existing clients. | closed |

## Accepted Risks Log

No accepted risks.

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-28 | 15 | 15 | 0 | GitHub Copilot, ASVS L1 plan-register review |

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-28. ASVS Level 1 closure uses the complete plan-time threat register and available automated evidence; no separate deep security-auditor run was performed.

## Security Audit 2026-10-28

| Metric | Count |
|---|---|
| Threats found | 15 |
| Closed | 15 |
| Open | 0 |
