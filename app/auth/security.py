"""Authentication, password hashing, and session security primitives."""

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from sqlmodel import Session, select

from app.db.models import User, UserSession, utc_now

logger = logging.getLogger("jobot.auth")

SESSION_DURATION_DAYS = 7


def hash_password(password: str) -> str:
    """Hash password using hashlib.scrypt with random salt."""
    salt = secrets.token_hex(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=16384,
        r=8,
        p=1,
    )
    return f"scrypt:{salt}:{derived.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against scrypt hash."""
    if not password_hash or not password_hash.startswith("scrypt:"):
        return False
    parts = password_hash.split(":")
    if len(parts) != 3:
        return False
    _, salt, expected_hex = parts
    try:
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            n=16384,
            r=8,
            p=1,
        )
        return hmac.compare_digest(derived.hex(), expected_hex)
    except Exception as e:
        logger.error("Error verifying password hash: %s", e)
        return False


def create_user_session(db: Session, user_id: int) -> UserSession:
    """Create a new session token for the user."""
    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(days=SESSION_DURATION_DAYS)
    session_obj = UserSession(
        user_id=user_id,
        session_token=token,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return session_obj


def validate_session_token(db: Session, session_token: str) -> User | None:
    """Validate session token and return the associated active User if valid."""
    if not session_token:
        return None

    statement = select(UserSession).where(
        UserSession.session_token == session_token,
        UserSession.revoked == False,
    )
    session_obj = db.exec(statement).first()
    if not session_obj:
        return None

    # Check expiration
    now = utc_now()
    expires_at = session_obj.expires_at
    if expires_at.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    elif expires_at.tzinfo is not None and now.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=None)

    if expires_at < now:
        session_obj.revoked = True
        db.add(session_obj)
        db.commit()
        return None

    user = db.get(User, session_obj.user_id)
    if not user or not user.is_active:
        return None

    return user


def revoke_session(db: Session, session_token: str) -> None:
    """Revoke a session token."""
    statement = select(UserSession).where(UserSession.session_token == session_token)
    session_obj = db.exec(statement).first()
    if session_obj:
        session_obj.revoked = True
        db.add(session_obj)
        db.commit()
