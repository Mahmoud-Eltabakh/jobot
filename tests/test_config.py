"""Tests for centralized configuration settings."""

import pytest

from app.core.config import Settings, get_settings


def test_default_settings(monkeypatch) -> None:
    """Verify default settings values."""
    with monkeypatch.context() as isolated:
        for field in Settings.model_fields:
            isolated.delenv(field.upper(), raising=False)
        settings = Settings(_env_file=None)
    assert settings.app_name == "Jobot"
    assert settings.env == "development"
    assert settings.database_url == "sqlite:///data/jobot.db"
    assert settings.chroma_dir == "data/chroma"
    assert settings.ai_provider == "ollama"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "llama3.1:8b"


@pytest.mark.parametrize("provider", ["ollama", "openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom"])
def test_all_provider_ids_validate(provider) -> None:
    """Every supported adapter can be selected in installation configuration."""
    assert Settings(_env_file=None, ai_provider=provider).ai_provider == provider


def test_get_settings_cached() -> None:
    """Verify get_settings returns cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_data_dir_derives_unset_paths_and_explicit_values_win(monkeypatch) -> None:
    from app.core.config import Settings

    for key in ("DATABASE_URL", "CHROMA_DIR", "ENCRYPTION_KEY_FILE", "JOBOT_DATABASE_URL", "JOBOT_CHROMA_DIR", "JOBOT_ENCRYPTION_KEY_FILE"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("JOBOT_DATA_DIR", "/srv/jobot")
    derived = Settings(_env_file=None)
    assert derived.database_url == "sqlite:////srv/jobot/jobot.db"
    assert derived.chroma_dir == "/srv/jobot/chroma"
    assert derived.encryption_key_file == "/srv/jobot/.jobot-encryption-key"

    monkeypatch.setenv("CHROMA_DIR", "/elsewhere/chroma")
    explicit = Settings(_env_file=None)
    assert explicit.chroma_dir == "/elsewhere/chroma"
    assert explicit.database_url == "sqlite:////srv/jobot/jobot.db"

    monkeypatch.delenv("JOBOT_DATA_DIR")
    monkeypatch.delenv("CHROMA_DIR")
    assert Settings(_env_file=None).database_url == "sqlite:///data/jobot.db"
