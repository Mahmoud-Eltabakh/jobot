"""Tests for base web router and settings API endpoints."""

import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.database import engine, get_user_setting, init_db
from app.db.models import FilterRule
from app.main import app


@pytest.fixture(autouse=True)
def setup_db(monkeypatch) -> None:
    init_db()
    monkeypatch.setattr("app.ai.client.OllamaAIClient.fetch_available_models", AsyncMock(return_value=[]))
    monkeypatch.setattr("app.ai.client.OllamaAIClient.check_health_details", AsyncMock(return_value={"healthy": True, "available_models": []}))


def test_index_page_rendering() -> None:
    """Verify GET / returns 200 OK HTML containing Jobot shell."""
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Jobot" in resp.text
        assert "view-container" in resp.text


def test_provider_settings_are_explicit_and_secret_free(authenticated_client, monkeypatch):
    """Opening Settings must not contact a model host or rehydrate secrets."""
    async def forbidden(*args, **kwargs):
        raise AssertionError("Settings GET performed provider discovery")

    monkeypatch.setattr("app.ai.client.OllamaAIClient.fetch_available_models", forbidden)
    response = authenticated_client.get("/web/views/settings")
    assert response.status_code == 200
    from bs4 import BeautifulSoup
    document = BeautifulSoup(response.text, "html.parser")
    for provider in ("ollama", "openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom"):
        assert len(document.select(f"#provider-status-{provider}")) == 1
        assert document.select_one(f"#provider-form-{provider}")
    assert all(not field.get("value") for field in document.select('input[type="password"]'))
    assert "Tailscale SSH Remote Access" in response.text
    assert "Concurrency" in response.text


def test_routing_fragments_and_missing_key_preserve_assignments(authenticated_client):
    """Preset swaps contain saved controls; rejected presets target only feedback."""
    response = authenticated_client.post("/api/settings/ai/preset", data={"preset": "local"}, headers={"HX-Request": "true", "HX-Target": "ai-routing-controls"})
    assert response.status_code == 200
    assert 'id="ai-routing-controls"' in response.text
    before = authenticated_client.get("/api/settings").json()
    rejected = authenticated_client.post("/api/settings/ai/preset", data={"preset": "cloud"}, headers={"HX-Request": "true", "HX-Target": "ai-routing-controls"})
    assert rejected.status_code == 422
    assert rejected.headers["HX-Retarget"] == "#ai-routing-feedback"
    assert "Save an OpenAI key" in rejected.text
    after = authenticated_client.get("/api/settings").json()
    assert all(before[key] == after[key] for key in before if key.startswith("task_"))


@pytest.mark.parametrize("save_first", [False, True])
def test_installation_local_defaults_match_settings_probe_save_and_presets(authenticated_client, authenticated_user, monkeypatch, save_first):
    """Ownerless non-secret defaults must describe the host execution will use."""
    from app.ai.client import get_ai_client, get_embedding_client
    from app.db.database import set_app_setting, set_user_setting

    endpoint, model = "http://installation-local.invalid:11434", "installed-local-model"
    set_app_setting("ollama_base_url", endpoint)
    set_app_setting("ollama_model", model)
    set_app_setting("provider_ollama_key", "installation-secret-not-for-owner")
    observed = []

    async def health(client):
        observed.append((client.base_url, client.model, client._headers))
        return {"healthy": True, "available_models": []}

    monkeypatch.setattr("app.ai.client.OllamaAIClient.check_health_details", health)
    before = authenticated_client.get("/api/settings").json()
    assert before["providers"]["ollama"]["base_url"] == endpoint
    assert before["providers"]["ollama"]["model"] == model
    assert all(before[f"task_{stage}_model"] == model for stage in ("scraping", "scoring", "applying"))
    probe = authenticated_client.post("/api/settings/test-provider", data={"provider": "ollama"})
    assert probe.status_code == 200
    assert observed == [(endpoint, model, {})]
    if save_first:
        saved = authenticated_client.post("/api/settings/ai/credentials", data={
            "ollama_base_url": before["providers"]["ollama"]["base_url"],
            "ollama_model": before["providers"]["ollama"]["model"], "provider_ollama_key": "",
        })
        assert saved.status_code == 200
    with Session(engine) as session:
        owner = authenticated_user["id"]
        assert get_embedding_client(session, owner).base_url == endpoint
        assert get_ai_client(session, owner).model == model
        assert not get_user_setting(session, owner, "provider_ollama_key", "")
        set_user_setting(session, owner, "provider_openai_key", "test-owner-key")
    for preset in ("local", "hybrid"):
        assert authenticated_client.post("/api/settings/ai/preset", data={"preset": preset}).status_code == 200
        values = authenticated_client.get("/api/settings").json()
        with Session(engine) as session:
            for stage in ("scraping", "scoring", "applying"):
                client = get_ai_client(session, owner, task_type=stage)
                assert client.model == values[f"task_{stage}_model"]
                if preset == "local" or stage != "applying":
                    assert client.model == model
                    assert client.base_url == endpoint
                    assert not client._headers


