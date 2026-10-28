"""Unit and integration tests for LinkedIn Authentication and Session Management."""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.ai.client import OllamaAIClient
from app.db.database import init_db
from app.db.vector import VectorStore
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


def test_linkedin_sync_api_endpoint(authenticated_client: TestClient, monkeypatch, tmp_path):
    """Test POST /api/profile/linkedin/sync endpoint with li_at cookie and raw text."""
    monkeypatch.setattr(OllamaAIClient, "generate", AsyncMock(return_value=json.dumps({
        "full_name": "Jane Engineer",
        "headline": "Senior Python Engineer",
        "summary": "Senior Python engineer experienced in FastAPI and Docker backend development.",
        "skills": ["Python", "FastAPI", "Docker"],
    })))
    monkeypatch.setattr(OllamaAIClient, "embed", AsyncMock(return_value=[1.0, 0.0]))
    vector_store = VectorStore(persist_dir=str(tmp_path / "linkedin-vectors"))
    monkeypatch.setattr("app.ai.linkedin_analyzer.get_vector_store", lambda: vector_store)
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


# ---- Phase 11 gap closure: login route, status badge, stored-cookie reuse ----

from sqlmodel import Session

from app.ai.embeddings import ProfileEmbedder
from app.ai.linkedin_analyzer import LinkedInProfileAnalyzer
from app.ai.profile_extractor import ExtractedProfile
from app.db.database import engine
from app.db.models import UserProfile
from app.db.ownership import get_user_profile
from sqlmodel import select

LI_AT = "AQEDAR-test-li-at-cookie-value-0123456789"
PASSWORD = "Sup3rS3cretPw!"


def fake_playwright(monkeypatch, url: str, cookies=(), visible: bool = True):
    """Replace Playwright in linkedin_auth with an offline double ending on `url`."""

    class Page:
        def __init__(self):
            self.url = url

        async def goto(self, *a, **k):
            return None

        async def wait_for_timeout(self, *a):
            return None

        async def is_visible(self, *a, **k):
            return visible

        async def fill(self, *a):
            return None

        async def click(self, *a):
            return None

    class Context:
        async def new_page(self):
            return Page()

        async def cookies(self):
            return list(cookies)

        async def add_cookies(self, *a):
            return None

    class Browser:
        async def new_context(self, **k):
            return Context()

        async def close(self):
            return None

    class PW:
        class chromium:
            @staticmethod
            async def launch(**k):
                return Browser()

    class CM:
        async def __aenter__(self):
            return PW()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr("app.scrapers.linkedin_auth.async_playwright", lambda: CM())


def login(client: TestClient):
    return client.post(
        "/web/profile/linkedin/login",
        data={"linkedin_email": "me@example.com", "linkedin_password": PASSWORD},
    )


def stored_profile(user_id: int, decrypt: bool = False) -> UserProfile:
    with Session(engine) as s:
        p = get_user_profile(s, user_id, decrypt=decrypt)
        s.expunge(p)
        return p


def test_login_success_stores_only_encrypted_cookie(authenticated_client, authenticated_user, monkeypatch):
    fake_playwright(monkeypatch, "https://www.linkedin.com/feed/", [{"name": "li_at", "value": LI_AT}])
    resp = login(authenticated_client)
    assert resp.status_code == 200
    assert "Logged in to LinkedIn" in resp.text
    assert LI_AT not in resp.text and PASSWORD not in resp.text

    raw = stored_profile(authenticated_user["id"])
    assert raw.linkedin_session_cookie and LI_AT not in raw.linkedin_session_cookie
    assert stored_profile(authenticated_user["id"], decrypt=True).linkedin_session_cookie == LI_AT
    assert all(PASSWORD not in str(v) for v in raw.model_dump().values())
    assert "Session stored" in authenticated_client.get("/web/views/profile").text


def test_login_failure_without_cookie(authenticated_client, authenticated_user, monkeypatch):
    fake_playwright(monkeypatch, "https://www.linkedin.com/login", [])
    resp = login(authenticated_client)
    assert "Could not capture li_at" in resp.text
    profile = stored_profile(authenticated_user["id"])
    assert not (profile and profile.linkedin_session_cookie)


def test_login_requires_2fa_challenge(authenticated_client, authenticated_user, monkeypatch):
    fake_playwright(monkeypatch, "https://www.linkedin.com/checkpoint/challenge/abc", [{"name": "li_at", "value": LI_AT}])
    resp = login(authenticated_client)
    assert "2FA" in resp.text and LI_AT not in resp.text
    profile = stored_profile(authenticated_user["id"])
    assert not (profile and profile.linkedin_session_cookie)


def test_login_blank_credentials_rejected(authenticated_client):
    resp = authenticated_client.post("/web/profile/linkedin/login", data={"linkedin_email": "", "linkedin_password": ""})
    assert "required" in resp.text


def test_session_status_states(authenticated_client, authenticated_user, monkeypatch):
    assert "Needs login" in authenticated_client.get("/web/profile/linkedin/status").text

    fake_playwright(monkeypatch, "https://www.linkedin.com/feed/", [{"name": "li_at", "value": LI_AT}])
    login(authenticated_client)
    assert "Logged In (Active)" in authenticated_client.get("/web/profile/linkedin/status").text

    fake_playwright(monkeypatch, "https://www.linkedin.com/login?session_redirect=feed")
    expired = authenticated_client.get("/web/profile/linkedin/status").text
    assert "Expired" in expired and LI_AT not in expired


def test_sync_reuses_stored_encrypted_cookie(authenticated_client, authenticated_user, monkeypatch):
    fake_playwright(monkeypatch, "https://www.linkedin.com/feed/", [{"name": "li_at", "value": LI_AT}])
    login(authenticated_client)

    seen = []

    def voyager(linkedin_url, session_cookie):
        seen.append(session_cookie)
        return ExtractedProfile(full_name="Reuse User", headline="Engineer", summary="s" * 40, skills=["Python"])

    monkeypatch.setattr(LinkedInProfileAnalyzer, "fetch_profile_via_linkedin_api", voyager)
    monkeypatch.setattr(ProfileEmbedder, "embed_and_store_profile", AsyncMock(return_value=1))
    resp = authenticated_client.post(
        "/web/profile/linkedin/sync", data={"linkedin_url": "https://www.linkedin.com/in/reuse"},
    )
    assert resp.status_code == 200
    assert seen == [LI_AT]
    assert LI_AT not in resp.text
    assert LI_AT not in stored_profile(authenticated_user["id"]).linkedin_session_cookie
    assert stored_profile(authenticated_user["id"], decrypt=True).linkedin_session_cookie == LI_AT


def test_sync_without_any_cookie_reports_guidance(authenticated_client, monkeypatch):
    monkeypatch.setattr(ProfileEmbedder, "embed_and_store_profile", AsyncMock(return_value=1))
    resp = authenticated_client.post(
        "/web/profile/linkedin/sync", data={"linkedin_url": "https://www.linkedin.com/in/nocookie"},
    )
    assert "li_at" in resp.text and "required" in resp.text
