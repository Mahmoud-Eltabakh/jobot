"""Tests for pluggable AI Client interface and provider implementations."""

import pytest

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
