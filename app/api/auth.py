"""Authentication REST API routes for user registration, login, logout, and current user info."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from app.auth.dependencies import COOKIE_NAME, get_current_user
from app.auth.security import create_user_session, hash_password, revoke_session, verify_password
from app.core.config import get_settings
from app.db.database import get_session
from app.db.models import User, UserProfile
from app.db.ownership import get_user_profile, migrate_legacy_user_data

logger = logging.getLogger("jobot.auth.api")

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool


@router.post("/register", response_model=UserResponse)
def register(
    req: RegisterRequest,
    response: Response,
    db: Session = Depends(get_session),
):
    """Register a new user account."""
    email = req.email.strip().lower()
    if len(req.password) < 10:
        raise HTTPException(status_code=400, detail="Password must be at least 10 characters")

    existing = db.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    user = User(
        email=email,
        password_hash=hash_password(req.password),
        full_name=req.full_name or "",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # A first account can safely adopt legacy single-user data; later accounts cannot.
    migrate_legacy_user_data(db)
    profile = get_user_profile(db, user.id)
    if not profile:
        profile = UserProfile(user_id=user.id, full_name=user.full_name or "Candidate")
        db.add(profile)
        db.commit()

    # Create session
    session_obj = create_user_session(db, user.id)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_obj.session_token,
        httponly=True,
        samesite="lax",
        secure=get_settings().env.lower() in {"production", "prod"},
        path="/",
        max_age=7 * 24 * 3600,
    )

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
    )


@router.post("/login", response_model=UserResponse)
def login(
    req: LoginRequest,
    response: Response,
    db: Session = Depends(get_session),
):
    """Authenticate user and issue session token."""
    email = req.email.strip().lower()
    user = db.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    session_obj = create_user_session(db, user.id)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_obj.session_token,
        httponly=True,
        samesite="lax",
        secure=get_settings().env.lower() in {"production", "prod"},
        path="/",
        max_age=7 * 24 * 3600,
    )

    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
    )


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_session),
):
    """Revoke active session token and clear authentication cookie."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        revoke_session(db, token)
    response.delete_cookie(key=COOKIE_NAME)
    return {"status": "ok", "message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return currently authenticated user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
    )
