"""Tests for centralized configuration settings."""

from app.core.config import Settings, get_settings


def test_default_settings() -> None:
    """Verify default settings values."""
    settings = Settings()
    assert settings.app_name == "Jobot"
    assert settings.env == "development"
    assert settings.database_url == "sqlite:///data/jobot.db"
    assert settings.chroma_dir == "data/chroma"
    assert settings.ai_provider == "ollama"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.ollama_model == "llama3.1:8b"


def test_get_settings_cached() -> None:
    """Verify get_settings returns cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