@pytest.mark.parametrize("provider", ["openai", "custom"])
def test_installation_provider_defaults_match_owner_routing(authenticated_client, authenticated_user, monkeypatch, provider):
    """Non-secret defaults agree without borrowing installation or orphan keys."""
    from bs4 import BeautifulSoup
    from app.ai.client import AIProviderError, get_ai_client
    from app.core.config import get_settings
    from app.db.database import set_app_setting, set_user_settings

    owner = authenticated_user["id"]
    model = "installation-openai-model" if provider == "openai" else "owner-custom-model"
    set_app_setting("ai_provider", provider)
    set_app_setting("openai_model", "installation-openai-model")
    set_app_setting("openai_api_key", "installation-legacy-secret")
    set_app_setting(f"provider_{provider}_key", "installation-vault-secret")
    monkeypatch.setattr(get_settings(), "openai_api_key", "environment-secret")
    with Session(engine) as session:
        set_user_settings(session, owner, {
            "custom_model": "owner-custom-model", "provider_custom_url": "http://owner-custom.invalid/v1",
            "openai_api_key": "orphan-owner-legacy-secret",
        })
        with pytest.raises(AIProviderError) as failure:
            get_ai_client(session, owner)
        assert (failure.value.provider, failure.value.model, failure.value.category) == (provider, model, "configuration")
    values = authenticated_client.get("/api/settings").json()
    assert values["ai_provider"] == provider
    assert not values["providers"][provider]["has_key"]
    document = BeautifulSoup(authenticated_client.get("/web/views/settings").text, "html.parser")
    for stage in ("scraping", "scoring", "applying"):
        assert values[f"task_{stage}_provider"] == provider
        assert values[f"task_{stage}_model"] == model
        assert document.select_one(f'select[name="task_{stage}_provider"] option[selected]')["value"] == provider
        assert document.select_one(f'input[name="task_{stage}_model"]')["value"] == model
    missing = authenticated_client.post("/api/settings/test-ai", data={})
    assert missing.status_code == 422
    assert "API key required" in missing.text
    observed = []

    async def health(client):
        observed.append((client.provider, client.model, client.base_url, client.client.api_key))
        return {"healthy": True}

    monkeypatch.setattr("app.ai.client.OpenAICompatibleClient.check_health_details", health)
    with Session(engine) as session:
        set_user_settings(session, owner, {f"provider_{provider}_key": "fake-owner-key"})
    assert authenticated_client.post("/api/settings/test-ai", data={}).status_code == 200
    assert authenticated_client.post("/api/settings/test-provider", data={"provider": provider}).status_code == 200
    for data in ({"task_scoring_model": model}, {"task_scoring_provider": provider},
                 {key: value for key, value in values.items() if key.startswith("task_")}):
        assert authenticated_client.post("/api/settings/ai", data=data).status_code == 200
        with Session(engine) as session:
            for stage in ("scraping", "scoring", "applying"):
                client = get_ai_client(session, owner, task_type=stage)
                assert (client.provider, client.model, client.client.api_key) == (provider, model, "fake-owner-key")
                assert all(item == (provider, model, client.base_url, "fake-owner-key") for item in observed)
    with Session(engine) as session:
        set_user_settings(session, owner, {"provider_openai_key": "fake-owner-openai-key"})
    for preset in ("local", "hybrid", "cloud"):
        assert authenticated_client.post("/api/settings/ai/preset", data={"preset": preset}).status_code == 200
        current = authenticated_client.get("/api/settings").json()
        with Session(engine) as session:
            for stage in ("scraping", "scoring", "applying"):
                expected = "openai" if preset == "cloud" or preset == "hybrid" and stage == "applying" else "ollama"
                expected_model = "gpt-4o-mini" if expected == "openai" else current["ollama_model"]
                client = get_ai_client(session, owner, task_type=stage)
                assert (client.provider, client.model) == (expected, expected_model)
                assert (current[f"task_{stage}_provider"], current[f"task_{stage}_model"]) == (expected, expected_model)


@pytest.mark.parametrize("kind", ["cover-letter", "tailor-resume"])
@pytest.mark.parametrize("category,status", [("rate_limit", 429), ("quota", 402), ("timeout", None)])
@pytest.mark.parametrize("provider", ["openai", "ollama"])
def test_web_generation_safe_failure(authenticated_client, authenticated_user, monkeypatch, kind, category, status, provider):
    from app.ai.client import AIProviderError
    from app.db.models import Job, ApplicationMaterial
    from unittest.mock import AsyncMock
    with Session(engine) as session:
        job = Job(user_id=authenticated_user["id"], title="Engineer", company="Example", location="Remote", source="test", url="https://example.test/job", dedup_hash="web-failure")
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id
    def resolve(*, task_type, session, user_id):
        assert task_type == "applying"
        assert user_id == authenticated_user["id"]
        raise AIProviderError(provider, "model-</textarea><script>alert(1)</script>", category, status)
    monkeypatch.setattr("app.web.routes.get_ai_client", resolve)
    response = authenticated_client.post(f"/web/job/{job_id}/{kind}/generate")
    assert response.status_code == (503 if provider == "ollama" else 502)
    assert "Switch to Local Ollama" in response.text
    assert "Retry" in response.text
    assert "<script>alert" not in response.text
    with Session(engine) as session:
        assert not session.exec(select(ApplicationMaterial)).all()


def test_generated_textarea_is_escaped(authenticated_client, authenticated_user, monkeypatch):
    from app.db.models import Job
    from unittest.mock import AsyncMock
    with Session(engine) as session:
        job = Job(user_id=authenticated_user["id"], title="Engineer", company="Example", location="Remote", source="test", url="https://example.test/job", dedup_hash="web-escape")
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id
    monkeypatch.setattr("app.web.routes.ApplicationGenerator.generate_cover_letter", AsyncMock(return_value='</textarea><script>alert(1)</script>'))
    response = authenticated_client.post(f"/web/job/{job_id}/cover-letter/generate")
    assert response.status_code == 200
    assert "<script>alert" not in response.text
    assert "&lt;/textarea&gt;" in response.text


