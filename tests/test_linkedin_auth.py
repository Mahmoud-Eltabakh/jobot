"""Unit and integration tests for LinkedIn Authentication and Session Management."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.ai.client import MockAIClient
from app.ai.linkedin_analyzer import LinkedInProfileAnalyzer
from app.db.database import engine, init_db
from app.db.models import UserProfile
from app.main import app
from app.scrapers.linkedin_auth import LinkedInAuthManager


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


@pytest.mark.asyncio
async def test_linkedin_auth_manager_validation():
    """Verify LinkedInAuthManager handles invalid credentials and cookies cleanly."""
    # Empty credentials test
    res = await LinkedInAuthManager.login_and_capture_session(email="", password="")
    assert res["success"] is False
    assert "required" in res["error"]

    # Cookie validation with bad cookie
    valid = await LinkedInAuthManager.validate_session_cookie("short_invalid_cookie")
    assert valid is False


def test_linkedin_sync_api_endpoint():
    """Test POST /api/profile/linkedin/sync endpoint with li_at cookie and raw text."""
    with TestClient(app) as client:
        # 1. Missing URL
        resp_bad = client.post("/api/profile/linkedin/sync", json={"linkedin_url": ""})
        assert resp_bad.status_code == 400

        # 2. Sync with li_at cookie payload structure
        sync_resp = client.post(
            "/api/profile/linkedin/sync",
            json={
                "linkedin_url": "https://www.linkedin.com/in/testuser",
                "session_cookie": "sample_li_at_cookie_val",
                "raw_text_override": "Jane Engineer\nSenior Python Engineer\nSkills: Python, FastAPI, Docker",
            },
        )
        assert sync_resp.status_code == 200
        data = sync_resp.json()
        assert data["status"] == "ok"
        assert "Jane Engineer" in data["full_name"]


def test_profile_tab_linkedin_cookie_form():
    """Test Profile web view renders LinkedIn li_at cookie authentication fields."""
    with TestClient(app) as client:
        resp = client.get("/web/views/profile")
        assert resp.status_code == 200
        assert "li_at" in resp.text
        assert "LinkedIn Profile URL" in resp.text
