"""SQLite connection, settings persistence, and owner credential migration.

Engine configuration is captured at import time. Test processes must select
disposable database and encryption storage before importing this module;
changing a Settings instance afterward does not replace the live engine.
AppSettings remains installation-scoped and is not an account credential vault.
UserSetting decryption requires the same owner used to encrypt the record.
The provider vault reuses that authenticated encryption instead of adding a
second key store or treating configuration defaults as account credentials.
Batch callers own their session transaction, including any autoflushed writes.
"""

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
    """Seed missing installation defaults without replacing existing settings.

    No credentials are copied from environment configuration into AppSettings.
    Existing installation secrets are neither deleted nor claimed by accounts.
    Task fields are intentionally absent: global stage defaults would override
    the factory's owner legacy resolution before the owner can migrate.
    Repeated initialization preserves existing provider and model selections.
    """
    default_settings = [
        ("ai_provider", settings.ai_provider, "Default generation provider"),
        ("ollama_base_url", settings.ollama_base_url, "Local Ollama HTTP endpoint"),
        ("ollama_model", settings.ollama_model, "Ollama LLM model for job evaluation"),
        ("ollama_embed_model", settings.ollama_embed_model, "Ollama embedding model for RAG"),
        ("openai_base_url", settings.openai_base_url, "OpenAI / Custom API endpoint"),
        ("openai_model", settings.openai_model, "Cloud AI LLM model"),
        ("scraper_default_interval_hours", settings.scraper_default_interval_hours, "Default scraper interval in hours"),
        ("weight_skills", 70, "Weight scale for profile skills match (0-100)"),
        ("weight_title", 15, "Weight scale for target title and seniority match (0-100)"),
        ("weight_location", 10, "Weight scale for workplace and location preference (0-100)"),
        ("weight_experience", 5, "Weight scale for experience relevance (0-100)"),
        ("weight_vector", 20, "Weight scale for vector semantic RAG similarity (0-100)"),
        ("weight_history_skills", 10, "Weight scale for prior role and project skill overlap (0-100)"),
        ("weight_education", 5, "Weight scale for education relevance to the target role (0-100)"),
        ("weight_projects", 10, "Weight scale for project evidence and applied technologies (0-100)"),
        ("concurrency_max_scrapers", settings.concurrency_max_scrapers, "Maximum concurrent scraping queries (1-5)"),
        ("concurrency_max_evaluators", settings.concurrency_max_evaluators, "Maximum concurrent AI evaluations (1-8)"),
        ("scraping_stagger_delay_seconds", settings.scraping_stagger_delay_seconds, "Stagger delay between concurrent scraping requests in seconds"),
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
    commit: bool = True,
) -> None:
    """Persist an owner value, optionally deferring commit to its batch caller.

    Provider vault keys are always encrypted, even if a caller omits sensitive.
    Empty secret forms mean preserve, not delete or rewrite the ciphertext.
    Other callers retain the historical one-write/one-commit behavior.
    JSON serialization happens before encryption so stored credentials cannot
    masquerade as an already-encrypted envelope by submitting a prefix.
    Encryption is bound to user_id; moving ciphertext across owners fails.
    A deferred write can autoflush on a later SELECT but cannot commit itself.
    Its caller must roll back if a later operation or final commit fails.
    No session or decrypted credential is cached across requests.
    """
    from sqlmodel import select
    if user_id is None:
        raise PermissionError("Authenticated user has no persistent identity")

    if key in PROVIDER_SECRET_KEYS:
        if not isinstance(value, str):
            raise ValueError("Invalid provider credential")
        if not value.strip():
            return
        sensitive = True
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
    if commit:
        session.commit()


PROVIDER_SECRET_KEYS = frozenset(
    f"provider_{provider}_key" for provider in
    ("ollama", "openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom")
)


def set_user_settings(
    session: Session,
    user_id: int | None,
    values: dict[str, Any],
    *,
    sensitive_keys: tuple[str, ...] = (),
    commit: bool = True,
) -> None:
    """Apply one owner batch atomically, including encryption and flush failures.

    No inner write commits: a later failure rolls back the entire prefix.
    commit=False lets migration participate in the endpoint's transaction.
    Callers must validate the full input before entering this write boundary.
    sensitive_keys extends encryption to legacy/non-provider secret fields;
    known provider slots cannot opt out by omitting this argument.
    Rollback includes already-flushed rows and encrypted replacements, not
    merely changes that remain in SQLAlchemy's pending collection.
    This helper is not a nested savepoint: use a dedicated request session,
    since a failure also rolls back other pending work in that transaction.
    An identity-less caller fails before a setting can be added.
    """
    try:
        if user_id is None:
            raise PermissionError("Authenticated user has no persistent identity")
        for key, value in values.items():
            set_user_setting(session, user_id, key, value, sensitive=key in sensitive_keys, commit=False)
        if commit:
            session.commit()
    except Exception:
        session.rollback()
        raise


def migrate_legacy_ai_settings(session: Session, user_id: int, *, commit: bool = True) -> None:
    """Copy only this owner's legacy routing and matching credential, once.

    Explicit records (including empty values) win over migration defaults.
    Installation/environment secrets are never inspected or claimed here.
    A legacy custom key belongs to custom, not to the OpenAI credential slot.
    Without owner legacy configuration, leave task defaults resolver-derived.
    Only absent task fields are filled. A provider explicitly chosen for a
    stage must not receive the old provider's model as an incidental default.
    Custom URL migration is separate from the shared legacy OpenAI key name.
    Only custom accounts copy that URL into the new custom endpoint slot.
    The existing legacy ciphertext remains available to compatible callers.
    Re-running migration does not re-encrypt an existing vault record.
    With commit=False the request can apply submitted legacy settings first,
    then migrate the resulting owner state under the same rollback boundary.
    """
    missing = object()
    provider = get_user_setting(session, user_id, "ai_provider", missing)
    if provider not in ("ollama", "openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom"):
        return
    from app.ai.client import PROVIDER_DEFAULTS

    values = {}
    model_key = "openai_model" if provider in ("openai", "custom") else f"{provider}_model"
    model = get_user_setting(session, user_id, model_key, PROVIDER_DEFAULTS[provider]["model"])
    for stage in ("scraping", "scoring", "applying"):
        provider_key = f"task_{stage}_provider"
        model_key = f"task_{stage}_model"
        existing_provider = get_user_setting(session, user_id, provider_key, missing)
        if existing_provider is missing:
            values[provider_key] = provider
        if (existing_provider is missing or existing_provider == provider) and model:
            if get_user_setting(session, user_id, model_key, missing) is missing:
                values[model_key] = model
    if provider in ("openai", "custom"):
        credential_key = f"provider_{provider}_key"
        legacy_key = get_user_setting(session, user_id, "openai_api_key", "")
        if legacy_key and get_user_setting(session, user_id, credential_key, missing) is missing:
            values[credential_key] = legacy_key
        if provider == "custom" and get_user_setting(session, user_id, "provider_custom_url", missing) is missing:
            legacy_url = get_user_setting(session, user_id, "openai_base_url", "")
            if legacy_url:
                values["provider_custom_url"] = legacy_url
    if values:
        set_user_settings(session, user_id, values, commit=commit)
