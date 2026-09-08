"""Centralized application settings management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    database_url: str = "sqlite:///data/jobot.db"
    chroma_dir: str = "data/chroma"

    # AI Provider & Models
    ai_provider: Literal["ollama", "openai", "custom"] = "ollama"
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

    # Tailscale SSH remote access
    tailscale_enabled: bool = False
    tailscale_hostname: str = ""
    tailscale_ssh_user: str = ""
    tailscale_ssh_port: int = 22
    tailscale_app_port: int = 8000
    tailscale_magic_dns: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
