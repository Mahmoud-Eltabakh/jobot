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
    AppSettings,
    FeedbackNote,
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