@pytest.mark.parametrize("tone", ["direct", "enthusiastic", "conversational"])
def test_cover_letter_retry_preserves_original_options(authenticated_client, authenticated_user, monkeypatch, tone):
    """The external options form remains the source of a manual retry's values."""
    from bs4 import BeautifulSoup
    from app.ai.application_generator import ApplicationGenerator
    from app.ai.client import AIProviderError
    from app.db.database import set_user_settings
    from app.db.models import ApplicationMaterial, Job

    owner = authenticated_user["id"]
    instructions = 'Keep "Python" & </textarea><script>unsafe</script> literal.'
    with Session(engine) as session:
        job = Job(user_id=owner, title="Engineer", company="Example", location="Remote", source="test",
                  url="https://example.test/retry-options", dedup_hash="retry-options")
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id
        ApplicationGenerator.save_material(session, job_id, "cover_letter", "Existing letter", user_id=owner)
        set_user_settings(session, owner, {"task_applying_provider": "openai", "task_applying_model": "test-model", "provider_openai_key": "fake-test-only"})
    generator = AsyncMock(side_effect=[AIProviderError("openai", "test-model", "rate_limit", 429), "Replacement letter"])
    monkeypatch.setattr("app.web.routes.ApplicationGenerator.generate_cover_letter", generator)
    url = f"/web/job/{job_id}/cover-letter/generate"
    original = BeautifulSoup(authenticated_client.get(f"/web/job/{job_id}/inspect").text, "html.parser")
    options = original.select_one(f'form[hx-post="{url}"]')
    response = authenticated_client.post(url, data={"tone": tone, "custom_instructions": instructions})
    assert response.status_code == 502
    retry = BeautifulSoup(response.text, "html.parser").find("button", string="Retry")
    assert retry.get("hx-include") == f"#cover-letter-options-{job_id}"
    assert options["id"] == f"cover-letter-options-{job_id}"
    assert options.select_one('[name="custom_instructions"]') is not None
    assert instructions not in response.text
    with Session(engine) as session:
        assert session.exec(select(ApplicationMaterial)).one().content_markdown == "Existing letter"
    assert authenticated_client.post("/api/settings/ai/preset", data={"preset": "local"}).status_code == 200
    assert generator.await_count == 1
    options.select_one('[name="custom_instructions"]').string = instructions
    submitted = {field["name"]: field.get_text() for field in options.select("textarea[name]")}
    submitted["tone"] = tone
    recovered = authenticated_client.post(retry["hx-post"], data=submitted)
    assert recovered.status_code == 200
    assert generator.await_count == 2
    for call in generator.await_args_list:
        assert call.kwargs["tone"] == tone
        assert call.kwargs["custom_instructions"] == instructions
    assert generator.await_args_list[1].kwargs["ai_client"].provider == "ollama"
    with Session(engine) as session:
        material = session.exec(select(ApplicationMaterial)).one()
        assert (material.content_markdown, material.tone) == ("Replacement letter", tone)


def test_failed_job_panel_and_switch_do_not_retry(authenticated_client, authenticated_user):
    import json
    from app.db.models import Job, ScrapeTask
    with Session(engine) as session:
        job = Job(user_id=authenticated_user["id"], title="Engineer", company="Example", location="Remote", source="test", url="https://example.test/job", dedup_hash="panel")
        session.add(job)
        session.commit()
        session.refresh(job)
        task = ScrapeTask(user_id=authenticated_user["id"], task_type="evaluate_job", payload_json=json.dumps({"job_id": job.id}), status="failed", error_message="rate_limit: Provider rate limit reached.")
        session.add(task)
        session.commit()
        session.refresh(task)
        task_id, job_id = task.id, job.id
    inspector = authenticated_client.get(f"/web/job/{job_id}/inspect")
    assert "Switch to Local Ollama" in inspector.text
    assert f"/web/queue/tasks/{task_id}/retry" in inspector.text
    queue = authenticated_client.get("/web/views/queue")
    assert "Switch to Local Ollama" in queue.text
    response = authenticated_client.post("/api/settings/ai/preset", data={"preset": "local"})
    assert response.status_code == 200
    with Session(engine) as session:
        assert session.get(ScrapeTask, task_id).status == "failed"


@pytest.mark.parametrize("models", [[], ["only-model"], ["one", "two", "<script>unsafe</script>"]])
def test_explicit_discovery_keeps_editable_model(authenticated_client, monkeypatch, models):
    from unittest.mock import AsyncMock
    monkeypatch.setattr("app.ai.client.OllamaAIClient.check_health_details", AsyncMock(return_value={"healthy": True, "available_models": models}))
    response = authenticated_client.post("/api/settings/test-provider", data={"provider": "ollama", "model": "chosen-model"})
    assert response.status_code == 200
    assert 'id="provider-models-ollama"' in response.text
    assert 'hx-swap-oob="outerHTML"' in response.text
    assert "<script>unsafe" not in response.text
    assert "selected" not in response.text


def test_keyless_save_keeps_secret_state_truthful(authenticated_client):
    response = authenticated_client.post("/api/settings/ai/credentials", data={"ollama_model": "chosen-local", "provider_ollama_key": ""}, headers={"HX-Target": "provider-save-ollama"})
    assert response.status_code == 200
    assert 'id="provider-secret-state-ollama"' in response.text
    assert "Not configured" in response.text


