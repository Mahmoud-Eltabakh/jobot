"""Tests for pluggable AI Client interface and provider implementations."""

import pytest
import httpx
import json
from unittest.mock import AsyncMock
from types import SimpleNamespace
import asyncio
import openai
from sqlmodel import Session, select
from app.db.database import engine, get_user_setting, set_user_setting
from app.db.models import UserSetting

from app.ai import client as ai

from app.ai.client import (
    MockAIClient,
    OllamaAIClient,
    OpenAICompatibleClient,
    get_ai_client,
)
from app.db.database import get_app_setting, init_db, set_app_setting


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


@pytest.mark.asyncio
async def test_mock_ai_client_generate_and_embed() -> None:
    """Verify MockAIClient returns structured response and embeddings."""
    client = MockAIClient()
    response = await client.generate("Test prompt")
    assert "fit_score" in response

    embedding = await client.embed("Python software engineer")
    assert len(embedding) == 384
    assert isinstance(embedding[0], float)

    health = await client.check_health()
    assert health is True


def test_ai_client_factory_resolution() -> None:
    """Test get_ai_client resolves Ollama or OpenAI based on AppSettings."""
    # Default is Ollama
    set_app_setting("ai_provider", "ollama")
    client = get_ai_client()
    assert isinstance(client, OllamaAIClient)
    assert client.model == get_app_setting("ollama_model")

    # Switch to OpenAI
    set_app_setting("ai_provider", "openai")
    set_app_setting("openai_api_key", "sk-test-key-123")
    client_openai = get_ai_client()
    assert isinstance(client_openai, OpenAICompatibleClient)
    assert client_openai.api_key == "sk-test-key-123"

    # Reset back to Ollama
    set_app_setting("ai_provider", "ollama")


@pytest.fixture
def native_transport(monkeypatch):
    """Keep every native provider request on a deterministic in-memory transport."""
    original_client = httpx.AsyncClient

    def install(handler):
        transport = httpx.MockTransport(handler)
        monkeypatch.setattr(ai.httpx, "AsyncClient", lambda **kwargs: original_client(
            **kwargs, transport=transport,
        ))

    return install


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["anthropic", "gemini"])
async def test_native_payload_and_health(provider, native_transport):
    requests = []

    def respond(request):
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"models": [], "data": []})
        if provider == "anthropic":
            return httpx.Response(200, json={"stop_reason": "end_turn", "content": [
                {"type": "thinking", "thinking": "hidden"},
                {"type": "text", "text": '{"ok":true}'},
            ]})
        return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"thought": True, "text": "hidden"}, {"text": '{"ok":true}'}],
        }}]})

    native_transport(respond)
    adapter = getattr(ai, "AnthropicClient" if provider == "anthropic" else "GeminiClient")
    client = adapter(api_key="native-secret", model="test-model")
    assert await client.generate("user data", "system rules") == '{"ok":true}'
    payload = json.loads(requests[0].content)
    assert "native-secret" not in str(requests[0].url)
    if provider == "anthropic":
        assert requests[0].url.path == "/v1/messages"
        assert requests[0].headers["x-api-key"] == "native-secret"
        assert requests[0].headers["anthropic-version"] == "2023-06-01"
        assert payload["max_tokens"] == 4096
        assert "system rules" in payload["system"] and "JSON" in payload["system"]
        assert payload["messages"] == [{"role": "user", "content": "user data"}]
    else:
        assert requests[0].url.path == "/v1beta/models/test-model:generateContent"
        assert requests[0].headers["x-goog-api-key"] == "native-secret"
        assert payload["systemInstruction"]["parts"][0]["text"] == "system rules"
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert payload["contents"][0]["parts"][0]["text"] == "user data"
    health = await client.check_health_details()
    assert health["healthy"] is True
    assert health["model_capability"] == "unverified"
    assert [request.method for request in requests] == ["POST", "GET"]
    with pytest.raises(NotImplementedError, match="get_embedding_client"):
        await client.embed("text")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["anthropic", "gemini"])
@pytest.mark.parametrize("status,category", [(401, "authentication"), (403, "authentication"),
    (402, "quota"), (429, "rate_limit"), (503, "unavailable"), (200, "invalid_response")])
