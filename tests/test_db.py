"""Tests for SQLModel relational database models, session lifecycle, and settings."""

import hashlib

import pytest
from sqlmodel import Session, select

from app.db.database import (
    engine,
    get_app_setting,
    init_db,
    set_app_setting,
)
from app.db.models import (
    FilterRule,
    Job,
    JobStatus,
    JobStatusHistory,
    UserProfile,
)


@pytest.fixture(autouse=True)
def setup_test_db() -> None:
    """Ensure clean database schema before tests."""
    init_db()


def compute_hash(company: str, title: str, location: str) -> str:
    """Compute SHA256 dedup hash."""
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{location.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_job_crud_and_status_history() -> None:
    """Test creating, querying, and updating a Job with status transitions."""
    dedup = compute_hash("TechCorp", "Python Engineer", "Berlin")

    with Session(engine) as session:
        # Create Job
        job = Job(
            source="linkedin",
            title="Python Engineer",
            company="TechCorp",
            location="Berlin",
            is_remote=True,
            salary_min=75000,
            salary_max=95000,
            salary_currency="EUR",
            url="https://linkedin.com/jobs/view/12345",
            description="Looking for senior python developer.",
            status=JobStatus.SEEN.value,
            dedup_hash=dedup,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.id is not None
        assert job.status == "seen"

        # Transition status to applied
        old_status = job.status
        job.status = JobStatus.APPLIED.value
        history = JobStatusHistory(
            job_id=job.id,
            old_status=old_status,
            new_status=job.status,
            notes="Applied via website with custom CV",
        )
        session.add(job)
        session.add(history)
        session.commit()

        # Query history
        histories = session.exec(
            select(JobStatusHistory).where(JobStatusHistory.job_id == job.id)
        ).all()
        assert len(histories) == 1
        assert histories[0].new_status == "applied"
        assert histories[0].notes == "Applied via website with custom CV"


def test_job_default_status_is_new() -> None:
    """Jobs should start in the NEW state and only be listed after scoring."""
    dedup = compute_hash("Nova Labs", "Full Stack Engineer", "Berlin")

    with Session(engine) as session:
        job = Job(
            source="linkedin",
            title="Full Stack Engineer",
            company="Nova Labs",
            location="Berlin",
            is_remote=True,
            url="https://linkedin.com/jobs/view/99999",
            description="Full stack Python and frontend role.",
            dedup_hash=dedup,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        assert job.status == "new"
        assert job.fit_score is None


def test_user_profile_crud() -> None:
    """Test user profile creation and JSON list fields."""
    with Session(engine) as session:
        profile = UserProfile(
            full_name="Alex Developer",
            target_titles_json='["Senior Python Developer", "Backend Engineer"]',
            target_locations_json='["Berlin", "Remote"]',
            target_salary_min=80000,
            skills_json='["Python", "FastAPI", "Docker", "PostgreSQL"]',
            cv_raw_text="Experienced Python Backend Engineer...",
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)

        assert profile.id is not None
        assert "FastAPI" in profile.skills_json


def test_filter_rule_crud() -> None:
    """Test negative blacklist filtering rules."""
    with Session(engine) as session:
        rule = FilterRule(
            rule_type="title",
            pattern="Senior Staff",
            is_regex=False,
            is_active=True,
        )
        session.add(rule)
        session.commit()
        session.refresh(rule)

        assert rule.id is not None
        rules = session.exec(
            select(FilterRule).where(FilterRule.is_active.is_(True))
        ).all()
        assert any(r.pattern == "Senior Staff" for r in rules)


def test_app_settings_helpers() -> None:
    """Test get_app_setting and set_app_setting helpers."""
    # Read default seeded setting
    provider = get_app_setting("ai_provider")
    assert provider == "ollama"

    # Update setting dynamically
    set_app_setting("ai_provider", "openai", description="Switched to cloud API")
    updated_provider = get_app_setting("ai_provider")
    assert updated_provider == "openai"

    # Reset back to ollama
    set_app_setting("ai_provider", "ollama")


def test_owner_vault_batch_api_exists() -> None:
    """Owner vault must expose atomic writes and idempotent legacy migration."""
    from app.db import database

    assert callable(getattr(database, "set_user_settings", None))
    assert callable(getattr(database, "migrate_legacy_ai_settings", None))


def test_vault_encryption_blank_preservation_and_rollback(authenticated_user, monkeypatch) -> None:
    """A failed batch cannot persist a prefix, including after an autoflush."""
    from app.db import database
    from app.db.models import UserSetting

    owner = authenticated_user["id"]
    with Session(engine) as session:
        assert callable(getattr(database, "set_user_settings", None))
        values = {f"provider_{provider}_key": f"fake-{provider}" for provider in
                  ("ollama", "openai", "anthropic", "gemini", "groq", "deepseek", "openrouter", "custom")}
        database.set_user_settings(session, owner, values)
        records = session.exec(select(UserSetting).where(UserSetting.user_id == owner)).all()
        ciphertext = {record.key: record.value_json for record in records}
        assert all(record.is_sensitive and record.value_json.startswith("enc:v2:") for record in records)
        assert all(values[record.key] not in record.value_json for record in records)
        database.set_user_settings(session, owner, {key: "  " for key in values})
        assert {record.key: record.value_json for record in records} == ciphertext
        original = database.set_user_setting

        def fail_second(session, user_id, key, value, **kwargs):
            if key == "task_scoring_model":
                raise RuntimeError("injected batch failure")
            original(session, user_id, key, value, **kwargs)
            session.flush()

        monkeypatch.setattr(database, "set_user_setting", fail_second)
        with pytest.raises(RuntimeError, match="injected"):
            database.set_user_settings(session, owner, {"task_scoring_provider": "openai", "task_scoring_model": "new"})
        assert database.get_user_setting(session, owner, "task_scoring_provider") is None
        monkeypatch.setattr(database, "set_user_setting", original)
        monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("commit failure")))
        with pytest.raises(RuntimeError, match="commit failure"):
            database.set_user_settings(session, owner, {"provider_openai_key": "replacement", "task_scoring_provider": "openai"})
        assert database.get_user_setting(session, owner, "provider_openai_key") == "fake-openai"
        assert database.get_user_setting(session, owner, "task_scoring_provider") is None


@pytest.mark.parametrize("provider", ["openai", "custom", "ollama"])
def test_legacy_owner_ai_migration_is_idempotent(authenticated_user, provider) -> None:
    """Only a matching owner's legacy secret migrates; explicit choices win."""
    from app.db import database
    from app.db.models import UserSetting

    owner = authenticated_user["id"]
    with Session(engine) as session:
        assert callable(getattr(database, "migrate_legacy_ai_settings", None))
        database.set_user_setting(session, owner, "ai_provider", provider)
        database.set_user_setting(session, owner, "openai_api_key", "legacy-owner", sensitive=True)
        database.set_user_setting(session, owner, "openai_base_url", "http://legacy.local/v1")
        database.set_user_setting(session, owner, "openai_model", "legacy-cloud")
        database.set_user_setting(session, owner, "ollama_model", "legacy-local")
        database.set_user_setting(session, owner, "task_scoring_provider", "gemini")
        database.set_user_setting(session, owner, "task_scoring_model", "explicit-model")
        database.migrate_legacy_ai_settings(session, owner)
        assert database.get_user_setting(session, owner, "task_scraping_provider") == provider
        assert database.get_user_setting(session, owner, "task_scraping_model") == ("legacy-local" if provider == "ollama" else "legacy-cloud")
        assert database.get_user_setting(session, owner, "task_scoring_provider") == "gemini"
        assert database.get_user_setting(session, owner, "task_scoring_model") == "explicit-model"
        if provider in ("custom", "openai"):
            assert database.get_user_setting(session, owner, f"provider_{provider}_key") == "legacy-owner"
        assert database.get_user_setting(session, owner, "provider_openai_key" if provider != "openai" else "provider_custom_key") is None
        if provider == "custom":
            assert database.get_user_setting(session, owner, "provider_custom_url") == "http://legacy.local/v1"
        before = {record.key: record.value_json for record in session.exec(select(UserSetting)).all()}
        database.migrate_legacy_ai_settings(session, owner)
        assert {record.key: record.value_json for record in session.exec(select(UserSetting)).all()} == before


def test_no_owner_legacy_settings_does_not_claim_installation_secrets(authenticated_user, monkeypatch) -> None:
    """New accounts keep resolver defaults rather than seeded task overrides."""
    from app.db import database
    from app.db.models import AppSettings, UserSetting

    assert callable(getattr(database, "migrate_legacy_ai_settings", None))
    monkeypatch.setattr(database.settings, "openai_api_key", "fake-env-secret")
    with Session(engine) as session:
        database.seed_default_settings(session)
        assert session.get(AppSettings, "openai_api_key") is None
        assert not any(record.key.startswith("task_") or record.key.startswith("provider_") for record in session.exec(select(AppSettings)).all())
        database.set_app_setting("openai_api_key", "fake-global-secret")
        database.migrate_legacy_ai_settings(session, authenticated_user["id"])
        assert session.exec(select(UserSetting)).all() == []


def test_single_write_commit_compatibility_and_owner_vault_isolation(authenticated_user, monkeypatch) -> None:
    """Existing callers commit once; deferred writes can be rolled back by callers."""
    from unittest.mock import Mock
    from app.db import database
    from app.db.models import User

    owner = authenticated_user["id"]
    with Session(engine) as session:
        other = User(email="vault-other@example.com", password_hash="not-used", full_name="Other")
        session.add(other)
        session.commit()
        other_id = other.id
        commit = Mock(wraps=session.commit)
        monkeypatch.setattr(session, "commit", commit)
        database.set_user_setting(session, owner, "provider_openai_key", "fake-owner")
        assert commit.call_count == 1
        database.set_user_setting(session, owner, "task_scoring_model", "uncommitted", commit=False)
        assert commit.call_count == 1
        session.rollback()
        assert database.get_user_setting(session, owner, "task_scoring_model") is None
        assert database.get_user_setting(session, other_id, "provider_openai_key") is None
        database.migrate_legacy_ai_settings(session, other_id)
        assert database.get_user_setting(session, other_id, "provider_openai_key") is None
        database.set_user_settings(session, owner, {"provider_openai_key": "replacement", "task_scoring_model": "new"})
        assert commit.call_count == 2
        with pytest.raises(PermissionError):
            database.set_user_settings(session, None, {"provider_openai_key": "fake-key"})