def test_custom_provider_model_hint_keeps_precedence_over_legacy(authenticated_client, authenticated_user, monkeypatch):
    """Sharing defaults must retain explicit provider hint precedence in probes."""
    from app.db.database import set_user_settings
    with Session(engine) as session:
        set_user_settings(session, authenticated_user["id"], {
            "ai_provider": "custom", "openai_model": "legacy-model", "custom_model": "explicit-model",
            "provider_custom_url": "http://custom.invalid/v1", "provider_custom_key": "fake-test-only",
        })
    observed = []

    async def health(client):
        observed.append(client.model)
        return {"healthy": True}

    monkeypatch.setattr("app.ai.client.OpenAICompatibleClient.check_health_details", health)
    assert authenticated_client.get("/api/settings").json()["providers"]["custom"]["model"] == "explicit-model"
    assert authenticated_client.post("/api/settings/test-provider", data={"provider": "custom"}).status_code == 200
    assert observed == ["explicit-model"]


def test_cv_provider_failure_returns_safe_fragment(authenticated_client, monkeypatch):
    from app.ai.client import AIProviderError
    monkeypatch.setattr("app.api.settings.CVParser.extract_text_from_bytes", lambda *args: "Private CV")
    def fail(*args, **kwargs):
        raise AIProviderError("openai", "gpt-4o-mini", "rate_limit", 429)
    monkeypatch.setattr("app.api.settings.get_ai_client", fail)
    response = authenticated_client.post("/api/settings/upload-cv", files={"file": ("cv.txt", b"Private CV", "text/plain")})
    assert response.status_code == 502
    assert "rate_limit" in response.text
    assert "HX-Redirect" not in response.headers


@pytest.mark.parametrize("failure", ["configuration", "rate_limit", "local_embedding"])
def test_settings_rescore_safe_failure_preserves_scores(authenticated_client, authenticated_user, monkeypatch, failure):
    """Factory and runtime failures use bounded feedback without mutating scores."""
    from bs4 import BeautifulSoup
    from app.ai.client import AIProviderError, MockAIClient
    from app.db.database import set_user_setting
    from app.db.models import Job

    owner = authenticated_user["id"]
    with Session(engine) as session:
        job = Job(user_id=owner, title="Engineer", company="Example", location="Remote", source="test",
                  url="https://example.test/rescore", dedup_hash="rescore-failure",
                  fit_score=81, fit_summary="Existing score", pros_json='["Existing evidence"]')
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id
        if failure == "configuration":
            set_user_setting(session, owner, "task_scoring_provider", "openai")
    category = "unavailable" if failure == "local_embedding" else failure
    provider = "ollama" if failure == "local_embedding" else "openai"
    error = AIProviderError(provider, "model-</p><script>unsafe</script>" + "x" * 500, category,
                            429 if failure == "rate_limit" else None)
    similarity = AsyncMock(return_value=0.5)
    scoring = AsyncMock(side_effect=error)
    if failure != "configuration":
        monkeypatch.setattr("app.api.settings.get_ai_client", lambda *args, **kwargs: MockAIClient())
    if failure == "local_embedding":
        similarity.side_effect = error
    monkeypatch.setattr("app.ai.embeddings.ProfileEmbedder.compute_semantic_similarity", similarity)
    monkeypatch.setattr("app.ai.feedback.FeedbackManager.compute_feedback_score_adjustment", AsyncMock(return_value=(0, [])))
    monkeypatch.setattr("app.ai.evaluator.JobEvaluator.evaluate_job", scoring)
    with TestClient(app, raise_server_exceptions=False) as client:
        client.cookies.update(authenticated_client.cookies)
        response = client.post("/api/settings/rescore-all", headers={"HX-Target": "scales-save-feedback"})
    assert response.status_code == (503 if provider == "ollama" else 502)
    assert category in response.text
    assert len(response.text) < 2500
    assert "<script>unsafe" not in response.text
    document = BeautifulSoup(response.text, "html.parser")
    retry = document.find("button", string="Retry")
    assert retry["hx-post"] == "/api/settings/rescore-all"
    assert retry["hx-target"] == "#scales-save-feedback"
    assert "Switch to Local Ollama" in response.text
    assert response.headers["HX-Reswap"] == "innerHTML"
    calls = (similarity.await_count, scoring.await_count)
    assert authenticated_client.post("/api/settings/ai/preset", data={"preset": "local"}).status_code == 200
    assert (similarity.await_count, scoring.await_count) == calls
    with Session(engine) as session:
        stored = session.get(Job, job_id)
        assert (stored.fit_score, stored.fit_summary, stored.pros_json) == (81, "Existing score", '["Existing evidence"]')


def test_settings_api_routes(authenticated_client: TestClient, authenticated_user: dict) -> None:
    """Verify settings REST API endpoints."""
    client = authenticated_client
    resp_get = client.get("/api/settings")
    assert resp_get.status_code == 200
    assert "ai_provider" in resp_get.json()

    resp_post = client.post(
        "/api/settings/ai",
        data={
            "ai_provider": "openai",
            "openai_model": "gpt-4o",
            "openai_api_key": "sk-test-secret",
        },
    )
    assert resp_post.status_code == 200
    with Session(engine) as session:
        assert get_user_setting(session, authenticated_user["id"], "ai_provider") == "openai"

    resp_rule = client.post(
        "/api/settings/rules",
        data={"rule_type": "title", "pattern": "Executive Vice President"},
    )
    assert resp_rule.status_code == 200

    with Session(engine) as session:
        rule = session.exec(
            select(FilterRule).where(
                FilterRule.pattern == "Executive Vice President",
                FilterRule.user_id == authenticated_user["id"],
            )
        ).first()
        assert rule is not None
        rule_id = rule.id

    resp_del = client.delete(f"/api/settings/rules/{rule_id}")
    assert resp_del.status_code == 200

    resp_models = client.get("/api/settings/ollama/models?ollama_base_url=http://127.0.0.1:11434")
    assert resp_models.status_code == 200
    assert "ollama_model" in resp_models.text

    resp_weights = client.post(
        "/api/settings/scoring-weights",
        data={
            "weight_skills": "80",
            "weight_title": "10",
            "weight_location": "5",
            "weight_experience": "5",
            "weight_vector": "15",
        },
    )
    assert resp_weights.status_code == 200
    assert "Scoring Weights Saved" in resp_weights.text
    with Session(engine) as session:
        assert get_user_setting(session, authenticated_user["id"], "weight_skills") == 80.0


