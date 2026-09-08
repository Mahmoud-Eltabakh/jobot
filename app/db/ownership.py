"""Account ownership and encrypted profile persistence boundaries."""

from typing import TypeVar

from sqlmodel import Session, SQLModel, select

from app.db.models import (
    ApplicationMaterial,
    FeedbackNote,
    FilterRule,
    Job,
    ScrapeTask,
    SearchConfig,
    User,
    UserProfile,
)
from app.security.encryption import decrypt_text, encrypt_text, rotate_text

OwnedModel = TypeVar("OwnedModel", bound=SQLModel)

# These fields contain direct personal data or credentials. Structured search
# preferences remain readable for indexed filtering and are protected by DB access.
SENSITIVE_PROFILE_FIELDS = (
    "bio",
    "experience_history_json",
    "education_json",
    "projects_json",
    "cv_raw_text",
    "linkedin_raw_text",
    "linkedin_session_cookie",
    "linkedin_data_json",
    "linkedin_access_token",
    "linkedin_email",
)


def owned_by_id(session: Session, model: type[OwnedModel], record_id: int, user_id: int | None) -> OwnedModel | None:
    """Fetch a user-owned record without revealing whether another owner has it."""
    if user_id is None:
        raise PermissionError("Authenticated user has no persistent identity")
    return session.exec(
        select(model).where(model.id == record_id, model.user_id == user_id)
    ).first()


def get_user_profile(session: Session, user_id: int | None, *, decrypt: bool = False) -> UserProfile | None:
    """Fetch the authenticated account's profile and optionally unlock sensitive fields."""
    if user_id is None:
        raise PermissionError("Authenticated user has no persistent identity")
    profile = session.exec(select(UserProfile).where(UserProfile.user_id == user_id)).first()
    if profile and decrypt:
        decrypt_profile(profile, user_id)
    return profile


def encrypt_profile(profile: UserProfile, user_id: int | None) -> UserProfile:
    """Encrypt every populated sensitive field before a profile is flushed."""
    if user_id is None:
        raise PermissionError("Authenticated user has no persistent identity")
    if profile.user_id not in (None, user_id):
        raise PermissionError("Profile belongs to another account")
    profile.user_id = user_id
    for field_name in SENSITIVE_PROFILE_FIELDS:
        value = getattr(profile, field_name)
        setattr(profile, field_name, encrypt_text(value, user_id=user_id))
    return profile


def decrypt_profile(profile: UserProfile, user_id: int | None) -> UserProfile:
    """Decrypt sensitive fields only after an exact ownership check."""
    if user_id is None:
        raise PermissionError("Authenticated user has no persistent identity")
    if profile.user_id != user_id:
        raise PermissionError("Profile belongs to another account")
    for field_name in SENSITIVE_PROFILE_FIELDS:
        value = getattr(profile, field_name)
        setattr(profile, field_name, decrypt_text(value, user_id=user_id))
    return profile


def migrate_legacy_user_data(session: Session) -> int | None:
    """Claim legacy unowned rows only when one unambiguous account exists.

    This migration is intentionally idempotent. Databases with zero or multiple
    accounts retain unowned rows for explicit operator recovery rather than risk
    exposing one person's historical data to another account.
    """
    users = session.exec(select(User)).all()
    if len(users) != 1 or users[0].id is None:
        return None
    user_id = users[0].id
    for model in (Job, UserProfile, SearchConfig, FeedbackNote, FilterRule, ApplicationMaterial, ScrapeTask):
        for record in session.exec(select(model).where(model.user_id == None)).all():
            record.user_id = user_id
            if isinstance(record, UserProfile):
                for field_name in SENSITIVE_PROFILE_FIELDS:
                    value = getattr(record, field_name)
                    setattr(record, field_name, rotate_text(value, user_id=user_id))
            session.add(record)
    session.commit()
    return user_id