async def test_native_safe_errors(provider, status, category, native_transport, caplog):
    native_transport(lambda request: httpx.Response(status, text="native-secret https://secret.invalid/?key=secret"))
    adapter = getattr(ai, "AnthropicClient" if provider == "anthropic" else "GeminiClient")
    client = adapter(api_key="native-secret", model="test-model")
    with pytest.raises(ai.AIProviderError) as caught:
        await client.generate("prompt")
    error = caught.value
    assert error.provider == provider and error.model == "test-model"
    assert error.category == category
    assert error.status_code == (status if status != 200 else None)
    assert "native-secret" not in str(error) + caplog.text
    assert "https://" not in str(error)
    assert error.__suppress_context__
    health = await client.check_health_details()
    assert health["healthy"] is False
    assert "native-secret" not in json.dumps(health)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,payload", [
    ("anthropic", {}), ("anthropic", {"error": {"message": "secret"}}),
    ("anthropic", {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "{}"}]}),
    ("anthropic", {"content": [{"type": "text", "text": " "}]}),
    ("anthropic", {"content": [{"type": "text", "text": "not json"}]}),
    ("gemini", {}), ("gemini", {"promptFeedback": {"blockReason": "SAFETY"}}),
    ("gemini", {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{}"}]}}]}),
    ("gemini", {"candidates": [{"content": {"parts": [{"thought": True, "text": "{}"}]}}]}),
    ("gemini", {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}),
    ("gemini", {"candidates": [None]}),
])
async def test_native_rejects_invalid_content(provider, payload, native_transport):
    native_transport(lambda request: httpx.Response(200, json=payload))
    adapter = getattr(ai, "AnthropicClient" if provider == "anthropic" else "GeminiClient")
    with pytest.raises(ai.AIProviderError, match="invalid_response"):
        await adapter(api_key="fake", model="model").generate("prompt")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["anthropic", "gemini"])
async def test_native_timeout_and_text_mode(provider, native_transport):
    def timeout(request):
        raise httpx.ReadTimeout("key=fake https://secret.invalid", request=request)

    native_transport(timeout)
    adapter = getattr(ai, "AnthropicClient" if provider == "anthropic" else "GeminiClient")
    client = adapter(api_key="fake", model="model")
    with pytest.raises(ai.AIProviderError) as caught:
        await client.generate("prompt")
    assert caught.value.category == "timeout"
    assert "secret.invalid" not in str(caught.value)

    def text_response(request):
        payload = json.loads(request.content)
        if provider == "anthropic":
            assert "system" not in payload
            return httpx.Response(200, json={"content": [{"type": "text", "text": "plain"}]})
        assert "responseMimeType" not in payload["generationConfig"]
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "plain"}]}}]})

    native_transport(text_response)
    assert await client.generate("prompt", json_mode=False) == "plain"


@pytest.mark.parametrize("provider,endpoint", [
    ("openai", "https://api.openai.com/v1"), ("groq", "https://api.groq.com/openai/v1"),
    ("deepseek", "https://api.deepseek.com"), ("openrouter", "https://openrouter.ai/api/v1"),
])
def test_compatible_provider_defaults(provider, endpoint):
    client = ai.OpenAICompatibleClient("fake", provider=provider)
    assert client.base_url == endpoint
    assert client.model == ai.PROVIDER_DEFAULTS[provider]["model"]
    assert client.client.max_retries == 0
    assert client.client.timeout.connect == 5
    assert client.client.timeout.read == 120
    assert set(ai.PROVIDER_DEFAULTS) == {
        "ollama", "openai", "groq", "deepseek", "openrouter", "anthropic", "gemini", "custom",
    }


@pytest.mark.parametrize("url", ["", "ftp://host", "https://user:secret@host", "https://host?key=secret", "https://host/#secret", "not a url"])
def test_custom_endpoint_validation(url):
    with pytest.raises(ai.AIProviderError, match="configuration"):
        ai.OpenAICompatibleClient("fake", base_url=url, provider="custom", model="model")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "groq", "deepseek", "openrouter", "custom", "ollama"])
@pytest.mark.parametrize("status,category", [(401, "authentication"), (403, "authentication"),
    (402, "quota"), (429, "rate_limit"), (503, "unavailable"), (None, "timeout")])
async def test_existing_adapter_safe_failures(provider, status, category, caplog):
    request = httpx.Request("POST", "https://secret.invalid/?key=private-key")
    if provider == "ollama":
        client = ai.OllamaAIClient()
        error = ai.ollama.ResponseError("private-key https://secret.invalid", status) if status else httpx.ReadTimeout("private-key")
        client.client.chat = AsyncMock(side_effect=error)
        client.client.embeddings = AsyncMock(side_effect=error)
    else:
        client = ai.OpenAICompatibleClient("private-key", provider=provider, base_url="https://test.invalid/v1", model="test-model")
        error = openai.APIStatusError("private-key https://secret.invalid", response=httpx.Response(status, request=request),
                                    body={"error": "private-key"}) if status else openai.APITimeoutError(request=request)
        client.client.chat.completions.create = AsyncMock(side_effect=error)
        client.client.embeddings.create = AsyncMock(side_effect=error)
        client.client.models.list = AsyncMock(side_effect=error)
    for action in (client.generate, client.embed):
        with pytest.raises(ai.AIProviderError) as caught:
            await action("prompt")
        assert caught.value.provider == provider
        assert caught.value.category == category
        assert caught.value.status_code == status
        assert caught.value.__suppress_context__
        assert "private-key" not in str(caught.value) + caplog.text
        assert "https://" not in str(caught.value)
    if provider != "ollama":
        health = await client.check_health_details()
        assert health["healthy"] is False
        assert "private-key" not in json.dumps(health)
        assert "secret.invalid" not in json.dumps(health)


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, "", " ", "not json"])
@pytest.mark.parametrize("provider", ["openai", "ollama"])
async def test_existing_adapter_rejects_empty_and_invalid_json(provider, content):
    if provider == "openai":
        client = ai.OpenAICompatibleClient("fake")
        client.client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=content, refusal=None))]))
    else:
        client = ai.OllamaAIClient()
        client.client.chat = AsyncMock(return_value={"message": {"content": content}})
    with pytest.raises(ai.AIProviderError, match="invalid_response"):
        await client.generate("prompt")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "ollama", "anthropic", "gemini"])