def test_tailscale_settings_render_and_persist(
    authenticated_client: TestClient,
    authenticated_user: dict,
) -> None:
    """Render and save the safe Tailscale SSH connection preferences."""
    client = authenticated_client
    settings_view = client.get("/web/views/settings")
    assert settings_view.status_code == 200
    assert "Tailscale SSH Remote Access" in settings_view.text
    assert "/api/settings/tailscale/status" in settings_view.text

    response = client.post(
        "/api/settings/remote-access",
        data={
            "tailscale_enabled": "true",
            "tailscale_hostname": "jobot-host.example.ts.net",
            "tailscale_ssh_user": "jobot-user",
            "tailscale_ssh_port": "22",
            "tailscale_app_port": "8000",
            "tailscale_magic_dns": "true",
        },
    )

    assert response.status_code == 200
    assert "settings saved" in response.text
    with Session(engine) as session:
        user_id = authenticated_user["id"]
        assert get_user_setting(session, user_id, "tailscale_enabled") is True
        assert get_user_setting(session, user_id, "tailscale_hostname") == "jobot-host.example.ts.net"
        assert get_user_setting(session, user_id, "tailscale_ssh_user") == "jobot-user"


def test_tailscale_settings_reject_unsafe_host(authenticated_client: TestClient) -> None:
    """Reject host input that could turn copied SSH guidance into a shell payload."""
    response = authenticated_client.post(
        "/api/settings/remote-access",
        data={
            "tailscale_hostname": "host; shutdown",
            "tailscale_ssh_user": "jobot-user",
            "tailscale_ssh_port": "22",
            "tailscale_app_port": "8000",
        },
    )

    assert response.status_code == 422


def test_tailscale_status_when_client_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
    authenticated_client: TestClient,
) -> None:
    """Status endpoint remains responsive when the Tailscale CLI is unavailable."""
    monkeypatch.setattr("app.api.settings.shutil.which", lambda command: None)

    response = authenticated_client.get("/api/settings/tailscale/status")

    assert response.status_code == 200
    assert "Not installed" in response.text


# --- Phase 18: live model discovery routes ----------------------------------

def _gemini_catalog(requests):
    def handler(request):
        import httpx
        requests.append(request)
        return httpx.Response(200, json={"models": [
            {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-3-pro", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/<img src=x onerror=alert(1)>", "supportedGenerationMethods": ["generateContent"]},
        ]})
    return handler


def test_provider_models_gemini_saved_key_returns_escaped_datalist(authenticated_client, provider_transport):
    """Owner-saved Gemini key lists models through POST; key stays in headers only."""
    key = "AIza-route-secret-key-0002"
    saved = authenticated_client.post("/api/settings/ai/credentials", data={"provider_gemini_key": key})
    assert saved.status_code == 200
    requests = []
    provider_transport(_gemini_catalog(requests))
    response = authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini"})
    assert response.status_code == 200
    assert 'id="provider-status-gemini"' in response.text
    assert '<datalist id="provider-models-gemini" hx-swap-oob="outerHTML">' in response.text
    assert '<option value="gemini-2.5-flash">' in response.text and "gemini-3-pro" in response.text
    assert "<img" not in response.text and "onerror" not in response.text
    assert "2 models listed" in response.text
    assert key not in response.text
    assert requests and all(key not in str(request.url) and request.headers["x-goog-api-key"] == key for request in requests)


def test_provider_models_without_key_is_rejected_without_request(authenticated_client, provider_transport):
    """No owner key means the existing 422 fragment and no outbound call."""
    requests = []
    provider_transport(_gemini_catalog(requests))
    response = authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini"})
    assert response.status_code == 422
    assert 'id="provider-status-gemini"' in response.text
    assert requests == []


def test_provider_models_fixed_cloud_endpoint_override_is_rejected(authenticated_client, provider_transport):
    """Fixed cloud hosts cannot be redirected through the discovery route."""
    requests = []
    provider_transport(_gemini_catalog(requests))
    response = authenticated_client.post("/api/settings/provider-models", data={
        "provider": "gemini", "api_key": "AIza-override-0012", "base_url": "http://evil.invalid"})
    assert response.status_code == 422
    assert "AIza-override-0012" not in response.text and requests == []


def test_provider_models_custom_lan_endpoint_is_allowed(authenticated_client, provider_transport):
    """D-08: URL hygiene only, so a LAN custom endpoint lists through the mocked transport."""
    import httpx
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"data": [{"id": "local-llm"}, {"id": "text-embedding-x"}]})

    provider_transport(handler)
    response = authenticated_client.post("/api/settings/provider-models", data={
        "provider": "custom", "api_key": "lan-key-0013", "base_url": "http://192.168.1.15:8080/v1", "model": "local-llm"})
    assert response.status_code == 200
    assert 'value="local-llm"' in response.text and "text-embedding-x" not in response.text
    assert str(seen[0].url) == "http://192.168.1.15:8080/v1/models"
    assert "lan-key-0013" not in response.text


