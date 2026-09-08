"""SQLite database connection engine, session management, and table initializers."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Generator, Optional
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import get_settings
from app.db.models import AppSettings

logger = logging.getLogger("jobot.db")

settings = get_settings()

# Ensure database directory exists
if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.replace("sqlite:///", "")
    db_dir = Path(db_path).parent
    if db_dir and not db_dir.exists():
        os.makedirs(db_dir, exist_ok=True)

# Create engine with thread concurrency support for SQLite
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    """Enable SQLite WAL mode and foreign key constraints on connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


def seed_default_settings(session: Session) -> None:
    """Seed default application and AI settings into database if not present."""
    default_settings = [
        ("ai_provider", settings.ai_provider, "Active AI backend (ollama, openai, custom)"),
        ("ollama_base_url", settings.ollama_base_url, "Local Ollama HTTP endpoint"),
        ("ollama_model", settings.ollama_model, "Ollama LLM model for job evaluation"),
        ("ollama_embed_model", settings.ollama_embed_model, "Ollama embedding model for RAG"),
        ("openai_base_url", settings.openai_base_url, "OpenAI / Custom API endpoint"),
        ("openai_model", settings.openai_model, "Cloud AI LLM model"),
        ("openai_api_key", settings.openai_api_key or "", "Cloud AI API key"),
        ("scraper_default_interval_hours", settings.scraper_default_interval_hours, "Default scraper interval in hours"),
        ("weight_skills", 70, "Weight scale for profile skills match (0-100)"),
        ("weight_title", 15, "Weight scale for target title and seniority match (0-100)"),
        ("weight_location", 10, "Weight scale for workplace and location preference (0-100)"),
        ("weight_experience", 5, "Weight scale for experience relevance (0-100)"),
        ("weight_vector", 20, "Weight scale for vector semantic RAG similarity (0-100)"),
    ]

    for key, val, desc in default_settings:
        existing = session.get(AppSettings, key)
        if not existing:
            setting_obj = AppSettings(
                key=key,
                value_json=json.dumps(val),
                description=desc,
            )
            session.add(setting_obj)
    session.commit()


def migrate_sqlite_columns() -> None:
    """Ensure newly added columns exist in existing SQLite tables."""
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(user_profiles)")).fetchall()
            existing_cols = {row[1] for row in res}
            cols_to_add = {
                "headline": "TEXT",
                "bio": "TEXT",
                "experience_years": "FLOAT DEFAULT 0.0",
                "work_preference": "TEXT DEFAULT 'remote_first'",
                "active_search_skills_json": "TEXT DEFAULT '[]'",
                "experience_history_json": "TEXT DEFAULT '[]'",
                "education_json": "TEXT DEFAULT '[]'",
                "cv_raw_text": "TEXT",
                "linkedin_raw_text": "TEXT",
                "linkedin_session_cookie": "TEXT",
                "linkedin_data_json": "TEXT",
                "linkedin_access_token": "TEXT",
                "linkedin_user_id": "TEXT",
                "linkedin_email": "TEXT",
                "linkedin_picture_url": "TEXT",
            }
            for col, col_type in cols_to_add.items():
                if col not in existing_cols:
                    conn.execute(text(f"ALTER TABLE user_profiles ADD COLUMN {col} {col_type}"))
            conn.commit()
        except Exception as e:
            logger.debug("Column migration skipped: %s", e)


def init_db() -> None:
    """Create all SQLModel tables in SQLite database and seed defaults."""
    logger.info("Initializing SQLite database tables at %s", settings.database_url)
    SQLModel.metadata.create_all(engine)
    migrate_sqlite_columns()
    with Session(engine) as session:
        seed_default_settings(session)
    logger.info("Database tables initialized successfully")


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding database session."""
    with Session(engine) as session:
        yield session


def get_app_setting(key: str, default: Optional[Any] = None) -> Any:
    """Retrieve an application setting value by key from the database."""
    with Session(engine) as session:
        setting_record = session.get(AppSettings, key)
        if setting_record:
            return json.loads(setting_record.value_json)
        return default


def set_app_setting(key: str, value: Any, description: Optional[str] = None) -> None:
    """Save or update an application setting in the database."""
    with Session(engine) as session:
        setting_record = session.get(AppSettings, key)
        if setting_record:
            setting_record.value_json = json.dumps(value)
            if description:
                setting_record.description = description
        else:
            setting_record = AppSettings(
                key=key,
                value_json=json.dumps(value),
                description=description,
            )
        session.add(setting_record)
        session.commit()
