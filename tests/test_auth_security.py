"""Integration and unit test suite for user authentication, data isolation, and encryption."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.auth.security import (
    create_user_session,
    hash_password,
    revoke_session,
    validate_session_token,
    verify_password,
)
from app.db.database import engine, get_user_setting
from app.db.models import Job, User
from app.db.ownership import encrypt_profile, get_user_profile
from app.main import app
from app.security.encryption import EncryptionError, decrypt_text, encrypt_text


@pytest.fixture(name="test_session")
def session_fixture():
    """Create in-memory SQLite database session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_password_hashing():
    """Test password hashing and verification with scrypt."""
    password = "MySecurePassword123!"
    hashed = hash_password(password)
    
    assert hashed != password
    assert hashed.startswith("scrypt:")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_session_lifecycle(test_session: Session):
    """Test session token creation, validation, and revocation."""
    user = User(
        email="test@example.com",
        password_hash=hash_password("password123"),
        full_name="Test User",
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    session_obj = create_user_session(test_session, user.id)
    assert session_obj.session_token is not None

    validated_user = validate_session_token(test_session, session_obj.session_token)
    assert validated_user is not None
    assert validated_user.id == user.id

    revoke_session(test_session, session_obj.session_token)
    invalidated_user = validate_session_token(test_session, session_obj.session_token)
    assert invalidated_user is None


def test_encryption_decryption_roundtrip():
    """Test authenticated encryption and decryption of sensitive user data."""
    sensitive_cv = "Confidential resume data for Jane Doe, SSN: 123-45-6789"
    encrypted = encrypt_text(sensitive_cv, user_id=42)
    
    assert encrypted != sensitive_cv
    assert encrypted.startswith("enc:v2:")
    
    decrypted = decrypt_text(encrypted, user_id=42)
    assert decrypted == sensitive_cv

    with pytest.raises(EncryptionError):
        decrypt_text(encrypted, user_id=43)

    # Unencrypted string fallback
    plain = "Regular unencrypted text"
    assert decrypt_text(plain) == plain


def test_auth_api_endpoints():
    """Test API endpoints for register, login, logout, and me."""
    client = TestClient(app)

    # 1. Register
    reg_payload = {
        "email": "api_user@example.com",
        "password": "Password123",
        "full_name": "API User",
    }
    resp = client.post("/api/auth/register", json=reg_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "api_user@example.com"
    assert "jobot_session" in resp.cookies

    # 2. Get Me
    me_resp = client.get("/api/auth/me", cookies=resp.cookies)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "api_user@example.com"

    # 3. Logout
    logout_resp = client.post("/api/auth/logout", cookies=resp.cookies)
    assert logout_resp.status_code == 200

    # 4. Login
    login_payload = {
        "email": "api_user@example.com",
        "password": "Password123",
    }
    login_resp = client.post("/api/auth/login", json=login_payload)
    assert login_resp.status_code == 200
    assert "jobot_session" in login_resp.cookies


def test_user_data_isolation(test_session: Session):
    """Test data isolation between two distinct user accounts."""
    user1 = User(email="user1@example.com", password_hash=hash_password("pass1"), full_name="User One")
    user2 = User(email="user2@example.com", password_hash=hash_password("pass2"), full_name="User Two")
    test_session.add(user1)
    test_session.add(user2)
    test_session.commit()
    test_session.refresh(user1)
    test_session.refresh(user2)

    job1 = Job(user_id=user1.id, source="linkedin", title="Backend Engineer", company="Corp A", location="Remote", url="http://example.com/1", dedup_hash="hash1")
    job2 = Job(user_id=user2.id, source="stepstone", title="Frontend Engineer", company="Corp B", location="Berlin", url="http://example.com/2", dedup_hash="hash2")
    test_session.add(job1)
    test_session.add(job2)
    test_session.commit()

    user1_jobs = test_session.exec(select(Job).where(Job.user_id == user1.id)).all()
    user2_jobs = test_session.exec(select(Job).where(Job.user_id == user2.id)).all()

    assert len(user1_jobs) == 1
    assert user1_jobs[0].title == "Backend Engineer"

    assert len(user2_jobs) == 1
    assert user2_jobs[0].title == "Frontend Engineer"


def test_saved_credentials_are_not_reflected_into_html():
    """Keep account secrets encrypted at rest and absent from rendered forms."""
    api_key = "sk-private-phase15-key"
    linkedin_cookie = "private-linkedin-session-cookie"

    with TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={
                "email": "secrets@example.com",
                "password": "SecurePassword123",
                "full_name": "Secret Owner",
            },
        )
        assert register_response.status_code == 200
        user_id = register_response.json()["id"]

        save_response = client.post(
            "/api/settings/ai",
            data={
                "ai_provider": "openai",
                "openai_model": "gpt-4o-mini",
                "openai_api_key": api_key,
            },
        )
        assert save_response.status_code == 200

        with Session(engine) as session:
            profile = get_user_profile(session, user_id, decrypt=True)
            assert profile is not None
            profile.linkedin_session_cookie = linkedin_cookie
            encrypt_profile(profile, user_id)
            session.add(profile)
            session.commit()

        settings_response = client.get("/web/views/settings")
        profile_response = client.get("/web/views/profile")
        assert settings_response.status_code == 200
        assert profile_response.status_code == 200
        assert api_key not in settings_response.text
        assert linkedin_cookie not in profile_response.text

        blank_save_response = client.post(
            "/api/settings/ai",
            data={
                "ai_provider": "openai",
                "openai_model": "gpt-4o-mini",
                "openai_api_key": "",
            },
        )
        assert blank_save_response.status_code == 200

        with Session(engine) as session:
            assert get_user_setting(session, user_id, "openai_api_key") == api_key