def test_provider_models_failure_fragment_is_sanitized(authenticated_client, provider_transport, caplog):
    """A hostile 500 body that echoes the key renders only the category message."""
    import httpx
    key = "AIza-echo-0014"
    provider_transport(lambda request: httpx.Response(500, json={"error": key}))
    caplog.set_level("DEBUG")
    response = authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini", "api_key": key})
    assert response.status_code == 502
    assert key not in response.text and key not in caplog.text
    assert "Provider is unavailable." in response.text


# --- Phase 18 plan 03: cached discovery, validation, Ollama requirements, save warnings ---

@pytest.fixture(autouse=True)
def reset_catalog():
    """Catalog is a process singleton; isolate cache state between tests."""
    from app.ai.model_catalog import reset_model_catalog
    reset_model_catalog()
    yield
    reset_model_catalog()


def _counting_gemini(requests, names, fail_after=None):
    """Gemini handler serving `names`; optionally fails once `fail_after` requests were seen."""
    import httpx

    def handler(request):
        requests.append(request)
        if fail_after is not None and len(requests) > fail_after:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json={"models": [
            {"name": f"models/{name}", "supportedGenerationMethods": ["generateContent"]} for name in names]})
    return handler


def _save_gemini_key(client, key="AIza-plan03-secret"):
    assert client.post("/api/settings/ai/credentials", data={"provider_gemini_key": key}).status_code == 200


def test_gemini_test_flags_model_missing_from_live_list_without_changing_settings(authenticated_client, provider_transport):
    """The Gemini 404 incident: connection passes, but the configured model is not listed."""
    _save_gemini_key(authenticated_client)
    provider_transport(_counting_gemini([], ["gemini-3-pro", "gemini-2.5-pro"]))
    before = authenticated_client.get("/api/settings").json()
    response = authenticated_client.post("/api/settings/test-provider", data={"provider": "gemini", "model": "gemini-2.5-flash"})
    assert response.status_code == 200
    assert "Reachable; credentials unverified" in response.text
    assert "Model not in provider list: gemini-2.5-flash" in response.text
    assert 'id="model-warning-gemini"' in response.text and response.text.count('id="provider-models-gemini"') == 1
    assert 'value="gemini-3-pro"' in response.text
    assert authenticated_client.get("/api/settings").json() == before


def test_gemini_test_reports_listed_model_and_unchecked_on_listing_failure(authenticated_client, provider_transport):
    _save_gemini_key(authenticated_client)
    provider_transport(_counting_gemini([], ["gemini-2.5-flash"]))
    listed = authenticated_client.post("/api/settings/test-provider", data={"provider": "gemini", "model": "gemini-2.5-flash"})
    assert "Model listed (not a guarantee it can generate)" in listed.text
    from app.ai.model_catalog import reset_model_catalog
    reset_model_catalog()
    # Health (first request) succeeds, the listing request then fails: result unchanged, model unchecked.
    provider_transport(_counting_gemini([], ["gemini-2.5-flash"], fail_after=1))
    unchecked = authenticated_client.post("/api/settings/test-provider", data={"provider": "gemini", "model": "gemini-2.5-flash"})
    assert unchecked.status_code == 200 and "Reachable; credentials unverified" in unchecked.text
    assert "Model not checked" in unchecked.text and "not in provider list" not in unchecked.text


def test_provider_models_refresh_cooldown_and_cache(authenticated_client, provider_transport):
    """Cache serves repeats; a second manual refresh inside the cooldown makes no provider call."""
    _save_gemini_key(authenticated_client)
    requests = []
    provider_transport(_counting_gemini(requests, ["gemini-2.5-flash"]))
    first = authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini", "refresh": "1"})
    assert first.status_code == 200 and len(requests) == 1
    second = authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini", "refresh": "1"})
    assert second.status_code == 429 and "Wait a few seconds before refreshing again" in second.text
    cached = authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini"})
    assert cached.status_code == 200 and len(requests) == 1


def _ollama_health(monkeypatch, names, seen=None):
    async def health(client):
        if seen is not None:
            seen.append(client.base_url)
        return {"healthy": True, "available_models": list(names)}
    monkeypatch.setattr("app.ai.client.OllamaAIClient.check_health_details", health)


def _ollama_tags(provider_transport, names):
    import httpx
    provider_transport(lambda request: httpx.Response(200, json={"models": [{"name": n, "details": {"family": "llama"}} for n in names]}))


def test_ollama_test_reports_missing_chat_and_embedding_models_with_pull_hints(authenticated_client, provider_transport, monkeypatch):
    """LAN host lacks the task chat model and nomic-embed-text: display-only pull hints for each."""
    host = "http://192.168.1.15:11434"
    saved = authenticated_client.post("/api/settings/ai/credentials", data={
        "ollama_base_url": host, "task_scoring_provider": "ollama", "task_scoring_model": "qwen2.5:7b"})
    assert saved.status_code == 200
    seen = []
    _ollama_health(monkeypatch, ["llama3.1:8b"], seen)
    _ollama_tags(provider_transport, ["llama3.1:8b"])
    response = authenticated_client.post("/api/settings/test-provider", data={"provider": "ollama", "model": "llama3.1:8b"})
    assert response.status_code == 200 and seen == [host]
    assert "<code>ollama pull qwen2.5:7b</code>" in response.text
    assert "<code>ollama pull nomic-embed-text</code>" in response.text
    assert "<code>ollama pull llama3.1:8b</code>" not in response.text
    assert response.text.count('id="provider-models-ollama"') == 1 and response.text.count('id="ollama-requirements-hint"') == 1
    assert "<a " not in response.text


