"""SQLite database connection engine, session management, and table initializers."""

import json
import logging
import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings
from app.db.models import AppSettings, UserSetting, utc_now
from app.security.encryption import decrypt_text, encrypt_text

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
        ("weight_history_skills", 10, "Weight scale for prior role and project skill overlap (0-100)"),
        ("weight_education", 5, "Weight scale for education relevance to the target role (0-100)"),
        ("weight_projects", 10, "Weight scale for project evidence and applied technologies (0-100)"),
        ("tailscale_enabled", settings.tailscale_enabled, "Enable Tailscale SSH remote access guidance"),
        ("tailscale_hostname", settings.tailscale_hostname, "Tailscale MagicDNS hostname or IP"),
        ("tailscale_ssh_user", settings.tailscale_ssh_user, "SSH user on the Jobot host"),
        ("tailscale_ssh_port", settings.tailscale_ssh_port, "SSH port exposed through Tailscale"),
        ("tailscale_app_port", settings.tailscale_app_port, "Jobot port forwarded through SSH"),
        ("tailscale_magic_dns", settings.tailscale_magic_dns, "Use Tailscale MagicDNS hostnames"),
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
    tables_to_check = [
        ("user_profiles", {
            "headline": "TEXT",
            "bio": "TEXT",
            "experience_years": "FLOAT DEFAULT 0.0",
            "work_preference": "TEXT DEFAULT 'remote_first'",
            "active_search_skills_json": "TEXT DEFAULT '[]'",
            "experience_history_json": "TEXT DEFAULT '[]'",
            "education_json": "TEXT DEFAULT '[]'",
            "projects_json": "TEXT DEFAULT '[]'",
            "cv_raw_text": "TEXT",
            "linkedin_raw_text": "TEXT",
            "linkedin_session_cookie": "TEXT",
            "linkedin_data_json": "TEXT",
            "linkedin_access_token": "TEXT",
            "linkedin_user_id": "TEXT",
            "linkedin_email": "TEXT",
            "linkedin_picture_url": "TEXT",
            "user_id": "INTEGER",
        }),
        ("jobs", {"user_id": "INTEGER"}),
        ("search_configs", {"user_id": "INTEGER"}),
        ("feedback_notes", {"user_id": "INTEGER"}),
        ("filter_rules", {"user_id": "INTEGER"}),
        ("application_materials", {"user_id": "INTEGER"}),
        ("scrape_tasks", {"user_id": "INTEGER"}),
    ]
    with engine.connect() as conn:
        for table_name, cols in tables_to_check:
            try:
                res = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
                existing_cols = {row[1] for row in res}
                for col, col_type in cols.items():
                    if col not in existing_cols:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception as e:
                logger.debug("Column migration for %s skipped: %s", table_name, e)


def init_db() -> None:
    """Create all SQLModel tables in SQLite database and seed defaults."""
    logger.info("Initializing SQLite database tables at %s", settings.database_url)
    SQLModel.metadata.create_all(engine)
    migrate_sqlite_columns()
    with Session(engine) as session:
        seed_default_settings(session)
        from app.db.ownership import migrate_legacy_user_data
        migrate_legacy_user_data(session)
    logger.info("Database tables initialized successfully")


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency yielding database session."""
    with Session(engine) as session:
        yield session


def get_app_setting(key: str, default: Any | None = None) -> Any:
    """Retrieve an application setting value by key from the database."""
    with Session(engine) as session:
        setting_record = session.get(AppSettings, key)
        if setting_record:
            return json.loads(setting_record.value_json)
        return default


def set_app_setting(key: str, value: Any, description: str | None = None) -> None:
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


def get_user_setting(
    session: Session,
    user_id: int | None,
    key: str,
    default: Any | None = None,
) -> Any:
    """Return one account-owned setting, decrypting it only for its owner."""
    from sqlmodel import select
    if user_id is None:
        raise PermissionError("Authenticated user has no persistent identity")

    record = session.exec(
        select(UserSetting).where(
            UserSetting.user_id == user_id,
            UserSetting.key == key,
        )
    ).first()
    if not record:
        return default
    serialized = decrypt_text(record.value_json, user_id=user_id) if record.is_sensitive else record.value_json
    return json.loads(serialized)


def set_user_setting(
    session: Session,
    user_id: int | None,
    key: str,
    value: Any,
    *,
    sensitive: bool = False,
) -> None:
    """Persist an account-owned setting with optional encryption at rest."""
    from sqlmodel import select
    if user_id is None:
        raise PermissionError("Authenticated user has no persistent identity")

    serialized = json.dumps(value)
    if sensitive:
        serialized = encrypt_text(serialized, user_id=user_id) or ""
    record = session.exec(
        select(UserSetting).where(
            UserSetting.user_id == user_id,
            UserSetting.key == key,
        )
    ).first()
    if record:
        record.value_json = serialized
        record.is_sensitive = sensitive
        record.updated_at = utc_now()
    else:
        record = UserSetting(
            user_id=user_id,
            key=key,
            value_json=serialized,
            is_sensitive=sensitive,
        )
    session.add(record)
    session.commit()