async def test_adapter_cancellation_propagates(provider, monkeypatch):
    if provider in ("anthropic", "gemini"):
        client = (ai.AnthropicClient if provider == "anthropic" else ai.GeminiClient)("fake")
        monkeypatch.setattr(client, "_request", AsyncMock(side_effect=asyncio.CancelledError))
    elif provider == "openai":
        client = ai.OpenAICompatibleClient("fake")
        client.client.chat.completions.create = AsyncMock(side_effect=asyncio.CancelledError)
    else:
        client = ai.OllamaAIClient()
        client.client.chat = AsyncMock(side_effect=asyncio.CancelledError)
    with pytest.raises(asyncio.CancelledError):
        await client.generate("prompt")


@pytest.mark.asyncio
async def test_ollama_health_sanitizes_remote_errors(native_transport):
    native_transport(lambda request: httpx.Response(503, text="private-key https://secret.invalid"))
    health = await ai.OllamaAIClient().check_health_details()
    assert not health["healthy"]
    assert "private-key" not in json.dumps(health)
    assert "secret.invalid" not in json.dumps(health)


@pytest.mark.asyncio
async def test_compatible_payload_text_and_embedding_compatibility():
    client = ai.OpenAICompatibleClient("fake")
    client.client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(
        finish_reason="stop", message=SimpleNamespace(content='{"ok":true}', refusal=None))]))
    assert await client.generate("user", "system") == '{"ok":true}'
    kwargs = client.client.chat.completions.create.call_args.kwargs
    assert kwargs["messages"] == [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}]
    assert kwargs["response_format"] == {"type": "json_object"}
    client.client.chat.completions.create.return_value.choices[0].message.content = "plain text"
    assert await client.generate("user", json_mode=False) == "plain text"
    assert "response_format" not in client.client.chat.completions.create.call_args.kwargs
    client.client.embeddings.create = AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2])]))
    assert await client.embed("text") == [0.1, 0.2]
    client.client.models.list = AsyncMock(return_value=SimpleNamespace(data=[]))
    health = await client.check_health_details()
    assert health["healthy"] and health["model_capability"] == "unverified"


@pytest.fixture
def owner_settings(client, authenticated_user):
    """Use two independently registered accounts and the real encrypted settings API."""
    response = client.post("/api/auth/register", json={
        "email": "second-owner@example.com", "password": "SecondOwnerPassword123", "full_name": "Second Owner",
    })
    assert response.status_code == 200
    with Session(engine) as session:
        yield session, authenticated_user["id"], response.json()["id"]


@pytest.mark.parametrize("provider", list(("ollama", "openai", "groq", "deepseek", "openrouter", "anthropic", "gemini", "custom")))
def test_owner_task_routes_every_provider(owner_settings, provider):
    session, owner, other = owner_settings
    set_user_setting(session, owner, "ai_provider", "ollama")
    set_user_setting(session, owner, "task_applying_provider", provider)
    set_user_setting(session, owner, "task_applying_model", "owner-model")
    set_user_setting(session, owner, f"provider_{provider}_key", "owner-key", sensitive=True)
    set_user_setting(session, other, f"provider_{provider}_key", "foreign-key", sensitive=True)
    set_user_setting(session, owner, "provider_custom_url", "https://owner.invalid/v1")
    client = ai.get_ai_client(session, owner, task_type="applying")
    assert client.provider == provider and client.model == "owner-model"
    if provider != "ollama":
        assert client.api_key == "owner-key"
    assert get_user_setting(session, owner, "ai_provider") == "ollama"
    assert ai.get_ai_client(session, owner).provider == "ollama"


