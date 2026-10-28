---
status: complete
phase: 18-live-model-discovery-for-cloud-providers-and-ollama
source: [18-01-SUMMARY.md, 18-02-SUMMARY.md, 18-03-SUMMARY.md, 18-04-SUMMARY.md, 18-05-SUMMARY.md]
started: 2026-10-28T06:24:54+01:00
updated: 2026-10-28T06:35:55+01:00
---

## Current Test

[testing complete]

## Tests

### 1. Live Gemini Model Refresh and Warning
expected: In the actual app, use your own Gemini key to refresh models. Confirm the returned list, enter a valid but unlisted model ID, observe the warning, and confirm Save still works without silently rewriting the model. Do not share credentials in chat.
result: pass
reported: "pass"

### 2. Ollama Missing-Model Guidance
expected: Against your intended Ollama host, confirm Test Connection and Test Local Embeddings show a display-only pull hint when `nomic-embed-text` is absent. Pull it on the Ollama host yourself, re-test, and confirm the missing-model hint disappears. Do not share endpoint credentials in chat.
result: pass
reported: "pass"

### 3. Browser Keyboard, Datalist, and Warning Accessibility
expected: At mobile and desktop widths, use the keyboard to reach and activate Refresh models. Change a task provider and confirm the model datalist follows that selection. Trigger an unlisted-model warning and confirm a screen reader announces it; controls and diagnostics remain reachable and do not overlap.
result: pass
reported: "pass"

### 4. Live Provider Listing Spot Checks
expected: In the actual app, spot-check model listing for OpenAI, Anthropic, Groq, DeepSeek, OpenRouter, and one custom OpenAI-compatible endpoint. Confirm each list belongs to the selected provider and that credentials are not shown in the URL or returned UI. Do not share credentials in chat.
result: pass
reported: "pass"

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

None reported by the user. Pending human checks are not implementation failures.

## Automated Evidence

- Latest isolated full suite: `.venv\Scripts\python.exe tests/run_phase17.py tests -q --tb=short` returned 673 passed, 4 existing deprecation warnings on Python 3.14.7. Provider transports were mocked and service sockets blocked.
- Disposable browser preview rendered eight provider cards and three task assignments. Changing Scoring provider to Gemini rebound its model input to `provider-models-gemini`. Refresh interaction did not complete from the directly loaded fragment; the user separately confirmed the browser keyboard/datalist/accessibility check.
- Phase 18 canonical verification: passed after all four UAT checks were accepted; live listing and Ollama behavior were operator-confirmed in the actual app. No credentials were shared in chat.

UAT complete: 4 passed, 0 issues. Milestone v7.0 remains active pending milestone audit/completion.