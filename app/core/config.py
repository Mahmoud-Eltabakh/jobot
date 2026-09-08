"""Centralized application settings management using Pydantic Settings."""

from functools import lru_cache
from typing import Literal, Optional
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
    debug: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite:///data/jobot.db"
    chroma_dir: str = "data/chroma"

    # AI Provider & Models
    ai_provider: Literal["ollama", "openai", "custom"] = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"

    # Cloud AI (Optional)
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # Scrapers
    scraper_default_interval_hours: int = 12
    scraper_headless: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
