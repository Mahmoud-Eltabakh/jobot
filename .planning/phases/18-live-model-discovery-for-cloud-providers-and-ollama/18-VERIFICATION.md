---
phase: 18-live-model-discovery-for-cloud-providers-and-ollama
status: passed
verified: 2026-10-28
score: 9/9
---

# Phase 18 Verification (goal-backward)

**Goal:** Stale or wrong model IDs (Gemini 404, missing Ollama model) are caught before a task runs, using live per-provider model lists offered as validated selections in Settings.

Evidence base: `.venv\Scripts\python.exe tests/run_phase17.py tests -q --tb=short` -> 677 passed, 0 failed, 4 existing warnings on Python 3.14.7 (mocked transports, sockets guarded). Operator UAT is recorded separately in `18-UAT.md`.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Each provider lists models via an owner-scoped POST; filtered, bounded, escaped | VERIFIED | `tests/test_ai_client.py` listing tests; `test_provider_models_*` in `tests/test_web_routes.py` |
| 2 | Lists cached per owner/provider/endpoint/key; refresh cooldown; invalidated on key/endpoint change | VERIFIED | `tests/test_model_catalog.py`; `test_provider_models_refresh_cooldown_and_cache`, `test_saving_a_new_key_invalidates_cached_listing` |
| 3 | Gemini listed-but-unusable/absent model is flagged, never rewritten | VERIFIED (mocked) | `test_gemini_test_flags_model_missing_from_live_list_*`, `test_incident_gemini_*` |
| 4 | Ollama missing chat model and `nomic-embed-text` produce display-only `ollama pull` hints | VERIFIED (mocked) | `test_ollama_test_reports_missing_*`, `test_incident_ollama_*`, `test_test_embeddings_adds_pull_hint_*` |
| 5 | Save warns from cache only, non-blocking, no network | VERIFIED | `test_save_warns_from_cached_list_*`, `test_save_without_cache_*` |
| 6 | Settings UI: Refresh models, datalists, free text, accessible non-blocking warnings, server slots present | VERIFIED (render only) | `test_settings_provider_cards_*`, `test_settings_has_server_fragment_slots_*`, `test_task_model_inputs_bind_*` |
| 7 | Owner isolation; no key, env-key or cross-account reuse | VERIFIED | `test_second_owner_cannot_reuse_*`, `test_cache_is_not_shared_between_owners`, `test_discovery_never_falls_back_to_environment_key` |
| 8 | No secret leakage in URLs, bodies, logs, catalog repr, Settings HTML | VERIFIED | `test_sentinel_key_never_leaks_across_discovery_flows` (7 providers), render test |
| 9 | Real providers/Ollama return payloads the adapters parse; the inline JS and a11y behave in a browser | VERIFIED (operator UAT) | User confirmed all four checks in `18-UAT.md`: Gemini list/warning/save, Ollama missing-model hints and re-test, browser keyboard/datalist/screen-reader behavior, and provider listing spot checks. No credentials were shared in chat. |

## Human verification completed

The operator confirmed the four checklist items in `18-UAT.md` as passed. This is user-reported acceptance, not independent reproduction by the verifier. Provider listing success still does not establish generation entitlement, billing readiness or output quality.

## Notes

- Independent code review is recorded clean in `18-REVIEW.md`; the Nyquist audit is in `18-VALIDATION.md`. REQ-QUAL-01 comment coverage remains unmeasured and explicitly partial.
- Healthy provider tests now cost two provider GETs (health plus cached listing).
- Task-provider changes that auto-fill a default model may warn about a value the owner did not type.
- Documentation (USER_MANUAL, CONTRIBUTING) is synchronized with the implementation and current UAT status.
