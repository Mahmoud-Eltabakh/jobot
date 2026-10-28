"""Disposable localhost-only preview and real-browser acceptance for Plan 17-04."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


def serve(port):
    root = Path(tempfile.mkdtemp(prefix="jobot-17-04-preview-"))
    os.environ.update(DATABASE_URL=f"sqlite:///{(root / 'preview.db').as_posix()}",
                      CHROMA_DIR=str(root / "chroma"), ENCRYPTION_KEY_FILE=str(root / "key"),
                      JOBOT_TESTING="1", ENV="testing", ANONYMIZED_TELEMETRY="False")
    import inspect
    import socket
    original_connect = socket.socket.connect

    def guarded_connect(connection, address):
        if any(frame.function == "_fallback_socketpair" for frame in inspect.stack()):
            return original_connect(connection, address)
        raise AssertionError(f"Preview service connection blocked: {address}")

    socket.socket.connect = guarded_connect
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.ai.client import AIProviderError, OllamaAIClient, OpenAICompatibleClient, AnthropicClient, GeminiClient
    from app.auth.security import create_user_session, hash_password
    from app.db.database import engine, init_db
    from app.db.models import User, UserProfile, Job, ScrapeTask
    from app.main import app
    from fastapi.responses import RedirectResponse
    from sqlmodel import Session
    import asyncio

    state = {"health_calls": 0, "generate_calls": 0, "models": [], "health": "ok",
             "rescore_failure": "", "rescore_calls": 0}

    from app.api import settings as settings_api
    from app.ai.evaluator import JobEvaluator
    original_factory = settings_api.get_ai_client

    def scoring_factory(*args, **kwargs):
        if state["rescore_failure"] == "configuration":
            raise AIProviderError("openai", "preview-model", "configuration")
        if state["rescore_failure"]:
            return OllamaAIClient(model="preview-model")
        return original_factory(*args, **kwargs)

    async def rescore(**kwargs):
        state["rescore_calls"] += 1
        if state["rescore_failure"] == "rate_limit":
            raise AIProviderError("openai", "preview-model", "rate_limit", 429)
        if state["rescore_failure"] == "local_embedding":
            raise AIProviderError("ollama", "nomic-embed-text", "unavailable")
        return 1

    settings_api.get_ai_client = scoring_factory
    JobEvaluator.rescore_all_jobs = rescore

    async def health(client):
        state["health_calls"] += 1
        await asyncio.sleep(0.35)
        if state["health"] != "ok":
            return {"healthy": False, "category": state["health"]}
        return {"healthy": True, "available_models": state["models"]}

    async def generate(client, *args, **kwargs):
        state["generate_calls"] += 1
        if client.provider != "ollama":
            raise AIProviderError(client.provider, client.model, "rate_limit", 429)
        return "Disposable local response. </textarea><script>window.injected=true</script>"

    async def embed(client, text):
        return [1.0, 0.0]

    for adapter in (OllamaAIClient, OpenAICompatibleClient, AnthropicClient, GeminiClient):
        adapter.check_health_details = health
        adapter.generate = generate
        adapter.embed = embed
    init_db()
    with Session(engine) as session:
        user = User(email="preview@example.test", full_name="Disposable Demo", password_hash=hash_password("DisposableDemo123"))
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(UserProfile(user_id=user.id, full_name="Disposable Demo", skills_json='["Python"]'))
        job = Job(user_id=user.id, source="preview", title="Preview Python Engineer", company="Disposable Example", location="Remote", url="https://example.test/preview", fit_score=90, dedup_hash="preview")
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id
        session.add(ScrapeTask(user_id=user.id, task_type="evaluate_job", payload_json=json.dumps({"job_id": job.id}), status="failed", error_message="rate_limit: Provider rate limit reached."))
        session.commit()
        token = create_user_session(session, user.id).session_token

    @app.get("/__preview")
    def preview_login():
        response = RedirectResponse("/")
        response.set_cookie("jobot_session", token, httponly=True, samesite="lax")
        return response

    @app.get("/__preview/state")
    def preview_state():
        with Session(engine) as session:
            return {**state, "stored_score": session.get(Job, job_id).fit_score}

    @app.post("/__preview/state")
    def update_preview_state(values: dict):
        state.update({key: value for key, value in values.items() if key in ("models", "health", "rescore_failure")})
        return state

    @app.post("/__preview/shutdown")
    def shutdown_preview():
        server.should_exit = True
        return {"stopping": True}

    print(f"DISPOSABLE PREVIEW http://127.0.0.1:{port}/__preview STORAGE {root}", flush=True)
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    server.run()


def browse(port):
    from playwright.sync_api import sync_playwright, expect
    output = Path(tempfile.mkdtemp(prefix="jobot-17-04-browser-"))
    base = f"http://127.0.0.1:{port}"
    evidence = {"url": base + "/__preview", "artifacts": str(output), "checks": []}
    print(f"Browser artifacts: {output}", flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        errors = []
        provider_payloads = []
        cover_payloads = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: provider_payloads.append(request.post_data) if request.url.endswith("/api/settings/test-provider") else None)
        page.on("request", lambda request: cover_payloads.append(request.post_data) if request.url.endswith("/cover-letter/generate") else None)
        page.goto(base + "/__preview")
        page.wait_for_load_state("networkidle")
        page.locator('nav button[hx-get="/web/views/settings"]').click()
        expect(page.locator("#ai-providers")).to_be_visible()
        expect(page.locator('[id^="provider-form-"]')).to_have_count(8)
        assert page.request.get(base + "/__preview/state").json()["health_calls"] == 0
        assert page.locator('input[type="password"]').evaluate_all("fields => fields.every(field => field.value === '')")
        evidence["checks"].append("Settings navigation/HTMX, eight forms, blank passwords, zero automatic health calls")
        page.get_by_role("button", name="Max Quality Cloud", exact=True).click()
        expect(page.locator("#ai-routing-feedback")).to_contain_text("Save an OpenAI key")
        assert page.locator('#task-applying-provider').input_value() == "ollama"
        evidence["checks"].append("422 missing-key preset visible; assignments unchanged")
        page.locator("#provider-key-openai").fill("fake-preview-only")
        page.locator("#provider-form-openai").get_by_role("button", name="Save Credentials").click()
        expect(page.locator("#provider-save-openai")).to_have_text("Saved")
        expect(page.locator("#provider-key-openai")).to_have_value("")
        expect(page.locator("#provider-secret-state-openai")).to_have_text("Saved")
        page.locator("#provider-key-groq").fill("unsaved-preserved")
        for label, expected in (("Cost-Optimized Hybrid", ["ollama", "ollama", "openai"]), ("Max Quality Cloud", ["openai"] * 3), ("100% Free / Local", ["ollama"] * 3)):
            page.get_by_role("button", name=label, exact=True).click()
            for stage, provider in zip(("scraping", "scoring", "applying"), expected):
                expect(page.locator(f"#task-{stage}-provider")).to_have_value(provider)
            assert page.locator("#provider-key-groq").input_value() == "unsaved-preserved"
            assert page.evaluate("document.activeElement.id") == {"Cost-Optimized Hybrid": "preset-hybrid", "Max Quality Cloud": "preset-cloud", "100% Free / Local": "preset-local"}[label]
        evidence["checks"].append("All three presets persist/swap six fields; credential inputs preserved")
        for stage, provider, model in (("scraping", "gemini", "owner-scraping"), ("scoring", "groq", "owner-scoring"), ("applying", "openai", "owner-applying")):
            page.locator(f"#task-{stage}-provider").select_option(provider)
            page.locator(f"#task-{stage}-model").fill(model)
        page.get_by_role("button", name="Save Routing", exact=True).click()
        expect(page.locator("#ai-routing-feedback")).to_contain_text("Saved")
        page.locator('nav button[hx-get="/web/views/settings"]').click()
        for stage, provider, model in (("scraping", "gemini", "owner-scraping"), ("scoring", "groq", "owner-scoring"), ("applying", "openai", "owner-applying")):
            expect(page.locator(f"#task-{stage}-provider")).to_have_value(provider)
            expect(page.locator(f"#task-{stage}-model")).to_have_value(model)
        for field in page.locator('input[type="password"]').all():
            expect(field).to_have_value("")
        evidence["checks"].append("Three independent provider/model pairs persist after Settings navigation; saved passwords remain blank")
        for models in ([], ["only-model"], ["one", "two", "<script>unsafe</script>"]):
            page.request.post(base + "/__preview/state", data={"models": models})
            page.locator("#provider-model-ollama").fill("chosen-model")
            test = page.locator("#provider-form-ollama").get_by_role("button", name="Test Connection")
            test.click()
            expect(page.locator("#provider-status-ollama")).to_have_text("Testing...")
            assert test.is_disabled()
            expect(page.locator("#provider-status-ollama")).to_have_text("Connected")
            expect(page.locator("#provider-models-ollama option")).to_have_count(len(models))
            assert page.locator("#provider-model-ollama").input_value() == "chosen-model"
            assert page.locator("#provider-status-openai").inner_text() == "Unchecked"
        evidence["checks"].append("Explicit zero/one/many discovery retains model; loading disabled; status isolation; escaped model suggestions")
        for provider in ("openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom"):
            if provider != "openai":
                page.locator(f"#provider-key-{provider}").fill("fake-transient-only")
            if provider == "custom":
                page.locator("#provider-url-custom").fill("http://127.0.0.1:9999/v1")
                page.locator("#provider-model-custom").fill("custom-chosen")
            page.locator(f"#provider-form-{provider}").get_by_role("button", name="Test Connection").click()
            expect(page.locator(f"#provider-status-{provider}")).to_have_text("Reachable; credentials unverified")
        from urllib.parse import parse_qs
        assert all(set(parse_qs(payload, keep_blank_values=True)) == {"provider", "api_key", "base_url", "model"} for payload in provider_payloads)
        evidence["checks"].append("All eight tests use provider-only POST fields and independent targets; model listing never claims generation entitlement")
        page.request.post(base + "/__preview/state", data={"health": "authentication"})
        page.locator("#provider-form-openai").get_by_role("button", name="Test Connection").click()
        expect(page.locator("#provider-status-openai")).to_contain_text("authentication")
        page.locator("#provider-model-openai").fill("long-model-" + "x" * 180)
        page.request.post(base + "/__preview/state", data={"health": "ok", "models": ["nomic-embed-text:latest"]})
        page.get_by_role("button", name="Test Local Embeddings").click()
        expect(page.locator("#embedding-status")).to_have_text("Connected")
        evidence["checks"].append("Provider authentication error visible; explicit fixed-local embedding status")
        for width, height in ((375, 812), (1440, 900)):
            page.set_viewport_size({"width": width, "height": height})
            page.locator("#ai-providers").scroll_into_view_if_needed()
            page.locator("#ai-providers").evaluate("element => element.parentElement.scrollTop += element.getBoundingClientRect().top - element.parentElement.getBoundingClientRect().top - 16")
            page.evaluate("window.scrollTo(0,0)")
            page.screenshot(path=str(output / f"settings-{width}.png"))
            overflow = page.evaluate("({viewport: innerWidth, document: document.documentElement.scrollWidth, providers: document.getElementById('ai-providers').scrollWidth, providerWidth: document.getElementById('ai-providers').clientWidth})")
            evidence[f"layout-{width}"] = overflow
            assert overflow["document"] <= width, overflow
            assert overflow["providers"] <= overflow["providerWidth"], overflow
            page.locator("#provider-key-ollama").focus()
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.id") == "provider-url-ollama"
            page.locator("#ai-routing-controls").scroll_into_view_if_needed()
            page.evaluate("window.scrollTo(0,0)")
            page.screenshot(path=str(output / f"routing-{width}.png"))
        evidence["checks"].append("375x812 and 1440x900 screenshots, no horizontal overflow, keyboard focus")
        for failure, category in (("configuration", "configuration"), ("rate_limit", "rate_limit"), ("local_embedding", "unavailable")):
            page.request.post(base + "/__preview/state", data={"rescore_failure": failure})
            page.get_by_role("button", name="Rescore All Stored Jobs", exact=True).click()
            feedback = page.locator("#scales-save-feedback")
            expect(feedback).to_contain_text(category)
            before_switch = page.request.get(base + "/__preview/state").json()["rescore_calls"]
            feedback.get_by_role("button", name="Switch to Local Ollama", exact=True).click()
            expect(feedback.locator(".local-routing-feedback")).to_contain_text("All three task assignments")
            current = page.request.get(base + "/__preview/state").json()
            assert current["rescore_calls"] == before_switch
            assert current["stored_score"] == 90
            if failure == "local_embedding":
                for width, height in ((375, 812), (1440, 900)):
                    page.set_viewport_size({"width": width, "height": height})
                    feedback.scroll_into_view_if_needed()
                    page.screenshot(path=str(output / f"rescore-failure-{width}.png"))
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.request.post(base + "/__preview/state", data={"rescore_failure": "success"})
            feedback.get_by_role("button", name="Retry", exact=True).click()
            expect(feedback).to_contain_text("Rescored 1 Jobs Successfully")
            assert page.request.get(base + "/__preview/state").json()["rescore_calls"] == before_switch + 1
        page.request.post(base + "/__preview/state", data={"rescore_failure": ""})
        evidence["checks"].append("Settings rescore configuration/429/local-outage HTML swaps; scores preserved; switch does not rescore; separate Retry succeeds")
        page.request.post(base + "/api/settings/ai", form={"task_applying_provider": "openai"})
        page.request.post(base + "/api/settings/ai", form={"task_applying_model": "long-model-" + "x" * 180})
        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator('nav button[hx-get="/web/views/kanban"]').click()
        page.get_by_text("Preview Python Engineer", exact=True).click()
        expect(page.locator("#inspector-drawer")).to_contain_text("Evaluation failed")
        page.locator("#tab-btn-cover-letter").click()
        instructions = 'Keep "Python" & </textarea><script>window.injected=true</script> literal.'
        page.locator('#cover-letter-options-1 [name="tone"]').select_option("direct")
        page.locator('#cover-letter-options-1 [name="custom_instructions"]').fill(instructions)
        page.locator('#inspector-drawer form[hx-post$="/cover-letter/generate"] button[type="submit"]').click()
        expect(page.locator("#cover-letter-container")).to_contain_text("rate_limit")
        before_switch = page.request.get(base + "/__preview/state").json()["generate_calls"]
        page.locator("#cover-letter-container").get_by_role("button", name="Switch to Local Ollama", exact=True).click()
        expect(page.locator("#cover-letter-container .local-routing-feedback")).to_contain_text("All three task assignments")
        assert page.request.get(base + "/__preview/state").json()["generate_calls"] == before_switch
        expect(page.locator('#cover-letter-options-1 [name="tone"]')).to_have_value("direct")
        expect(page.locator('#cover-letter-options-1 [name="custom_instructions"]')).to_have_value(instructions)
        tasks = page.request.get(base + "/api/queue/status").json()
        assert tasks["stats"]["failed"] == 1
        for width, height in ((375, 812), (1440, 900)):
            page.set_viewport_size({"width": width, "height": height})
            page.screenshot(path=str(output / f"failure-{width}.png"))
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator("#cover-letter-container").get_by_role("button", name="Retry", exact=True).click()
        expect(page.locator("#cover-letter-text")).to_have_value("Disposable local response. </textarea><script>window.injected=true</script>")
        assert page.evaluate("window.injected === undefined")
        assert page.request.get(base + "/__preview/state").json()["generate_calls"] == before_switch + 1
        assert len(cover_payloads) == 2
        assert parse_qs(cover_payloads[0]) == parse_qs(cover_payloads[1]) == {"tone": ["direct"], "custom_instructions": [instructions]}
        evidence["checks"].append("Inspector 429 visible; switch changes assignments without generation/retry; separate local Retry preserves direct tone and literal instructions; generated textarea escaped")
        page.locator("#inspector-drawer").evaluate("element => element.innerHTML = ''")
        page.locator('nav button[hx-get="/web/views/queue"]').click()
        expect(page.locator("#queue-routing-feedback-1")).to_be_attached()
        page.locator('button[hx-post="/api/settings/ai/preset"]').click()
        expect(page.locator("#queue-routing-feedback-1")).to_contain_text("Local routing saved")
        assert page.request.get(base + "/api/queue/status").json()["stats"]["failed"] == 1
        page.locator('button[hx-post="/web/queue/tasks/1/retry"]').click()
        expect(page.locator('button[hx-post="/web/queue/tasks/1/retry"]')).to_have_count(0)
        evidence["checks"].append("Queue local switch leaves task failed; independent owned Retry changes task to pending")
        for width, height in ((375, 812), (1440, 900)):
            page.set_viewport_size({"width": width, "height": height})
            page.evaluate("window.scrollTo(0,0)")
            page.screenshot(path=str(output / f"queue-{width}.png"))
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.request.post(base + "/api/settings/ai", form={"task_scraping_provider": "openai", "task_scraping_model": "owner-scraping"})
        profile_response = page.request.get(base + "/web/views/profile")
        assert profile_response.status == 200, profile_response.text()[:500]
        assert "bio-textarea-container" in profile_response.text(), profile_response.text()[:500]
        with page.expect_response("**/web/views/profile") as navigation:
            page.locator('nav button[hx-get="/web/views/profile"]').click()
        assert navigation.value.status == 200
        expect(page.locator("#bio-textarea-container")).to_be_visible()
        page.locator('button[hx-post="/web/profile/generate-bio"]').click()
        expect(page.locator("#bio-textarea-container")).to_contain_text("rate_limit")
        evidence["checks"].append("Profile bio provider failure is visibly swapped without synthetic success")
        evidence["page_errors"] = errors
        assert not errors, errors
        browser.close()
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("serve", "browse"))
    parser.add_argument("--port", type=int, default=18764)
    args = parser.parse_args()
    if args.mode == "serve":
        serve(args.port)
    else:
        try:
            browse(args.port)
        finally:
            from urllib.request import Request, urlopen
            try:
                urlopen(Request(f"http://127.0.0.1:{args.port}/__preview/shutdown", data=b"", method="POST"), timeout=5).close()
            except OSError:
                pass