def test_ollama_test_all_present_tag_insensitive(authenticated_client, provider_transport, monkeypatch):
    _ollama_health(monkeypatch, ["llama3.1:8b", "nomic-embed-text:latest"])
    _ollama_tags(provider_transport, ["llama3.1:8b"])
    response = authenticated_client.post("/api/settings/test-provider", data={"provider": "ollama", "model": "llama3.1:8b"})
    assert "ollama pull" not in response.text and "All required Ollama models are present." in response.text


def test_test_embeddings_adds_pull_hint_only_for_reachable_host_missing_model(authenticated_client, monkeypatch):
    host = "http://192.168.1.15:11434"
    authenticated_client.post("/api/settings/ai/credentials", data={"ollama_base_url": host})
    seen = []
    _ollama_health(monkeypatch, ["llama3.1:8b"], seen)
    missing = authenticated_client.post("/api/settings/test-embeddings")
    assert seen == [host] and ">Unavailable</span>" in missing.text
    assert "ollama pull nomic-embed-text" in missing.text and 'id="embedding-hint"' in missing.text
    _ollama_health(monkeypatch, ["nomic-embed-text:latest"])
    present = authenticated_client.post("/api/settings/test-embeddings")
    assert ">Connected</span>" in present.text and "ollama pull" not in present.text

    async def unreachable(client):
        return {"healthy": False, "category": "unavailable"}
    monkeypatch.setattr("app.ai.client.OllamaAIClient.check_health_details", unreachable)
    down = authenticated_client.post("/api/settings/test-embeddings")
    assert ">Unavailable</span>" in down.text and "ollama pull" not in down.text


def test_pull_hint_rejects_hostile_names_and_escapes():
    from app.api.settings import _pull_hint, ollama_requirements
    assert _pull_hint("x; rm -rf /") == "" and _pull_hint("<script>") == "" and _pull_hint("a b") == ""
    assert _pull_hint("qwen2.5:7b") == "Run on the Ollama host: <code>ollama pull qwen2.5:7b</code>"
    assert ollama_requirements(["a:latest", "b:1"], ["a", "b", "c"]) == ["b", "c"]


def test_save_warns_from_cached_list_without_blocking_or_rewriting(authenticated_client, provider_transport):
    """A cached Gemini list lacking the saved task model yields a warning; value persists exactly."""
    _save_gemini_key(authenticated_client)
    requests = []
    provider_transport(_counting_gemini(requests, ["gemini-2.5-flash"]))
    assert authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini"}).status_code == 200
    seen_before = len(requests)
    for headers in ({}, {"HX-Target": "ai-routing-controls", "HX-Request": "true"}):
        response = authenticated_client.post("/api/settings/ai", data={
            "task_scoring_provider": "gemini", "task_scoring_model": "gemini-9-ultra"}, headers=headers)
        assert response.status_code == 200
        assert "Not in provider list: gemini-9-ultra" in response.text
        assert response.text.count('id="model-save-warning"') == 1 and 'id="provider-models-ollama"' not in response.text
        assert authenticated_client.get("/api/settings").json()["task_scoring_model"] == "gemini-9-ultra"
    provider_save = authenticated_client.post("/api/settings/ai", data={"gemini_model": "gemini-9-ultra"},
                                              headers={"HX-Target": "provider-save-gemini"})
    assert "Not in provider list" in provider_save.text and provider_save.text.count('id="model-save-warning"') == 1
    ok = authenticated_client.post("/api/settings/ai", data={"task_scoring_provider": "gemini", "task_scoring_model": "gemini-2.5-flash"})
    assert "Not in provider list" not in ok.text and ok.text.count('id="model-save-warning"') == 1
    assert len(requests) == seen_before  # saves never touch the network


def test_save_without_cache_makes_no_request_and_no_warning(authenticated_client, provider_transport):
    _save_gemini_key(authenticated_client)
    requests = []
    provider_transport(_counting_gemini(requests, ["gemini-2.5-flash"]))
    response = authenticated_client.post("/api/settings/ai", data={"task_scoring_provider": "gemini", "task_scoring_model": "anything"})
    assert response.status_code == 200 and "Not in provider list" not in response.text and requests == []


def test_saving_a_new_key_invalidates_cached_listing(authenticated_client, provider_transport):
    _save_gemini_key(authenticated_client)
    requests = []
    provider_transport(_counting_gemini(requests, ["gemini-2.5-flash"]))
    authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini"})
    authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini"})
    assert len(requests) == 1
    _save_gemini_key(authenticated_client, "AIza-rotated-key")
    authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini"})
    assert len(requests) == 2


def test_cache_is_not_shared_between_owners(authenticated_client, provider_transport):
    """A second account with its own key cannot be served the first owner's cached list."""
    from fastapi.testclient import TestClient
    from app.main import app
    _save_gemini_key(authenticated_client)
    requests = []
    provider_transport(_counting_gemini(requests, ["gemini-2.5-flash"]))
    authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini"})
    with TestClient(app) as other:
        assert other.post("/api/auth/register", json={"email": "other-owner@example.com", "password": "OtherPassword123", "full_name": "Other"}).status_code == 200
        denied = other.post("/api/settings/provider-models", data={"provider": "gemini"})
        assert denied.status_code == 422
        other.post("/api/settings/ai/credentials", data={"provider_gemini_key": "AIza-other-owner"})
        other.post("/api/settings/provider-models", data={"provider": "gemini"})
    assert len(requests) == 2


# --- Phase 18 plan 04: Settings template slots and bindings ---

def _settings_document(client):
    from bs4 import BeautifulSoup
    response = client.get("/web/views/settings")
    assert response.status_code == 200
    return response.text, BeautifulSoup(response.text, "html.parser")


