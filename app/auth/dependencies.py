"""FastAPI dependency providers for authentication and current user context."""

import logging

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session

from app.auth.security import validate_session_token
from app.db.database import get_session
from app.db.models import User

logger = logging.getLogger("jobot.auth")

COOKIE_NAME = "jobot_session"


def get_token_from_request(request: Request) -> str | None:
    """Extract session token from cookie or Authorization header."""
    # Check cookie
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token

    # Check Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    return None


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_session),
) -> User | None:
    """Get the currently authenticated user if session token is valid, else None."""
    token = get_token_from_request(request)
    if token:
        user = validate_session_token(db, token)
        if user:
            return user
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_session),
) -> User:
    """Get the currently authenticated user or raise HTTP 401 Unauthorized."""
    user = get_optional_current_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