@pytest.mark.parametrize("provider", ["openai", "groq", "deepseek", "openrouter", "anthropic", "gemini", "custom"])
@pytest.mark.parametrize("with_session", [True, False])
def test_owner_never_inherits_global_or_foreign_key(owner_settings, monkeypatch, provider, with_session):
    session, owner, other = owner_settings
    set_app_setting("openai_api_key", "global-secret")
    monkeypatch.setattr(ai.get_settings(), "openai_api_key", "environment-secret")
    set_user_setting(session, other, f"provider_{provider}_key", "foreign-secret", sensitive=True)
    set_user_setting(session, owner, "ai_provider", provider)
    set_user_setting(session, owner, "task_scoring_model", "model")
    set_user_setting(session, owner, "provider_custom_url", "https://owner.invalid/v1")
    with pytest.raises(ai.AIProviderError, match="configuration") as caught:
        ai.get_ai_client(session if with_session else None, owner)
    assert caught.value.provider == provider
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("provider", ["openai", "custom"])
def test_owner_legacy_positional_and_user_id_only(owner_settings, provider):
    session, owner, other = owner_settings
    set_user_setting(session, owner, "ai_provider", provider)
    set_user_setting(session, owner, "openai_api_key", "legacy-owner-key", sensitive=True)
    set_user_setting(session, owner, "openai_base_url", "https://legacy-owner.invalid/v1")
    set_user_setting(session, owner, "openai_model", "legacy-owner-model")
    set_user_setting(session, other, "openai_api_key", "foreign-key", sensitive=True)
    if provider == "openai":
        canonical = ai.PROVIDER_DEFAULTS["openai"]["base_url"]
        assert ai.get_provider_defaults(session, owner, "openai")["base_url"] == canonical
        from app.api.settings import _owner_endpoint
        assert _owner_endpoint(session, owner, "openai") == canonical
        for resolved in (lambda: ai.get_ai_client(session, owner), lambda: ai.get_ai_client(user_id=owner)):
            with pytest.raises(ai.AIProviderError, match="configuration"):
                resolved()
    else:
        for client in (ai.get_ai_client(session, owner), ai.get_ai_client(user_id=owner)):
            assert client.api_key == "legacy-owner-key"
            assert client.base_url == "https://legacy-owner.invalid/v1"
            assert client.model == "legacy-owner-model"
    set_user_setting(session, owner, f"provider_{provider}_key", "vault-key", sensitive=True)
    if provider == "custom":
        assert ai.get_ai_client(session, owner).api_key == "vault-key"


def test_task_precedence_and_no_cross_provider_legacy_credentials(owner_settings):
    session, owner, other = owner_settings
    set_user_setting(session, owner, "ai_provider", "openai")
    set_user_setting(session, owner, "openai_model", "legacy-model")
    set_user_setting(session, owner, "openai_api_key", "legacy-key", sensitive=True)
    set_user_setting(session, owner, "task_scraping_provider", "groq")
    with pytest.raises(ai.AIProviderError, match="configuration"):
        ai.get_ai_client(session, owner, task_type="scraping")
    set_user_setting(session, owner, "provider_groq_key", "groq-key", sensitive=True)
    assert ai.get_ai_client(session, owner, task_type="scraping").model == ai.PROVIDER_DEFAULTS["groq"]["model"]
    set_user_setting(session, owner, "task_scoring_model", "task-model")
    assert ai.get_ai_client(session, owner).model == "task-model"
    set_user_setting(session, owner, "task_applying_provider", "custom")
    set_user_setting(session, owner, "task_applying_model", "custom-model")
    set_user_setting(session, owner, "provider_custom_url", "https://custom.invalid/v1")
    with pytest.raises(ai.AIProviderError, match="configuration"):
        ai.get_ai_client(session, owner, task_type="applying")


@pytest.mark.parametrize("with_session", [True, False])
def test_embedding_resolver_is_owner_local_fixed_and_read_only(owner_settings, with_session):
    session, owner, other = owner_settings
    set_user_setting(session, owner, "ai_provider", "openai")
    set_user_setting(session, owner, "task_embeddings_provider", "unknown-provider")
    set_user_setting(session, owner, "ollama_base_url", "http://owner.invalid:11434")
    set_user_setting(session, other, "ollama_base_url", "http://foreign.invalid:11434")
    set_user_setting(session, owner, "ollama_embed_model", "must-not-use")
    set_user_setting(session, owner, "provider_ollama_key", "local-owner-token", sensitive=True)
    before = [(record.key, record.value_json) for record in session.exec(select(UserSetting)).all()]
    for client in (ai.get_embedding_client(session if with_session else None, owner),
                   ai.get_ai_client(session if with_session else None, owner, task_type="embeddings")):
        assert isinstance(client, ai.OllamaAIClient)
        assert client.base_url == "http://owner.invalid:11434"
        assert client.embed_model == "nomic-embed-text"
        assert client._headers == {"Authorization": "Bearer local-owner-token"}
    after = [(record.key, record.value_json) for record in session.exec(select(UserSetting)).all()]
    assert before == after


def test_unknown_ids_reject_and_installation_calls_remain_valid(owner_settings):
    session, owner, other = owner_settings
    with pytest.raises(ValueError):
        ai.get_ai_client(session, owner, task_type="unknown")
    set_user_setting(session, owner, "ai_provider", "unknown")
    with pytest.raises(ValueError):
        ai.get_ai_client(session, owner)
    set_app_setting("ai_provider", "unknown")
    with pytest.raises(ValueError):
        ai.get_ai_client()
    set_app_setting("ai_provider", "openai")
    set_app_setting("openai_api_key", "installation-key")
    for client in (ai.get_ai_client(), ai.get_ai_client(session)):
        assert client.api_key == "installation-key"
    assert ai.get_embedding_client().embed_model == "nomic-embed-text"


