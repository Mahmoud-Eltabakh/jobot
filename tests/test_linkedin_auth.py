"""Unit and integration tests for LinkedIn Authentication and Session Management."""

import pytest
from fastapi.testclient import TestClient

from app.db.database import init_db
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


def test_linkedin_sync_api_endpoint(authenticated_client: TestClient):
    """Test POST /api/profile/linkedin/sync endpoint with li_at cookie and raw text."""
    # Missing URL still exercises authenticated request validation.
    resp_bad = authenticated_client.post("/api/profile/linkedin/sync", json={"linkedin_url": ""})
    assert resp_bad.status_code == 400

    sync_resp = authenticated_client.post(
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


def test_profile_tab_linkedin_cookie_form(authenticated_client: TestClient):
    """Test Profile web view renders LinkedIn li_at cookie authentication fields."""
    resp = authenticated_client.get("/web/views/profile")
    assert resp.status_code == 200
    assert "li_at" in resp.text
    assert "LinkedIn Profile URL" in resp.text
