"""Centralized application settings management using Pydantic Settings."""

from functools import lru_cache
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

ENV_PREFIX = "JOBOT_"


class _PrefixedEnvSource(PydanticBaseSettingsSource):
    """Expose JOBOT_<NAME> variables (used by compose/k8s) as <NAME>."""

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        return os.environ.get(ENV_PREFIX + field_name.upper()), field_name, False

    def __call__(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for name in self.settings_cls.model_fields:
            value, _, _ = self.get_field_value(None, name)
            if value is not None:
                values[name] = value
        return values


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Unprefixed env wins over JOBOT_*, which wins over .env.
        return (init_settings, env_settings, _PrefixedEnvSource(settings_cls), dotenv_settings, file_secret_settings)

    # General
    app_name: str = "Jobot"
    env: str = "development"
    debug: bool = False  # Set DEBUG=true in .env for development only
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    secret_key: str | None = None
    encryption_key: str | None = None
    encryption_key_id: str = "local"
    encryption_key_file: str = "data/.jobot-encryption-key"
    previous_encryption_keys: str = ""

    # Database
    data_dir: str | None = None  # JOBOT_DATA_DIR: base for DB/Chroma/key paths not set explicitly
    database_url: str = "sqlite:///data/jobot.db"
    chroma_dir: str = "data/chroma"

    # AI Provider & Models
    ai_provider: Literal["ollama", "openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"

    # Cloud AI (Optional)
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Scrapers
    scraper_default_interval_hours: int = 12
    scraper_headless: bool = True
    concurrency_max_scrapers: int = 2
    concurrency_max_evaluators: int = 3
    scraping_stagger_delay_seconds: float = 0.5

    # Tailscale SSH remote access
    tailscale_enabled: bool = False
    tailscale_hostname: str = ""
    tailscale_ssh_user: str = ""
    tailscale_ssh_port: int = 22
    tailscale_app_port: int = 8000
    tailscale_magic_dns: bool = True

    @model_validator(mode="after")
    def _apply_data_dir(self) -> "Settings":
        # Explicitly configured paths always win over the data_dir-derived defaults.
        if self.data_dir:
            base = Path(self.data_dir).as_posix().rstrip("/")
            if "database_url" not in self.model_fields_set:
                self.database_url = f"sqlite:///{base}/jobot.db"
            if "chroma_dir" not in self.model_fields_set:
                self.chroma_dir = f"{base}/chroma"
            if "encryption_key_file" not in self.model_fields_set:
                self.encryption_key_file = f"{base}/.jobot-encryption-key"
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
