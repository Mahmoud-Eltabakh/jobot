"""SQLModel database models for Jobot."""

from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return current UTC datetime with timezone awareness."""
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    """Lifecycle status stages for job applications."""

    NEW = "new"
    SEEN = "seen"
    APPLIED = "applied"
    WAITING = "waiting for respond"
    INTERVIEW_1 = "1. interview"
    INTERVIEW_2 = "2. interview"
    INTERVIEW_3 = "3. interview"
    NOT_A_FIT = "not a good fit"
    REJECTED = "rejected"


class User(SQLModel, table=True):
    """User account for authentication and data isolation."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    full_name: str = Field(default="")
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class UserSession(SQLModel, table=True):
    """Session token record for user authentication."""

    __tablename__ = "user_sessions"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    session_token: str = Field(unique=True, index=True)
    expires_at: datetime = Field(index=True)
    revoked: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utc_now)


class Job(SQLModel, table=True):
    """Job listing scraped from job boards or added manually."""

    __tablename__ = "jobs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    source: str = Field(index=True)  # e.g. "linkedin", "stepstone", "google"
    source_id: str | None = Field(default=None, index=True)
    title: str = Field(index=True)
    company: str = Field(index=True)
    location: str = Field(index=True)
    is_remote: bool = Field(default=False, index=True)

    # Compensation
    salary_min: float | None = Field(default=None)
    salary_max: float | None = Field(default=None)
    salary_currency: str | None = Field(default=None)

    # Link & Content
    url: str = Field(index=True)
    description: str = Field(default="")

    # AI Evaluation & Fit Score (0-100)
    fit_score: int | None = Field(default=None, index=True)
    fit_summary: str | None = Field(default=None)
    pros_json: str | None = Field(default=None)  # JSON serialized list of strengths
    cons_json: str | None = Field(default=None)  # JSON serialized list of concerns
    missing_skills_json: str | None = Field(default=None)  # JSON list of missing skills

    # Status & Deduplication
    status: str = Field(default=JobStatus.NEW.value, index=True)
    dedup_hash: str = Field(unique=True, index=True)  # SHA-256 of normalized company+title+location

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class JobStatusHistory(SQLModel, table=True):
    """Audit log of status transitions and candidate comments for a job."""

    __tablename__ = "job_status_history"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    old_status: str | None = Field(default=None)
    new_status: str = Field(index=True)
    notes: str | None = Field(default=None)
    changed_at: datetime = Field(default_factory=utc_now)


class UserProfile(SQLModel, table=True):
    """Candidate profile, target preferences, and parsed CV data."""

    __tablename__ = "user_profiles"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    full_name: str = Field(default="")
    headline: str | None = Field(default=None)
    bio: str | None = Field(default=None)
    experience_years: float = Field(default=0.0)
    target_titles_json: str = Field(default="[]")  # JSON list of strings
    target_locations_json: str = Field(default="[]")  # JSON list of strings
    target_salary_min: float | None = Field(default=None)
    work_preference: str = Field(default="remote_first")  # remote_first, hybrid, onsite, any
    skills_json: str = Field(default="[]")  # JSON list of extracted skills
    active_search_skills_json: str = Field(default="[]")  # Subset of skills used for scraping queries
    experience_history_json: str = Field(default="[]")  # JSON list of past roles dicts
    education_json: str = Field(default="[]")  # JSON list of education dicts
    projects_json: str = Field(default="[]")  # JSON list of project dicts with technologies and outcomes
    cv_raw_text: str | None = Field(default=None)
    linkedin_raw_text: str | None = Field(default=None)
    linkedin_url: str | None = Field(default=None)
    linkedin_session_cookie: str | None = Field(default=None)
    linkedin_data_json: str | None = Field(default=None)
    linkedin_access_token: str | None = Field(default=None)
    linkedin_user_id: str | None = Field(default=None)
    linkedin_email: str | None = Field(default=None)
    linkedin_picture_url: str | None = Field(default=None)
    updated_at: datetime = Field(default_factory=utc_now)


class UserSetting(SQLModel, table=True):
    """Account-owned setting, with sensitive values encrypted before storage."""

    __tablename__ = "user_settings"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    key: str = Field(index=True)
    value_json: str
    is_sensitive: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=utc_now)


class SearchConfig(SQLModel, table=True):
    """Configured search jobs for automated background scrapers."""

    __tablename__ = "search_configs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    source: str = Field(index=True)  # "linkedin", "stepstone", "google"
    keywords: str = Field(index=True)
    location: str = Field(index=True)
    interval_hours: int = Field(default=12)
    is_active: bool = Field(default=True, index=True)
    last_run_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)


class FeedbackNote(SQLModel, table=True):
    """User feedback note attached to a position for adaptive learning."""

    __tablename__ = "feedback_notes"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    sentiment: str = Field(default="neutral")  # "positive", "negative", "neutral"
    note_text: str
    created_at: datetime = Field(default_factory=utc_now)


class FilterRule(SQLModel, table=True):
    """Negative blacklist rule for filtering out jobs by title, keyword, or company."""

    __tablename__ = "filter_rules"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    rule_type: str = Field(index=True)  # "title", "keyword", "company"
    pattern: str = Field(index=True)  # e.g. "Senior", "PHP", "Director"
    is_regex: bool = Field(default=False)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)


class ApplicationMaterial(SQLModel, table=True):
    """Tailored application materials (cover letter or resume bullet points) for a specific job."""

    __tablename__ = "application_materials"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    material_type: str = Field(index=True)  # "cover_letter", "tailored_resume"
    tone: str = Field(default="professional")  # "professional", "enthusiastic", "direct", "conversational"
    content_markdown: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ScrapeTask(SQLModel, table=True):
    """Persistent task queue item for continuous background scraping and AI scoring."""

    __tablename__ = "scrape_tasks"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    task_type: str = Field(index=True)  # "scrape_query", "evaluate_job", "feedback_tune"
    payload_json: str = Field(default="{}")  # JSON payload with parameters
    status: str = Field(default="pending", index=True)  # "pending", "in_progress", "completed", "failed"
    retries: int = Field(default=0)
    max_retries: int = Field(default=3)
    error_message: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = Field(default=None)


class AppSettings(SQLModel, table=True):
    """Persistent, UI-editable configuration key-value storage."""

    __tablename__ = "app_settings"

    key: str = Field(primary_key=True, index=True)
    value_json: str  # JSON serialized value (string, int, bool, dict)
    description: str | None = Field(default=None)
    updated_at: datetime = Field(default_factory=utc_now)
