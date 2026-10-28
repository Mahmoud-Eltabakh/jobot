# Phase 17 Source Pattern Map

Date: 2026-10-27. Planner-authored from inspected current source/tests; not an independently dispatched pattern-mapper result. Read actual dirty source before execution.

| Role / file | Existing API or pattern | Plan / required change |
|-------------|-------------------------|------------------------|
| Client: app/ai/client.py | BaseAIClient.generate(prompt, system_prompt=None, json_mode=True); abstract embed; get_ai_client(session=None, user_id=None) | 01: preserve arguments, add task_type keyword-only, safe error, native adapters and local resolver. |
| Settings persistence: app/db/database.py | get_user_setting(session, user_id, key, default); set_user_setting(..., sensitive=False) commits | 02: optional commit=True, batch helper, same-owner legacy migration. |
| Encryption: app/security/encryption.py | encrypt_text/decrypt_text user_id-bound; enc:v2 envelope | Reuse unchanged; tests inspect ciphertext and wrong-owner failure. |
| Ownership: app/db/ownership.py | get_user_profile(..., decrypt=True), owned_by_id, single-owner legacy row migration | Reuse exact record checks; never infer global secret ownership from first login. |
| Settings API: app/api/settings.py | Authenticated router; /ai, /test-ai, /ollama/models, get_all_settings, upload_cv_document, rescore_all_jobs_endpoint | 02: owner-only metadata/endpoints/credentials on every route; local upload vectors, scoring rescore; 04: routing fragment wiring. |
| Queue worker: app/queue/worker.py | _handle_full_discovery, _handle_evaluate_job; self.ai_client injection; TaskQueue error state | 03: scraping vs scoring clients from task owner; safe failed task, preserve concurrency. |
| Strategy: app/scrapers/query_strategist.py | generate_search_queries(session, ..., ai_client=None, user_id=None) | 03: scraping, owned config; JSON object queries envelope for compatible providers; provider errors bypass rule fallback. |
| Extractor: app/scrapers/ai_extractor.py | extract_from_html(..., ai_client=None); AIExtractedJobListing.model_validate | 03: optional owner context, scraping; do not use nonexistent extract_job_listing. |
| Scheduler: app/scrapers/scheduler.py | ScraperPipeline.run_full_pipeline(..., user_id=None) | 03: split scraping/scoring resolutions, retain explicit client injection behavior. |
| Evaluation: app/ai/evaluator.py | evaluate_job, evaluate_and_update_job, rescore_all_jobs | 03: local vectors separate from generation; typed failures bypass broad direct-score catches. |
| Vectors: app/ai/embeddings.py | ProfileEmbedder.embed_and_store_profile / compute_semantic_similarity take ai_client | 03: retain old arguments but local resolver/keyword test embedding_client; fail non-destructively for wrong dimensions. |
| Feedback: app/ai/feedback.py | record_job_feedback / compute_feedback_score_adjustment directly call ai_client.embed | 03: both paths local; carry owner context, do not broaden ownership. |
| Applying: app/ai/application_generator.py | generate_cover_letter / generate_tailored_resume_points, save_material | 03: applying default with owner; explicit errors, no template saves. |
| API applying: app/api/applications.py | /api/jobs/{job_id}/cover-letter/generate and /tailor-resume/generate check owned job | 03: inject owner applying client and preserve current response contracts on success. |
| Profile: app/api/profile.py and app/ai/linkedin_analyzer.py | update_profile, generate_profile_bio_api, sync_linkedin_to_profile(session,...,user_id) | 03: scraping generation and local vector clients passed separately; partial failure truthful. |
| Web: app/web/routes.py | get_settings_view; web application/profile/rescore paths; queue owned task retry | 04: safe display, explicit injecting clients, correct HTMX failure swaps, separate local switch/retry. |
| Templates | components/settings.html, job_inspector.html, queue_view.html | 04: extend AI region, not nonexistent queue.html; preserve unrelated controls. |
| Tests | tests/conftest.py register_test_account/authenticated_client; SQLModel clearing fixture | All: temporary DB/vector/key environment before imports; no live credentials. |

## Verification Reuse

Use tests/test_ai_client.py and tests/test_auth_security.py for factory/vault, tests/test_db.py for transactions, tests/test_ai_scraping.py and tests/test_parallel_execution.py for stage/worker, tests/test_embeddings.py and tests/test_feedback.py for local vectors, tests/test_application_generator.py and tests/test_profile_and_linkedin.py for generation/profile, tests/test_web_routes.py and tests/test_htmx_views.py for fragments. Final cross-boundary behavior belongs in tests/test_e2e_workflow.py. No redundant provider/routing test files or framework installs required.

## Dependency and File Coupling

Wave 1 / 17-01 -> Wave 2 / 17-02 -> Wave 3 / 17-03 -> Wave 4 / 17-04 -> Wave 5 / 17-05. Each wave has one plan. Shared API/test/web files intentionally make these sequential; no same-wave ownership overlap. Inside each plan tasks run 1, 2, 3. Plan 03 has three slices of five modified files each, not one unbounded integration edit. Use focused tests after each source slice.