def test_owner_custom_endpoint_does_not_inherit_installation_endpoint(owner_settings):
    session, owner, other = owner_settings
    set_app_setting("openai_base_url", "https://global.invalid/v1")
    set_app_setting("provider_custom_url", "https://global-custom.invalid/v1")
    set_user_setting(session, owner, "ai_provider", "custom")
    set_user_setting(session, owner, "provider_custom_key", "owner-key", sensitive=True)
    set_user_setting(session, owner, "task_scoring_model", "owner-model")
    with pytest.raises(ai.AIProviderError, match="configuration"):
        ai.get_ai_client(session, owner)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["anthropic", "gemini"])
async def test_native_has_whole_request_deadline(provider, native_transport, monkeypatch):
    deadlines = []
    original_wait_for = asyncio.wait_for

    async def observe_deadline(awaitable, timeout):
        deadlines.append(timeout)
        return await original_wait_for(awaitable, timeout)

    monkeypatch.setattr(ai.asyncio, "wait_for", observe_deadline)
    payload = {"content": [{"type": "text", "text": "{}"}]} if provider == "anthropic" else {
        "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
    }
    native_transport(lambda request: httpx.Response(200, json=payload))
    adapter = ai.AnthropicClient if provider == "anthropic" else ai.GeminiClient
    assert await adapter("fake").generate("prompt") == "{}"
    assert 120 in deadlines


@pytest.mark.asyncio
async def test_settings_health_check_has_python310_compatible_deadline(monkeypatch):
    from app.api.settings import _health_details

    deadlines = []
    original_wait_for = asyncio.wait_for

    async def observe_deadline(awaitable, timeout):
        deadlines.append(timeout)
        return await original_wait_for(awaitable, timeout)

    monkeypatch.setattr(ai.asyncio, "wait_for", observe_deadline)
    client = SimpleNamespace(
        provider="openai",
        model="test-model",
        api_key="fake-key",
        check_health_details=AsyncMock(return_value={"healthy": True}),
    )

    assert await _health_details(client) == {"healthy": True}
    assert deadlines == [5]


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [None, {}, {"error": {"message": "secret"}}, {"data": None}])
async def test_compatible_health_rejects_malformed_listing(payload):
    client = ai.OpenAICompatibleClient("fake")
    client.client.models.list = AsyncMock(return_value=SimpleNamespace(**payload) if isinstance(payload, dict) else payload)
    health = await client.check_health_details()
    assert not health["healthy"]
    assert health["category"] == "invalid_response"
    assert "secret" not in json.dumps(health)


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls"])
async def test_compatible_rejects_incomplete_or_refused_output(reason):
    client = ai.OpenAICompatibleClient("fake")
    client.client.chat.completions.create = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(
        finish_reason=reason, message=SimpleNamespace(content="{}", refusal=None))]))
    with pytest.raises(ai.AIProviderError, match="invalid_response"):
        await client.generate("prompt")


def _wire_adapter(provider):
    """Use production adapters and test-only credentials, never factory doubles."""
    if provider == "ollama":
        return ai.OllamaAIClient("http://local.invalid:11434", "wire-model", api_key="wire-secret")
    if provider in ("anthropic", "gemini"):
        return (ai.AnthropicClient if provider == "anthropic" else ai.GeminiClient)("wire-secret", "wire-model")
    return ai.OpenAICompatibleClient("wire-secret", provider=provider, model="wire-model",
                                     base_url="http://custom.invalid/v1" if provider == "custom" else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", list(ai.PROVIDER_DEFAULTS))
@pytest.mark.parametrize("json_mode", [True, False])
async def test_all_provider_generation_wire_contract(provider_transport, provider, json_mode):
    """Every provider preserves system/user separation and the selected model."""
    requests = []
    content = '{"ok":true}' if json_mode else "Plain application text"

    def respond(request):
        requests.append(request)
        payload = json.loads(request.content)
        assert request.method == "POST"
        assert "wire-secret" not in str(request.url)
        header = "x-api-key" if provider == "anthropic" else "x-goog-api-key" if provider == "gemini" else "Authorization"
        assert request.headers[header] == ("wire-secret" if provider in ("anthropic", "gemini") else "Bearer wire-secret")
        if provider == "gemini":
            assert request.url.path.endswith("/wire-model:generateContent")
            assert payload["systemInstruction"]["parts"][0]["text"] == "system boundary"
            assert payload["contents"][0]["parts"][0]["text"] == "private user text"
            assert (payload["generationConfig"].get("responseMimeType") == "application/json") == json_mode
            body = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": content}]}}]}
        elif provider == "anthropic":
            assert payload["model"] == "wire-model"
            assert payload["system"].startswith("system boundary")
            assert ("Return only valid JSON" in payload["system"]) == json_mode
            assert payload["messages"] == [{"role": "user", "content": "private user text"}]
            body = {"stop_reason": "end_turn", "content": [{"type": "text", "text": content}]}
        else:
            assert payload["model"] == "wire-model"
            assert payload["messages"] == [{"role": "system", "content": "system boundary"}, {"role": "user", "content": "private user text"}]
            assert (payload.get("format") == "json" if provider == "ollama" else payload.get("response_format") == {"type": "json_object"}) == json_mode
            body = {"message": {"role": "assistant", "content": content}} if provider == "ollama" else {
                "id": "wire", "object": "chat.completion", "created": 0, "model": "wire-model",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
            }
        return httpx.Response(200, json=body)

    provider_transport(respond)
    assert await _wire_adapter(provider).generate("private user text", "system boundary", json_mode) == content
    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", list(ai.PROVIDER_DEFAULTS))
@pytest.mark.parametrize("status,category", [(401, "authentication"), (403, "authentication"),
    (402, "quota"), (429, "rate_limit"), (503, "unavailable"), (200, "invalid_response")])
async def test_all_provider_wire_failures_do_not_retry_or_reflect(provider_transport, provider, status, category, caplog):
    """Hostile remote bodies never become logs, fallback output or a second call."""
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"message": 'wire-secret <script>remote</script>'}})

    provider_transport(respond)
    with pytest.raises(ai.AIProviderError) as caught:
        await _wire_adapter(provider).generate("private user text")
    assert caught.value.category == category
    assert caught.value.status_code == (None if status == 200 else status)
    assert caught.value.provider == provider
    assert len(requests) == 1
    assert "wire-secret" not in str(caught.value) + caplog.text
    assert "<script>" not in str(caught.value) + caplog.text


