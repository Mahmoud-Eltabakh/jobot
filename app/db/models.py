"""SQLModel database models for Jobot."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return current UTC datetime with timezone awareness."""
    return datetime.now(timezone.utc)


class JobStatus(str, Enum):
    """Lifecycle status stages for job applications."""

    SEEN = "seen"
    APPLIED = "applied"
    WAITING = "waiting for respond"
    INTERVIEW_1 = "1. interview"
    INTERVIEW_2 = "2. interview"
    INTERVIEW_3 = "3. interview"
    NOT_A_FIT = "not a good fit"
    REJECTED = "rejected"


class Job(SQLModel, table=True):
    """Job listing scraped from job boards or added manually."""

    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)  # e.g. "linkedin", "stepstone", "google"
    source_id: Optional[str] = Field(default=None, index=True)
    title: str = Field(index=True)
    company: str = Field(index=True)
    location: str = Field(index=True)
    is_remote: bool = Field(default=False, index=True)

    # Compensation
    salary_min: Optional[float] = Field(default=None)
    salary_max: Optional[float] = Field(default=None)
    salary_currency: Optional[str] = Field(default=None)

    # Link & Content
    url: str = Field(index=True)
    description: str = Field(default="")

    # AI Evaluation & Fit Score (0-100)
    fit_score: Optional[int] = Field(default=None, index=True)
    fit_summary: Optional[str] = Field(default=None)
    pros_json: Optional[str] = Field(default=None)  # JSON serialized list of strengths
    cons_json: Optional[str] = Field(default=None)  # JSON serialized list of concerns
    missing_skills_json: Optional[str] = Field(default=None)  # JSON list of missing skills

    # Status & Deduplication
    status: str = Field(default=JobStatus.SEEN.value, index=True)
    dedup_hash: str = Field(unique=True, index=True)  # SHA-256 of normalized company+title+location

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class JobStatusHistory(SQLModel, table=True):
    """Audit log of status transitions and candidate comments for a job."""

    __tablename__ = "job_status_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    old_status: Optional[str] = Field(default=None)
    new_status: str = Field(index=True)
    notes: Optional[str] = Field(default=None)
    changed_at: datetime = Field(default_factory=utc_now)


class UserProfile(SQLModel, table=True):
    """Candidate profile, target preferences, and parsed CV data."""

    __tablename__ = "user_profiles"

    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(default="")
    headline: Optional[str] = Field(default=None)
    bio: Optional[str] = Field(default=None)
    experience_years: float = Field(default=0.0)
    target_titles_json: str = Field(default="[]")  # JSON list of strings
    target_locations_json: str = Field(default="[]")  # JSON list of strings
    target_salary_min: Optional[float] = Field(default=None)
    work_preference: str = Field(default="remote_first")  # remote_first, hybrid, onsite, any
    skills_json: str = Field(default="[]")  # JSON list of extracted skills
    active_search_skills_json: str = Field(default="[]")  # Subset of skills used for scraping queries
    experience_history_json: str = Field(default="[]")  # JSON list of past roles dicts
    education_json: str = Field(default="[]")  # JSON list of education dicts
    cv_raw_text: Optional[str] = Field(default=None)
    linkedin_url: Optional[str] = Field(default=None)
    linkedin_session_cookie: Optional[str] = Field(default=None)
    linkedin_data_json: Optional[str] = Field(default=None)
    linkedin_access_token: Optional[str] = Field(default=None)
    linkedin_user_id: Optional[str] = Field(default=None)
    linkedin_email: Optional[str] = Field(default=None)
    linkedin_picture_url: Optional[str] = Field(default=None)
    updated_at: datetime = Field(default_factory=utc_now)


class SearchConfig(SQLModel, table=True):
    """Configured search jobs for automated background scrapers."""

    __tablename__ = "search_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)  # "linkedin", "stepstone", "google"
    keywords: str = Field(index=True)
    location: str = Field(index=True)
    interval_hours: int = Field(default=12)
    is_active: bool = Field(default=True, index=True)
    last_run_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)


class FeedbackNote(SQLModel, table=True):
    """User feedback note attached to a position for adaptive learning."""

    __tablename__ = "feedback_notes"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    sentiment: str = Field(default="neutral")  # "positive", "negative", "neutral"
    note_text: str
    created_at: datetime = Field(default_factory=utc_now)


class FilterRule(SQLModel, table=True):
    """Negative blacklist rule for filtering out jobs by title, keyword, or company."""

    __tablename__ = "filter_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    rule_type: str = Field(index=True)  # "title", "keyword", "company"
    pattern: str = Field(index=True)  # e.g. "Senior", "PHP", "Director"
    is_regex: bool = Field(default=False)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)


class ApplicationMaterial(SQLModel, table=True):
    """Tailored application materials (cover letter or resume bullet points) for a specific job."""

    __tablename__ = "application_materials"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    material_type: str = Field(index=True)  # "cover_letter", "tailored_resume"
    tone: str = Field(default="professional")  # "professional", "enthusiastic", "direct", "conversational"
    content_markdown: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ScrapeTask(SQLModel, table=True):
    """Persistent task queue item for continuous background scraping and AI scoring."""

    __tablename__ = "scrape_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_type: str = Field(index=True)  # "scrape_query", "evaluate_job", "feedback_tune"
    payload_json: str = Field(default="{}")  # JSON payload with parameters
    status: str = Field(default="pending", index=True)  # "pending", "in_progress", "completed", "failed"
    retries: int = Field(default=0)
    max_retries: int = Field(default=3)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = Field(default=None)


class AppSettings(SQLModel, table=True):
    """Persistent, UI-editable configuration key-value storage."""

    __tablename__ = "app_settings"

    key: str = Field(primary_key=True, index=True)
    value_json: str  # JSON serialized value (string, int, bool, dict)
    description: Optional[str] = Field(default=None)
    updated_at: datetime = Field(default_factory=utc_now)