def test_settings_provider_cards_have_refresh_button_and_secret_free_markup(authenticated_client):
    """Every card posts Refresh models (key in body, never a GET) and renders no key anywhere."""
    authenticated_client.post("/api/settings/ai/credentials", data={"provider_gemini_key": "AIza-render-sentinel-0001"})
    text, document = _settings_document(authenticated_client)
    providers = ("ollama", "openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom")
    for provider in providers:
        form = document.select_one(f"#provider-form-{provider}")
        button = next(b for b in form.select("button") if b.get_text(strip=True) == "Refresh models")
        assert button["hx-post"] == "/api/settings/provider-models"
        assert button["hx-target"] == f"#provider-status-{provider}" and not button.has_attr("hx-get")
        assert form.select_one(f"#provider-model-{provider}")["list"] == f"provider-models-{provider}"
        assert document.select_one(f"#model-warning-{provider}")["aria-live"] == "polite"
        assert form.select_one(f"#provider-model-help-{provider}")
    assert "AIza-render-sentinel-0001" not in text
    assert all(not field.get("value") for field in document.select('input[type="password"]'))
    assert "hx-trigger=\"load\"" not in str(document.select_one("#ai-providers"))


def test_settings_has_server_fragment_slots_and_non_blocking_save(authenticated_client):
    """OOB targets for Plan 03 fragments exist, and warnings never disable Save."""
    text, document = _settings_document(authenticated_client)
    for slot in ("ollama-requirements-hint", "embedding-hint", "model-save-warning", "model-warning-task-scoring"):
        assert len(document.select(f"#{slot}")) == 1, slot
    assert document.select_one("#model-save-warning")["aria-live"] == "polite"
    assert document.select_one("#model-warning-task-scoring")["role"] == "status"
    assert "innerHTML" not in text.split("function jobotModelWarn")[1].split("function toggleAIFields")[0]
    assert "textContent" in text
    assert not [b for b in document.select("#ai-providers button") if b.has_attr("disabled")]


def test_task_model_inputs_bind_to_selected_provider_datalist(authenticated_client):
    """Task inputs follow their provider select; presets keep the binding."""
    authenticated_client.post("/api/settings/ai", data={"task_scoring_provider": "ollama", "task_scoring_model": "llama3.1:8b"})
    _, document = _settings_document(authenticated_client)
    assert document.select_one("#task-scoring-model")["list"] == "provider-models-ollama"
    assert "provider-models-'+this.value" in document.select_one("#task-scoring-provider")["onchange"]
    preset = authenticated_client.post("/api/settings/ai/preset", data={"preset": "local"},
                                       headers={"HX-Request": "true", "HX-Target": "ai-routing-controls"})
    from bs4 import BeautifulSoup
    fragment = BeautifulSoup(preset.text, "html.parser")
    assert all(fragment.select_one(f"#task-{stage}-model")["list"] == "provider-models-ollama" for stage in ("scraping", "scoring", "applying"))


# --- Phase 18 plan 05: end-to-end incident regressions ---

def test_incident_gemini_listed_models_exclude_unsupported_and_chosen_model_is_flagged(authenticated_client, provider_transport):
    """Gemini incident: chosen model absent from the generateContent list is flagged, not rewritten."""
    import httpx
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"models": [
            {"name": "models/gemini-2.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["embedContent"]},
            {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
        ]})

    _save_gemini_key(authenticated_client)
    authenticated_client.post("/api/settings/ai", data={"gemini_model": "gemini-2.5-flash"})
    provider_transport(handler)
    listing = authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini", "model": "gemini-2.5-flash"})
    assert 'value="gemini-2.5-flash-lite"' in listing.text and 'value="gemini-2.5-flash"' not in listing.text
    assert "text-embedding" not in listing.text and "Model not in provider list" in listing.text
    count = len(requests)
    tested = authenticated_client.post("/api/settings/test-provider", data={"provider": "gemini", "model": "gemini-2.5-flash"})
    assert "Model not in provider list: gemini-2.5-flash" in tested.text
    assert len(requests) == count + 1  # one health GET; the listing came from cache
    _, document = _settings_document(authenticated_client)
    assert document.select_one("#provider-model-gemini")["value"] == "gemini-2.5-flash"


def test_incident_ollama_missing_models_become_present_after_pull(authenticated_client, provider_transport, monkeypatch):
    """Ollama incident: hints for both missing models vanish once the host lists them."""
    host = "http://192.168.1.15:11434"
    authenticated_client.post("/api/settings/ai/credentials", data={"ollama_base_url": host, "ollama_model": "qwen2.5:7b"})
    _ollama_health(monkeypatch, ["unrelated:1b"])
    _ollama_tags(provider_transport, ["unrelated:1b"])
    missing = authenticated_client.post("/api/settings/test-provider", data={"provider": "ollama", "model": "qwen2.5:7b"})
    assert "ollama pull qwen2.5:7b" in missing.text and "ollama pull nomic-embed-text" in missing.text
    embedding = authenticated_client.post("/api/settings/test-embeddings")
    assert "ollama pull nomic-embed-text" in embedding.text
    _ollama_health(monkeypatch, ["unrelated:1b", "qwen2.5:7b", "nomic-embed-text:latest"])
    _ollama_tags(provider_transport, ["unrelated:1b", "qwen2.5:7b", "nomic-embed-text:latest"])
    present = authenticated_client.post("/api/settings/test-provider", data={"provider": "ollama", "model": "qwen2.5:7b"})
    assert "ollama pull" not in present.text and "All required Ollama models are present." in present.text
    assert "ollama pull" not in authenticated_client.post("/api/settings/test-embeddings").text