# --- Phase 18: live model discovery -----------------------------------------

GEMINI_KEY = "AIza-test-secret-key-0001"


def _gemini_pages(requests):
    """Two-page Gemini catalog fixture; records every request for URL/header checks."""
    def handler(request):
        requests.append(request)
        if request.url.params.get("pageToken") == "p2":
            return httpx.Response(200, json={"models": [
                {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/<script>alert(1)</script>", "supportedGenerationMethods": ["generateContent"]},
            ]})
        return httpx.Response(200, json={"nextPageToken": "p2", "models": [
            {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent", "countTokens"]},
            {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
            {"name": "models/gemini-2.5-flash-preview-tts", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-2.0-flash-image", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/legacy-no-generate", "supportedGenerationMethods": ["countTokens"]},
        ]})
    return handler


@pytest.mark.asyncio
async def test_gemini_list_models_paginates_filters_and_keeps_key_in_header(provider_transport) -> None:
    """Gemini listing unions pages, strips models/, drops non-generation families and hostile IDs."""
    requests = []
    provider_transport(_gemini_pages(requests))
    listing = await ai.GeminiClient(GEMINI_KEY).list_models()
    assert listing.models == ("gemini-2.5-flash", "gemini-2.5-pro")
    assert not listing.truncated and listing.supported
    assert len(requests) == 2
    assert requests[0].url.params["pageSize"] == "100"
    assert all(request.headers["x-goog-api-key"] == GEMINI_KEY for request in requests)
    assert all(GEMINI_KEY not in str(request.url) for request in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [1, False, {}, [], "   "])
async def test_gemini_rejects_malformed_next_page_token(provider_transport, token) -> None:
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"models": [{"name": "models/gemini-2.5-flash",
            "supportedGenerationMethods": ["generateContent"]}], "nextPageToken": token})

    provider_transport(handler)
    with pytest.raises(ai.AIProviderError, match="invalid_response"):
        await ai.GeminiClient(GEMINI_KEY).list_models()

    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("token_state", ["absent", "null", "empty"])
async def test_gemini_empty_next_page_token_completes_listing(provider_transport, token_state) -> None:
    requests = []

    def handler(request):
        requests.append(request)
        payload = {"models": [{"name": "models/gemini-2.5-flash",
            "supportedGenerationMethods": ["generateContent"]}]}
        if token_state == "null":
            payload["nextPageToken"] = None
        elif token_state == "empty":
            payload["nextPageToken"] = ""
        return httpx.Response(200, json=payload)

    provider_transport(handler)
    listing = await ai.GeminiClient(GEMINI_KEY).list_models()

    assert listing.models == ("gemini-2.5-flash",)
    assert not listing.truncated
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_anthropic_list_models_pages_with_after_id(provider_transport) -> None:
    """has_more/last_id drives after_id pagination; key is header-only."""
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.params.get("after_id") == "claude-b":
            return httpx.Response(200, json={"data": [{"id": "claude-c"}], "has_more": False})
        return httpx.Response(200, json={"data": [{"id": "claude-b"}, {"id": "Claude-a"}], "has_more": True, "last_id": "claude-b"})

    provider_transport(handler)
    listing = await ai.AnthropicClient("sk-ant-test-0003").list_models()
    assert listing.models == ("Claude-a", "claude-b", "claude-c")
    assert requests[0].url.params["limit"] == "100"
    assert all(r.headers["x-api-key"] == "sk-ant-test-0003" and "sk-ant" not in str(r.url) for r in requests)


@pytest.mark.asyncio
@pytest.mark.parametrize("has_more", [None, "false", 0, 1, []])
async def test_anthropic_rejects_malformed_has_more(provider_transport, has_more) -> None:
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": "claude-a"}], "has_more": has_more})

    provider_transport(handler)
    with pytest.raises(ai.AIProviderError, match="invalid_response"):
        await ai.AnthropicClient("sk-ant-test-0003").list_models()

    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("cursor", [None, "", "   ", 123])
async def test_anthropic_has_more_requires_valid_cursor(provider_transport, cursor) -> None:
    requests = []

    def handler(request):
        requests.append(request)
        payload = {"data": [{"id": "claude-a"}], "has_more": True}
        if cursor is not None:
            payload["last_id"] = cursor
        return httpx.Response(200, json=payload)

    provider_transport(handler)
    with pytest.raises(ai.AIProviderError, match="invalid_response"):
        await ai.AnthropicClient("sk-ant-test-0003").list_models()

    assert len(requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "groq", "deepseek", "custom"])
