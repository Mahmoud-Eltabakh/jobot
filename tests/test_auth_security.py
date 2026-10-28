"""Integration and unit test suite for user authentication, data isolation, and encryption."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.auth.security import (
    create_user_session,
    hash_password,
    revoke_session,
    validate_session_token,
    verify_password,
)
from app.db.database import engine, get_user_setting
from app.db.models import Job, User
from app.db.ownership import encrypt_profile, get_user_profile
from app.main import app
from app.security.encryption import EncryptionError, decrypt_text, encrypt_text


@pytest.fixture(name="test_session")
def session_fixture():
    """Create in-memory SQLite database session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_password_hashing():
    """Test password hashing and verification with scrypt."""
    password = "MySecurePassword123!"
    hashed = hash_password(password)
    
    assert hashed != password
    assert hashed.startswith("scrypt:")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_session_lifecycle(test_session: Session):
    """Test session token creation, validation, and revocation."""
    user = User(
        email="test@example.com",
        password_hash=hash_password("password123"),
        full_name="Test User",
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    session_obj = create_user_session(test_session, user.id)
    assert session_obj.session_token is not None

    validated_user = validate_session_token(test_session, session_obj.session_token)
    assert validated_user is not None
    assert validated_user.id == user.id

    revoke_session(test_session, session_obj.session_token)
    invalidated_user = validate_session_token(test_session, session_obj.session_token)
    assert invalidated_user is None


def test_encryption_decryption_roundtrip():
    """Test authenticated encryption and decryption of sensitive user data."""
    sensitive_cv = "Confidential resume data for Jane Doe, SSN: 123-45-6789"
    encrypted = encrypt_text(sensitive_cv, user_id=42)
    
    assert encrypted != sensitive_cv
    assert encrypted.startswith("enc:v2:")
    
    decrypted = decrypt_text(encrypted, user_id=42)
    assert decrypted == sensitive_cv

    with pytest.raises(EncryptionError):
        decrypt_text(encrypted, user_id=43)

    # Unencrypted string fallback
    plain = "Regular unencrypted text"
    assert decrypt_text(plain) == plain


def test_auth_api_endpoints():
    """Test API endpoints for register, login, logout, and me."""
    client = TestClient(app)

    # 1. Register
    reg_payload = {
        "email": "api_user@example.com",
        "password": "Password123",
        "full_name": "API User",
    }
    resp = client.post("/api/auth/register", json=reg_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "api_user@example.com"
    assert "jobot_session" in resp.cookies

    # 2. Get Me
    me_resp = client.get("/api/auth/me", cookies=resp.cookies)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "api_user@example.com"

    # 3. Logout
    logout_resp = client.post("/api/auth/logout", cookies=resp.cookies)
    assert logout_resp.status_code == 200

    # 4. Login
    login_payload = {
        "email": "api_user@example.com",
        "password": "Password123",
    }
    login_resp = client.post("/api/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    assert "jobot_session" in login_resp.cookies


def test_user_data_isolation(test_session: Session):
    """Test data isolation between two distinct user accounts."""
    user1 = User(email="user1@example.com", password_hash=hash_password("pass1"), full_name="User One")
    user2 = User(email="user2@example.com", password_hash=hash_password("pass2"), full_name="User Two")
    test_session.add(user1)
    test_session.add(user2)
    test_session.commit()
    test_session.refresh(user1)
    test_session.refresh(user2)

    job1 = Job(user_id=user1.id, source="linkedin", title="Backend Engineer", company="Corp A", location="Remote", url="http://example.com/1", dedup_hash="hash1")
    job2 = Job(user_id=user2.id, source="stepstone", title="Frontend Engineer", company="Corp B", location="Berlin", url="http://example.com/2", dedup_hash="hash2")
    test_session.add(job1)
    test_session.add(job2)
    test_session.commit()

    user1_jobs = test_session.exec(select(Job).where(Job.user_id == user1.id)).all()
    user2_jobs = test_session.exec(select(Job).where(Job.user_id == user2.id)).all()

    assert len(user1_jobs) == 1
    assert user1_jobs[0].title == "Backend Engineer"

    assert len(user2_jobs) == 1
    assert user2_jobs[0].title == "Frontend Engineer"


def test_saved_credentials_are_not_reflected_into_html():
    """Keep account secrets encrypted at rest and absent from rendered forms."""
    api_key = "sk-private-phase15-key"
    linkedin_cookie = "private-linkedin-session-cookie"

    with TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "email": "secrets@example.com",
                "password": "SecurePassword123",
                "full_name": "Secret Owner",
            },
        )
        assert register_response.status_code == 200
        user_id = register_response.json()["id"]

        save_response = client.post(
            "/api/settings/ai",
            data={
                "ai_provider": "openai",
                "openai_model": "gpt-4o-mini",
                "openai_api_key": api_key,
            },
        )
        assert save_response.status_code == 200

        with Session(engine) as session:
            profile = get_user_profile(session, user_id, decrypt=True)
            assert profile is not None
            profile.linkedin_session_cookie = linkedin_cookie
            encrypt_profile(profile, user_id)
            session.add(profile)
            session.commit()

        settings_response = client.get("/web/views/settings")
        profile_response = client.get("/web/views/profile")
        assert settings_response.status_code == 200
        assert profile_response.status_code == 200
        assert api_key not in settings_response.text
        assert linkedin_cookie not in profile_response.text

        blank_save_response = client.post(
            "/api/settings/ai",
            data={
                "ai_provider": "openai",
                "openai_model": "gpt-4o-mini",
                "openai_api_key": "",
            },
        )
        assert blank_save_response.status_code == 200

        with Session(engine) as session:
            assert get_user_setting(session, user_id, "openai_api_key") == api_key


@pytest.fixture
def provider_accounts(authenticated_client, authenticated_user):
    """Independent cookie jars exercise the real owner authentication boundary."""
    with TestClient(app) as other:
        response = other.post("/api/auth/register", json={
            "email": "provider-other@example.com", "password": "OtherPassword123", "full_name": "Other",
        })
        assert response.status_code == 200
        yield authenticated_client, authenticated_user["id"], other, response.json()["id"]


@pytest.mark.parametrize("provider", ["ollama", "openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom"])
def test_individual_provider_probe_is_owner_only_and_not_persisted(provider_accounts, monkeypatch, provider):
    """Submitted credentials are transient and cannot inherit installation secrets."""
    from app.ai import client as ai
    from app.db.database import set_app_setting, set_user_setting
    from app.db.models import UserSetting

    owner_client, owner, other_client, other = provider_accounts
    with Session(engine) as session:
        set_app_setting("openai_api_key", "fake-global-key")
        set_user_setting(session, owner, f"provider_{provider}_key", "fake-owner-key", sensitive=True)
        set_user_setting(session, owner, "provider_custom_url", "http://owner.local/v1")
        set_user_setting(session, owner, "openai_model", "owner-model")
        before = [(record.id, record.value_json) for record in session.exec(select(UserSetting)).all()]
    observed = []

    async def health(client):
        observed.append(client)
        return {"healthy": True, "credential_validation": "unverified", "available_models": ['<img src=x onerror=alert(1)>']}

    for adapter in (ai.OllamaAIClient, ai.OpenAICompatibleClient, ai.AnthropicClient, ai.GeminiClient):
        monkeypatch.setattr(adapter, "check_health_details", health)
    data = {"provider": provider, "model": "owner-model"}
    response = owner_client.post("/api/settings/test-provider", data=data)
    assert response.status_code == 200, response.text
    assert f'provider-status-{provider}' in response.text
    assert "unverified" in response.text
    assert "fake-owner-key" not in response.text
    assert "<img" not in response.text
    assert observed[-1].provider == provider
    if provider == "ollama":
        assert observed[-1]._headers == {"Authorization": "Bearer fake-owner-key"}
    else:
        assert observed[-1].api_key == "fake-owner-key"
    if provider != "ollama":
        rejected = other_client.post("/api/settings/test-provider", data=data)
        assert rejected.status_code == 422
        assert len(observed) == 1
    response = other_client.post("/api/settings/test-provider", data={**data, "api_key": "fake-transient", "base_url": "http://other.local/v1"} if provider == "custom" else {**data, "api_key": "fake-transient"})
    assert response.status_code == 200
    assert observed[-1].api_key == "fake-transient" if provider != "ollama" else observed[-1]._headers == {"Authorization": "Bearer fake-transient"}
    with Session(engine) as session:
        assert [(record.id, record.value_json) for record in session.exec(select(UserSetting)).all()] == before


@pytest.mark.parametrize("data", [
    {"provider": "unknown"}, {"provider": "gemini", "model": "bad?key=secret"},
    {"provider": "openai", "base_url": "https://evil.local/v1"},
    *[{"provider": "custom", "model": "custom-model", "base_url": url} for url in (
        "file:///tmp/file", "http://user:pass@host/v1", "http://host/v1?key=secret", "http://host/v1#secret", "http:///missing", "http://host:invalid")],
])
def test_provider_probe_rejects_invalid_configuration(authenticated_client, monkeypatch, data):
    from app.ai.client import BaseAIClient

    async def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration reached the network")

    monkeypatch.setattr(BaseAIClient, "check_health_details", forbidden)
    response = authenticated_client.post("/api/settings/test-provider", data={"api_key": "fake-secret", **data})
    assert response.status_code == 422
    assert "fake-secret" not in response.text
    assert "evil.local" not in response.text


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("failure", ["details", "exception", "timeout"])
def test_probe_errors_never_render_remote_text(authenticated_client, monkeypatch, legacy, failure):
    from app.ai.client import OllamaAIClient

    hostile = '<script>alert("fake-secret")</script>'

    async def health(client):
        if failure == "exception":
            raise RuntimeError(hostile)
        if failure == "timeout":
            raise TimeoutError(hostile)
        return {"healthy": False, "category": "authentication", "message": hostile, "error": hostile}

    monkeypatch.setattr(OllamaAIClient, "check_health_details", health)
    route = "test-ai" if legacy else "test-provider"
    response = authenticated_client.post(f"/api/settings/{route}", data={"ai_provider" if legacy else "provider": "ollama"})
    assert response.status_code == 503
    assert "fake-secret" not in response.text
    assert "<script" not in response.text
    assert ("authentication" if failure == "details" else "timeout" if failure == "timeout" else "unavailable") in response.text


def test_legacy_probes_models_and_has_key_are_owner_scoped(provider_accounts, monkeypatch):
    from app.ai.client import OllamaAIClient
    from app.core.config import get_settings
    from app.db.database import set_app_setting, set_user_setting

    owner_client, owner, other_client, other = provider_accounts
    monkeypatch.setattr(get_settings(), "openai_api_key", "fake-env")
    with Session(engine) as session:
        set_app_setting("ollama_base_url", "http://global.local:11434")
        for user_id, host, model in ((owner, "http://owner.local:11434", "owner-model"), (other, "http://other.local:11434", "other-model")):
            set_user_setting(session, user_id, "ollama_base_url", host)
            set_user_setting(session, user_id, "ollama_model", model)
        set_user_setting(session, owner, "provider_ollama_key", "fake-owner-token")
        set_user_setting(session, owner, "provider_openai_key", "fake-openai")
    observed = []

    async def health(client):
        observed.append((client.base_url, client.model, client._headers))
        return {"healthy": True, "available_models": [client.model, '<img src=x onerror=alert(1)>']}

    monkeypatch.setattr(OllamaAIClient, "check_health_details", health)
    for client, host, model, headers in ((owner_client, "http://owner.local:11434", "owner-model", {"Authorization": "Bearer fake-owner-token"}), (other_client, "http://other.local:11434", "other-model", {})):
        assert client.post("/api/settings/test-ai", data={"ai_provider": "ollama"}).status_code == 200
        response = client.get("/api/settings/ollama/models")
        assert response.status_code == 200
        assert "<img" not in response.text
        assert observed[-1] == (host, model, headers)
        config = client.get("/api/settings").json()
        assert config["ollama_base_url"] == host
        assert config["has_openai_key"] == (client is owner_client)
        assert "fake-" not in str(config)
    rejected = owner_client.get("/api/settings/ollama/models", params={"ollama_base_url": "http://evil.local"})
    assert rejected.status_code == 422
    assert observed[-1][0] != "http://evil.local"


@pytest.mark.parametrize("route", ["test-provider", "test-ai", "ai/preset", "ai/credentials"])
def test_provider_routes_require_authentication(client, route):
    assert client.post(f"/api/settings/{route}", data={"provider": "ollama", "preset": "local"}).status_code == 401


def test_settings_cv_and_rescore_use_owner_stage_clients(authenticated_client, authenticated_user, monkeypatch):
    """CV generation and local vectors have independent, owner-bound clients."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.api import settings as routes
    from app.ai.evaluator import JobEvaluator

    generation, embedding = object(), object()
    calls = []

    def factory(session, user_id, *, task_type="scoring"):
        calls.append((user_id, task_type))
        return generation

    def vectors(session, user_id):
        calls.append((user_id, "embeddings"))
        return embedding

    monkeypatch.setattr(routes, "get_ai_client", factory)
    monkeypatch.setattr(routes, "get_embedding_client", vectors)
    monkeypatch.setattr(routes.CVParser, "extract_text_from_bytes", lambda *args: "CV text")
    monkeypatch.setattr(routes, "extract_profile_from_text", AsyncMock(return_value="profile"))
    monkeypatch.setattr(routes, "save_profile_to_db", lambda *args, **kwargs: SimpleNamespace(full_name="Owner"))
    monkeypatch.setattr(routes, "get_vector_store", lambda: "store")
    embed = AsyncMock()
    monkeypatch.setattr(routes.ProfileEmbedder, "embed_and_store_profile", embed)
    response = authenticated_client.post("/api/settings/upload-cv", files={"file": ("cv.txt", b"CV text", "text/plain")})
    assert response.status_code == 200
    assert calls == [(authenticated_user["id"], "scraping"), (authenticated_user["id"], "embeddings")]
    assert embed.await_args.args == ("profile", "store")
    assert embed.await_args.kwargs["embedding_client"] is embedding
    assert embed.await_args.kwargs["user_id"] == authenticated_user["id"]
    assert isinstance(embed.await_args.kwargs["session"], Session)
    rescore = AsyncMock(return_value=2)
    monkeypatch.setattr(JobEvaluator, "rescore_all_jobs", rescore)
    assert authenticated_client.post("/api/settings/rescore-all").status_code == 200
    assert calls[-1] == (authenticated_user["id"], "scoring")
    assert rescore.await_args.kwargs["user_id"] == authenticated_user["id"]


def _owner_settings_snapshot(user_id):
    """Compare persisted ciphertext as well as fields, not just decrypted keys."""
    from app.db.models import UserSetting

    with Session(engine) as session:
        return {record.key: (record.value_json, record.is_sensitive) for record in
                session.exec(select(UserSetting).where(UserSetting.user_id == user_id)).all()}


def test_settings_html_isolates_owner_metadata(provider_accounts):
    """The rendered vault and task controls expose only the current account's metadata."""
    from app.db.database import set_user_settings
    owner_client, owner, other_client, other = provider_accounts
    with Session(engine) as session:
        set_user_settings(session, owner, {"provider_openai_key": "fake-owner-secret", "ollama_base_url": "http://owner-only.local:11434", "task_scraping_model": "owner-only-model"})
        set_user_settings(session, other, {"ollama_base_url": "http://other-only.local:11434", "task_scraping_model": "other-only-model"})
    owner_html = owner_client.get("/web/views/settings").text
    other_html = other_client.get("/web/views/settings").text
    assert "owner-only.local" in owner_html
    assert "owner-only-model" in owner_html
    assert "owner-only" not in other_html
    assert "other-only" not in owner_html
    assert "fake-owner-secret" not in owner_html + other_html
    assert 'id="provider-secret-state-openai" data-secret-state class="block text-xs text-slate-400">Not configured' in other_html


def test_generation_and_retry_reject_foreign_owner_before_resolution(provider_accounts, monkeypatch):
    import json
    from app.db.models import ScrapeTask
    owner_client, owner, other_client, other = provider_accounts
    with Session(engine) as session:
        job = Job(user_id=owner, title="Owned Engineer", company="Example", location="Remote", source="test", url="https://example.test/owned", dedup_hash="foreign-recovery")
        session.add(job)
        session.commit()
        session.refresh(job)
        task = ScrapeTask(user_id=owner, task_type="evaluate_job", payload_json=json.dumps({"job_id": job.id}), status="failed")
        session.add(task)
        session.commit()
        session.refresh(task)
        job_id, task_id = job.id, task.id
    def forbidden(*args, **kwargs):
        raise AssertionError("Foreign request reached client resolution")
    monkeypatch.setattr("app.web.routes.get_ai_client", forbidden)
    for path in (f"/web/job/{job_id}/cover-letter/generate", f"/web/job/{job_id}/tailor-resume/generate", f"/web/queue/tasks/{task_id}/retry"):
        assert other_client.post(path).status_code == 404
    with Session(engine) as session:
        assert session.get(ScrapeTask, task_id).status == "failed"


@pytest.mark.parametrize("preset", ["local", "hybrid", "cloud"])
def test_presets_exact_assignments_preserve_credentials(provider_accounts, preset):
    from app.db.database import set_user_settings

    client, owner, other_client, other = provider_accounts
    with Session(engine) as session:
        set_user_settings(session, owner, {"provider_openai_key": "fake-owner", "provider_ollama_key": "fake-local",
                                          "ollama_model": "owner-local", "provider_custom_url": "http://owner.local/v1"})
        set_user_settings(session, other, {"task_scoring_model": "other-choice"})
    before = _owner_settings_snapshot(owner)
    other_before = _owner_settings_snapshot(other)
    response = client.post("/api/settings/ai/preset", data={"preset": preset})
    assert response.status_code == 200, response.text
    assert "fake-owner" not in response.text
    after = _owner_settings_snapshot(owner)
    assert {key: value for key, value in after.items() if not key.startswith("task_")} == before
    assert _owner_settings_snapshot(other) == other_before
    with Session(engine) as session:
        for stage in ("scraping", "scoring", "applying"):
            expected = "openai" if preset == "cloud" or preset == "hybrid" and stage == "applying" else "ollama"
            assert get_user_setting(session, owner, f"task_{stage}_provider") == expected
            assert get_user_setting(session, owner, f"task_{stage}_model") == ("gpt-4o-mini" if expected == "openai" else "owner-local")
    payload = client.get("/api/settings").json()
    assert payload["task_applying_provider"] == ("ollama" if preset == "local" else "openai")
    assert payload["task_scraping_model"] == ("gpt-4o-mini" if preset == "cloud" else "owner-local")


@pytest.mark.parametrize("preset", ["hybrid", "cloud", "invalid"])
def test_preset_rejection_changes_nothing_even_with_foreign_global_key(provider_accounts, monkeypatch, preset):
    from app.core.config import get_settings
    from app.db.database import set_app_setting, set_user_settings

    client, owner, other_client, other = provider_accounts
    monkeypatch.setattr(get_settings(), "openai_api_key", "fake-env")
    with Session(engine) as session:
        set_app_setting("openai_api_key", "fake-global")
        set_user_settings(session, other, {"provider_openai_key": "fake-other"})
        set_user_settings(session, owner, {"ai_provider": "custom", "openai_api_key": "fake-custom",
                                          "task_scraping_provider": "ollama", "task_scraping_model": "old"}, sensitive_keys=("openai_api_key",))
    before = _owner_settings_snapshot(owner)
    response = client.post("/api/settings/ai/preset", data={"preset": preset})
    assert response.status_code == 422
    assert _owner_settings_snapshot(owner) == before
    assert "fake-" not in response.text


@pytest.mark.parametrize("route", ["ai", "ai/credentials"])
def test_all_provider_credentials_save_encrypted_and_blank_preserves(provider_accounts, route):
    client, owner, other_client, other = provider_accounts
    values = {f"provider_{provider}_key": f"fake-{provider}" for provider in
              ("ollama", "openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom")}
    response = client.post(f"/api/settings/{route}", data={**values, "provider_custom_url": "http://owner.local/v1"})
    assert response.status_code == 200, response.text
    assert "fake-" not in response.text
    before = _owner_settings_snapshot(owner)
    assert all(before[key][1] and value not in before[key][0] and before[key][0].startswith("enc:v2:") for key, value in values.items())
    response = client.post(f"/api/settings/{route}", data={key: " " for key in values})
    assert response.status_code == 200
    assert _owner_settings_snapshot(owner) == before
    assert _owner_settings_snapshot(other) == {}
    payload = client.get("/api/settings").json()
    assert all(payload["providers"][provider]["has_key"] for provider in payload["providers"])
    assert "fake-" not in str(payload)


@pytest.mark.parametrize("invalid", [
    {"task_scoring_provider": "unknown"}, {"task_unknown_model": "x"},
    {"provider_unknown_key": "fake-secret"}, {"provider_custom_url": "https://user:pass@host"},
    {"task_scoring_model": "bad?secret=key"}, {"ai_provider": "unknown"},
    {"openai_base_url": "https://evil.local/v1"},
])
def test_ai_save_validates_entire_form_before_writes(authenticated_client, authenticated_user, invalid):
    from app.db.database import set_user_settings

    owner = authenticated_user["id"]
    with Session(engine) as session:
        set_user_settings(session, owner, {"ai_provider": "openai", "openai_api_key": "fake-legacy"}, sensitive_keys=("openai_api_key",))
    before = _owner_settings_snapshot(owner)
    response = authenticated_client.post("/api/settings/ai", data={"ai_provider": "openai", "provider_groq_key": "fake-new", "task_scraping_provider": "openai", **invalid})
    assert response.status_code == 422, response.text
    assert _owner_settings_snapshot(owner) == before
    assert "fake-" not in response.text


def test_routing_save_and_legacy_migration_are_atomic(authenticated_client, authenticated_user, monkeypatch):
    from app.api import settings as routes
    from app.db.database import set_user_settings

    owner = authenticated_user["id"]
    with Session(engine) as session:
        set_user_settings(session, owner, {"ai_provider": "custom", "openai_api_key": "fake-legacy", "openai_base_url": "http://legacy.local/v1", "openai_model": "legacy-model"}, sensitive_keys=("openai_api_key",))
    data = {"ai_provider": "custom", "provider_groq_key": "fake-groq", "task_scoring_provider": "gemini", "task_scoring_model": "gemini-own"}
    before = _owner_settings_snapshot(owner)

    def failing_session():
        with Session(engine) as session:
            def fail():
                session.flush()
                raise RuntimeError("fake-secret <script>commit failure</script>")
            monkeypatch.setattr(session, "commit", fail)
            yield session

    app.dependency_overrides[routes.get_session] = failing_session
    try:
        response = authenticated_client.post("/api/settings/ai", data=data)
        assert response.status_code == 500
        assert "fake-secret" not in response.text
        assert _owner_settings_snapshot(owner) == before
    finally:
        app.dependency_overrides.pop(routes.get_session, None)
    assert authenticated_client.post("/api/settings/ai", data=data).status_code == 200
    with Session(engine) as session:
        assert get_user_setting(session, owner, "provider_custom_key") == "fake-legacy"
        assert get_user_setting(session, owner, "provider_openai_key") is None
        assert get_user_setting(session, owner, "task_scoring_provider") == "gemini"
        assert get_user_setting(session, owner, "task_scoring_model") == "gemini-own"
        assert get_user_setting(session, owner, "task_applying_provider") == "custom"


@pytest.mark.parametrize("preset", ["local", "hybrid", "cloud"])
def test_preset_commit_failure_rolls_back_all_six_fields(authenticated_client, authenticated_user, monkeypatch, preset):
    from app.api import settings as routes
    from app.db.database import set_user_settings

    owner = authenticated_user["id"]
    with Session(engine) as session:
        set_user_settings(session, owner, {"provider_openai_key": "fake-openai", **{f"task_{stage}_{field}": "ollama" if field == "provider" else "old-model" for stage in ("scraping", "scoring", "applying") for field in ("provider", "model")}})
    before = _owner_settings_snapshot(owner)

    def failing_session():
        with Session(engine) as session:
            def fail():
                session.flush()
                raise RuntimeError("fake-secret commit failure")
            monkeypatch.setattr(session, "commit", fail)
            yield session

    app.dependency_overrides[routes.get_session] = failing_session
    try:
        response = authenticated_client.post("/api/settings/ai/preset", data={"preset": preset})
        assert response.status_code == 500
        assert "fake-secret" not in response.text
        assert _owner_settings_snapshot(owner) == before
    finally:
        app.dependency_overrides.pop(routes.get_session, None)


@pytest.mark.parametrize("provider", ["ollama", "openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom"])
@pytest.mark.parametrize("redirect", [False, True])
def test_provider_probe_transport_headers_get_only_no_redirects(authenticated_client, monkeypatch, provider, redirect, caplog):
    """Exercise real adapter HTTP handling, not just factory/health spies."""
    import httpx
    from importlib import import_module
    from app.ai.client import PROVIDER_DEFAULTS, openai

    observed = []

    def install_transport(http):
        def handle(request):
            observed.append(request)
            if redirect:
                return http.Response(302, headers={"Location": "https://evil.local/steal"}, text="fake-secret <script>remote</script>")
            return http.Response(200, json={"data": [], "models": []})

        transport = http.MockTransport(handle)

        def route_transport(client, url):
            assert client.follow_redirects is False
            return transport

        monkeypatch.setattr(http.AsyncClient, "_transport_for_url", route_transport)

    install_transport(httpx)
    sdk_http_module = next(base.__module__.partition(".")[0] for base in openai.DefaultAsyncHttpxClient.__mro__ if base.__name__ == "AsyncClient")
    install_transport(import_module(sdk_http_module))
    response = authenticated_client.post("/api/settings/test-provider", data={
        "provider": provider, "api_key": "fake-secret", "model": "org/model", "base_url":
        "http://custom.local/v1" if provider == "custom" else PROVIDER_DEFAULTS[provider]["base_url"],
    })
    expected_status = (503 if provider == "ollama" else 502) if redirect else 200
    assert response.status_code == expected_status, response.text
    # Phase 18: a healthy probe is followed by one cached model-listing GET (health fails first on redirect).
    assert len(observed) == (1 if redirect else 2)
    assert all(item.method == "GET" and item.url.host != "evil.local" and "fake-secret" not in str(item.url) for item in observed)
    request = observed[0]
    assert request.method == "GET"
    assert request.url.host != "evil.local"
    assert not request.url.query
    assert request.url.path.endswith("/api/tags" if provider == "ollama" else "/v1beta/models" if provider == "gemini" else "/models")
    header = "x-api-key" if provider == "anthropic" else "x-goog-api-key" if provider == "gemini" else "Authorization"
    assert all(item.headers[header] == ("fake-secret" if provider in ("anthropic", "gemini") else "Bearer fake-secret")
               for item in observed if provider != "ollama" or item.headers.get(header))
    assert "fake-secret" not in response.text + caplog.text
    assert "<script>" not in response.text


def test_provider_probe_enforces_whole_operation_deadline(authenticated_client, monkeypatch):
    from app.api import settings as routes

    budgets = []
    original = routes.asyncio.wait_for

    async def short_clock(awaitable, timeout):
        budgets.append(timeout)
        return await original(awaitable, 0.01)

    async def stalled(client):
        await routes.asyncio.Future()

    monkeypatch.setattr(routes.asyncio, "wait_for", short_clock)
    monkeypatch.setattr(routes.OllamaAIClient, "check_health_details", stalled)
    response = authenticated_client.post("/api/settings/test-provider", data={"provider": "ollama"})
    assert response.status_code == 503
    assert "timeout" in response.text
    assert budgets == [5]


def test_settings_does_not_reflect_unsafe_legacy_endpoint(authenticated_client, authenticated_user):
    from app.db.database import set_user_setting

    with Session(engine) as session:
        set_user_setting(session, authenticated_user["id"], "ai_provider", "custom")
        set_user_setting(session, authenticated_user["id"], "openai_base_url", "http://host/v1?key=fake-secret")
    response = authenticated_client.get("/api/settings")
    assert response.status_code == 200
    assert "fake-secret" not in response.text
    assert response.json()["providers"]["custom"]["base_url"] == ""


def test_unreadable_owner_credential_has_safe_configuration_error(authenticated_client, authenticated_user):
    from app.db.models import UserSetting

    with Session(engine) as session:
        session.add(UserSetting(user_id=authenticated_user["id"], key="provider_openai_key", value_json="enc:v2:local:user-999:fake-secret", is_sensitive=True))
        session.commit()
    response = authenticated_client.post("/api/settings/test-provider", data={"provider": "openai"})
    assert response.status_code == 422
    assert "fake-secret" not in response.text


@pytest.mark.parametrize("provider", ["openai", "custom"])
def test_legacy_cloud_probe_uses_matching_owner_configuration(provider_accounts, monkeypatch, provider):
    from app.ai.client import OpenAICompatibleClient
    from app.core.config import get_settings
    from app.db.database import set_app_setting, set_user_settings

    client, owner, other_client, other = provider_accounts
    monkeypatch.setattr(get_settings(), "openai_api_key", "fake-env")
    with Session(engine) as session:
        set_app_setting("openai_api_key", "fake-global")
        set_app_setting("openai_base_url", "http://global.local/v1")
        set_app_setting("openai_model", "global-model")
        for user_id, model in ((owner, "owner-model"), (other, "other-model")):
            set_user_settings(session, user_id, {"ai_provider": provider, "openai_model": model, "openai_base_url": f"http://owner-{user_id}.local/v1"})
        set_user_settings(session, owner, {"openai_api_key": "fake-legacy-owner"}, sensitive_keys=("openai_api_key",))
    before = _owner_settings_snapshot(owner)
    observed = []

    async def health(client):
        observed.append((client.api_key, client.base_url, client.model))
        return {"healthy": True}

    monkeypatch.setattr(OpenAICompatibleClient, "check_health_details", health)
    response = client.post("/api/settings/test-ai")
    assert response.status_code == 200
    assert observed == [("fake-legacy-owner", "https://api.openai.com/v1" if provider == "openai" else f"http://owner-{owner}.local/v1", "owner-model")]
    assert other_client.post("/api/settings/test-ai").status_code == 422
    assert len(observed) == 1
    assert other_client.get("/api/settings").json()["has_openai_key"] is False
    assert client.get("/api/settings").json()["has_openai_key"] == (provider == "openai")
    assert _owner_settings_snapshot(owner) == before


def test_ollama_model_discovery_cannot_echo_owner_token(authenticated_client, authenticated_user, monkeypatch):
    from app.ai.client import OllamaAIClient
    from app.db.database import set_user_setting

    with Session(engine) as session:
        set_user_setting(session, authenticated_user["id"], "provider_ollama_key", "fake-owner-token")

    async def health(client):
        return {"healthy": True, "available_models": ["valid-model", "fake-owner-token", "model-fake-owner-token"]}

    monkeypatch.setattr(OllamaAIClient, "check_health_details", health)
    for response in (authenticated_client.get("/api/settings/ollama/models"), authenticated_client.post("/api/settings/test-ai", data={"ai_provider": "ollama"})):
        assert response.status_code == 200
        assert "valid-model" in response.text
        assert "fake-owner-token" not in response.text


@pytest.mark.parametrize("preset", ["local", "hybrid", "cloud"])
def test_mid_preset_flush_failure_preserves_both_owners(provider_accounts, monkeypatch, preset, caplog):
    """A failure after persisted intermediate flushes must roll back the batch."""
    from app.db import database

    owner_client, owner, other_client, other = provider_accounts
    with Session(engine) as session:
        for user_id in (owner, other):
            database.set_user_settings(session, user_id, {
                "provider_openai_key": f"fake-private-{user_id}", "ollama_model": f"owner-{user_id}",
                **{f"task_{stage}_{field}": "ollama" if field == "provider" else "prior-model"
                   for stage in ("scraping", "scoring", "applying") for field in ("provider", "model")},
            })
    before = {user_id: _owner_settings_snapshot(user_id) for user_id in (owner, other)}
    original = database.set_user_setting
    writes = []

    def interrupted(session, user_id, key, value, **kwargs):
        original(session, user_id, key, value, **kwargs)
        session.flush()
        writes.append(key)
        if len(writes) == 3:
            raise RuntimeError("fake-private-transaction <script>rollback</script>")

    monkeypatch.setattr(database, "set_user_setting", interrupted)
    response = owner_client.post("/api/settings/ai/preset", data={"preset": preset})
    assert response.status_code == 500
    assert len(writes) == 3
    assert {user_id: _owner_settings_snapshot(user_id) for user_id in (owner, other)} == before
    assert "fake-private" not in response.text + caplog.text


@pytest.mark.parametrize("env,secure", [("production", True), ("development", False)])
def test_web_login_and_register_cookie_flags_follow_config(client, monkeypatch, env, secure):
    from app.core.config import Settings

    monkeypatch.setattr("app.web.routes.get_settings", lambda: Settings(env=env))
    register = client.post(
        "/register",
        data={"email": "cookie@example.com", "password": "CookiePassword123", "full_name": "C"},
        follow_redirects=False,
    )
    login = client.post(
        "/login", data={"email": "cookie@example.com", "password": "CookiePassword123"}, follow_redirects=False)
    for response in (register, login):
        header = response.headers["set-cookie"].lower()
        assert "httponly" in header and "samesite=lax" in header
        assert ("secure" in header.replace("samesite", "")) is secure


# --- Phase 18: discovery isolation and secret hygiene ---

def test_provider_models_requires_authentication():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anonymous:
        response = anonymous.post("/api/settings/provider-models", data={"provider": "gemini", "api_key": "AIza-anon-0001"})
    assert response.status_code in (401, 403)
    assert "AIza-anon-0001" not in response.text


def test_discovery_never_falls_back_to_environment_key(authenticated_client, provider_transport, monkeypatch):
    """An owner without a saved key gets 422, even when a process-wide key exists."""
    from app.ai.model_catalog import reset_model_catalog
    reset_model_catalog()
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(name, "env-sentinel-key-0002")
    seen = []
    provider_transport(lambda request: seen.append(request))
    for provider in ("gemini", "openai"):
        response = authenticated_client.post("/api/settings/provider-models", data={"provider": provider})
        assert response.status_code == 422 and "env-sentinel-key-0002" not in response.text
    assert seen == []


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom"])
def test_sentinel_key_never_leaks_across_discovery_flows(authenticated_client, provider_transport, caplog, provider):
    """Keys stay in headers: no URL, response body, log or settings page contains the sentinel."""
    import httpx
    from app.ai.model_catalog import get_model_catalog, reset_model_catalog
    reset_model_catalog()
    key = f"sentinel-{provider}-key-7731"
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"models": [{"name": "models/m1", "supportedGenerationMethods": ["generateContent"]}],
                                         "data": [{"id": "m1"}]})

    provider_transport(handler)
    caplog.set_level("DEBUG")
    form = {"provider": provider, "api_key": key, "model": "m1"}
    if provider == "custom":
        form["base_url"] = "http://192.168.1.15:8080/v1"
    responses = [
        authenticated_client.post("/api/settings/provider-models", data=form),
        authenticated_client.post("/api/settings/provider-models", data={**form, "refresh": "1"}),
        authenticated_client.post("/api/settings/test-provider", data=form),
    ]
    saved = {f"provider_{provider}_key": key}
    if provider == "custom":
        saved["provider_custom_url"] = "http://192.168.1.15:8080/v1"
    responses.append(authenticated_client.post("/api/settings/ai/credentials", data=saved))
    responses.append(authenticated_client.get("/web/views/settings"))
    responses.append(authenticated_client.get("/api/settings"))
    assert all(key not in response.text for response in responses)
    assert all(key not in str(request.url) for request in seen)
    assert key not in caplog.text and key not in repr(get_model_catalog())


def test_second_owner_cannot_reuse_first_owners_key_endpoint_or_cache(authenticated_client, provider_transport):
    import httpx
    from fastapi.testclient import TestClient
    from app.ai.model_catalog import reset_model_catalog
    from app.main import app
    reset_model_catalog()
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"models": [{"name": "models/owner-a-only", "supportedGenerationMethods": ["generateContent"]}]})

    provider_transport(handler)
    authenticated_client.post("/api/settings/ai/credentials", data={"provider_gemini_key": "AIza-owner-a-0003"})
    first = authenticated_client.post("/api/settings/provider-models", data={"provider": "gemini"})
    assert "owner-a-only" in first.text
    with TestClient(app) as second:
        assert second.post("/api/auth/register", json={"email": "owner-b@example.com", "password": "OwnerBPassword123", "full_name": "B"}).status_code == 200
        denied = second.post("/api/settings/provider-models", data={"provider": "gemini"})
        assert denied.status_code == 422 and "owner-a-only" not in denied.text
        page = second.get("/web/views/settings")
        assert "AIza-owner-a-0003" not in page.text and "owner-a-only" not in page.text
    assert len(requests) == 1
    assert all(request.headers.get("x-goog-api-key") == "AIza-owner-a-0003" for request in requests)