async def test_openai_family_list_models_filters_non_chat_ids(provider_transport, provider) -> None:
    """Embedding/audio/image/moderation IDs are excluded; unknown IDs and duplicates handled."""
    requests = []
    ids = ["gpt-4o", "gpt-4o", "text-embedding-3-small", "whisper-1", "tts-1", "gpt-4o-realtime-preview",
           "dall-e-3", "gpt-image-1", "omni-moderation-latest", "brand-new-model", "gpt-4o-audio-preview"]

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{"id": i} for i in ids]})

    provider_transport(handler)
    client = OpenAICompatibleClient("sk-test-0004", base_url="http://192.168.1.15:8080/v1" if provider == "custom" else None,
                                    model="m", provider=provider)
    listing = await client.list_models()
    assert listing.models == ("brand-new-model", "gpt-4o")
    assert requests[0].headers["authorization"] == "Bearer sk-test-0004"
    assert requests[0].url.path.endswith("/models") and not requests[0].url.query


@pytest.mark.asyncio
async def test_openrouter_list_models_requires_text_output(provider_transport) -> None:
    """Only entries whose architecture.output_modalities include text survive."""
    provider_transport(lambda request: httpx.Response(200, json={"data": [
        {"id": "a/text", "architecture": {"output_modalities": ["text"]}},
        {"id": "b/image", "architecture": {"output_modalities": ["image"]}},
        {"id": "c/unknown"},
    ]}))
    listing = await OpenAICompatibleClient("k-or-5", model="m", provider="openrouter").list_models()
    assert listing.models == ("a/text",)


@pytest.mark.asyncio
async def test_ollama_list_models_splits_embedding_families_and_maps_errors(provider_transport) -> None:
    """Chat vs embedding split via family/name; an unauthorized host is an error, not []."""
    state = {"status": 200}

    def handler(request):
        if state["status"] != 200:
            return httpx.Response(state["status"], json={"error": "nope"})
        return httpx.Response(200, json={"models": [
            {"name": "llama3.1:8b", "details": {"family": "llama"}},
            {"name": "nomic-embed-text:latest", "details": {"family": "nomic-bert"}},
            {"name": "bge-m3", "details": {"family": "bert"}},
            {"name": "snowflake-embed:1"},
        ]})

    provider_transport(handler)
    client = OllamaAIClient(base_url="http://192.168.1.15:11434", api_key="ollama-token")
    listing = await client.list_models()
    assert listing.models == ("llama3.1:8b",)
    assert listing.embedding_models == ("bge-m3", "nomic-embed-text:latest", "snowflake-embed:1")
    state["status"] = 401
    with pytest.raises(ai.AIProviderError) as raised:
        await client.list_models()
    assert raised.value.category == "authentication"


@pytest.mark.asyncio
async def test_base_client_list_models_is_unsupported() -> None:
    """Legacy/mock adapters report unsupported instead of an empty catalog."""
    listing = await MockAIClient().list_models()
    assert listing.supported is False and listing.models == ()


def _clients(secret):
    """One adapter per provider, built with the same secret."""
    return {
        "gemini": ai.GeminiClient(secret), "anthropic": ai.AnthropicClient(secret),
        "openai": OpenAICompatibleClient(secret, model="m", provider="openai"),
        "groq": OpenAICompatibleClient(secret, model="m", provider="groq"),
        "deepseek": OpenAICompatibleClient(secret, model="m", provider="deepseek"),
        "openrouter": OpenAICompatibleClient(secret, model="m", provider="openrouter"),
        "custom": OpenAICompatibleClient(secret, base_url="http://192.168.1.15:8080/v1", model="m", provider="custom"),
        "ollama": OllamaAIClient(base_url="http://192.168.1.15:11434", api_key=secret),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("response, category", [
    (httpx.Response(401, json={}), "authentication"),
    (httpx.Response(403, json={}), "authentication"),
    (httpx.Response(429, json={}), "rate_limit"),
    (httpx.Response(503, json={}), "unavailable"),
    (httpx.Response(302, headers={"location": "http://evil.invalid/"}), "unavailable"),
    (httpx.Response(200, content=b"<html>not json</html>"), "invalid_response"),
    (httpx.Response(200, json=[1, 2]), "invalid_response"),
    (httpx.Response(200, content=b'{"models": "' + b"x" * (1024 * 1024 + 10) + b'"}'), "invalid_response"),
    (httpx.Response(200, json={"models": {}, "data": {}}), "invalid_response"),
])
@pytest.mark.parametrize("provider", ["gemini", "anthropic", "openai", "ollama"])
async def test_list_models_failures_map_to_safe_categories(provider_transport, provider, response, category) -> None:
    """Every failure class is a sanitized AIProviderError; redirects are never followed."""
    provider_transport(lambda request: response)
    with pytest.raises(ai.AIProviderError) as raised:
        await _clients("sk-hostile-0006")[provider].list_models()
    assert raised.value.category == category
    assert "sk-hostile-0006" not in str(raised.value) and "evil.invalid" not in str(raised.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("error, category", [
    (httpx.ReadTimeout("slow"), "timeout"), (httpx.ConnectError("refused"), "unavailable"),
])
async def test_list_models_transport_errors(provider_transport, error, category) -> None:
    """Timeouts and connection failures stay distinguishable and secret-free."""
    def handler(request):
        raise error

    provider_transport(handler)
    with pytest.raises(ai.AIProviderError) as raised:
        await ai.GeminiClient("sk-hostile-0007").list_models()
    assert raised.value.category == category


@pytest.mark.asyncio
async def test_page_cap_returns_truncated_without_extra_requests(provider_transport) -> None:
    """An endless nextPageToken chain stops at 10 pages and reports truncation."""
    requests = []

    def handler(request):
        requests.append(request)
        page = len(requests)
        return httpx.Response(200, json={"nextPageToken": f"t{page}", "models": [
            {"name": f"models/gemini-p{page}-m{i}", "supportedGenerationMethods": ["generateContent"]} for i in range(5)]})

    provider_transport(handler)
    listing = await ai.GeminiClient("sk-cap-0008").list_models()
    assert len(requests) == ai.MAX_LISTING_PAGES
    assert listing.truncated and len(listing.models) == 50


@pytest.mark.asyncio
async def test_model_cap_returns_truncated_listing(provider_transport) -> None:
    """More than 500 IDs yields exactly 500 and truncated=True, never an error."""
    provider_transport(lambda request: httpx.Response(200, json={"data": [{"id": f"model-{i:04d}"} for i in range(650)]}))
    listing = await OpenAICompatibleClient("sk-cap-0009", model="m", provider="groq").list_models()
    assert len(listing.models) == 500 and listing.truncated


def test_collect_model_ids_drops_hostile_ids() -> None:
    """Markup, whitespace, control characters, quotes and over-long IDs never survive."""
    hostile = ["<b>x</b>", "has space", "tab\tid", "new\nline", 'quo"te', "a" * 201, "", None, 7, "ok-model"]
    assert ai._collect_model_ids(hostile) == (("ok-model",), False)
    assert ai._collect_model_ids(["leaks-sk-secret-1", "fine"], "sk-secret-1") == (("fine",), False)


def test_catalog_identity_is_stable_and_keyless() -> None:
    """Equal clients give equal identities across Ollama (dict headers) and cloud (method headers)."""
    for provider, first in _clients("sk-identity-0010").items():
        second = _clients("sk-identity-0010")[provider]
        identity = ai._catalog_identity(first)
        assert identity == ai._catalog_identity(second)
        assert identity[0] == provider and "sk-identity-0010" not in "".join(identity)
        assert identity != ai._catalog_identity(_clients("sk-other-key")[provider])
    assert ai._catalog_identity(OllamaAIClient(base_url="http://Host:11434/"))[1:] == ("http://host:11434", "")
    assert ai._catalog_identity(OllamaAIClient(base_url="http://host:80"))[1] == "http://host"


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["gemini", "anthropic", "openai", "groq", "deepseek", "openrouter", "custom", "ollama"])
async def test_adversarial_key_echo_never_surfaces(provider_transport, provider, caplog) -> None:
    """A provider that echoes the key in IDs or error text cannot leak it via exception or logs."""
    secret = "sk-adversarial-0011"
    echo = {"models": [{"name": f"models/gemini-{secret}", "supportedGenerationMethods": ["generateContent"]}],
            "data": [{"id": f"id-{secret}", "architecture": {"output_modalities": ["text"]}}],
            "has_more": False}
    state = {"ok": True}

    def handler(request):
        if state["ok"]:
            return httpx.Response(200, json=echo)
        return httpx.Response(500, json={"error": f"bad key {secret}"})

    provider_transport(handler)
    client = _clients(secret)[provider]
    caplog.set_level("DEBUG")
    listing = await client.list_models()
    assert all(secret not in model for model in listing.models + listing.embedding_models)
    state["ok"] = False
    with pytest.raises(ai.AIProviderError) as raised:
        await client.list_models()
    assert secret not in str(raised.value) and secret not in repr(raised.value) and raised.value.__cause__ is None
    assert secret not in caplog.text
