"""Tests for base web router and settings API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.database import engine, get_user_setting, init_db
from app.db.models import FilterRule
from app.main import app


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def test_index_page_rendering() -> None:
    """Verify GET / returns 200 OK HTML containing Jobot shell."""
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Jobot" in resp.text
        assert "view-container" in resp.text


def test_settings_api_routes(authenticated_client: TestClient, authenticated_user: dict) -> None:
    """Verify settings REST API endpoints."""
    client = authenticated_client
    resp_get = client.get("/api/settings")
    assert resp_get.status_code == 200
    assert "ai_provider" in resp_get.json()

    resp_post = client.post(
        "/api/settings/ai",
        data={
            "ai_provider": "openai",
            "openai_model": "gpt-4o",
            "openai_api_key": "sk-test-secret",
        },
    )
    assert resp_post.status_code == 200
    with Session(engine) as session:
        assert get_user_setting(session, authenticated_user["id"], "ai_provider") == "openai"

    resp_rule = client.post(
        "/api/settings/rules",
        data={"rule_type": "title", "pattern": "Executive Vice President"},
    )
    assert resp_rule.status_code == 200

    with Session(engine) as session:
        rule = session.exec(
            select(FilterRule).where(
                FilterRule.pattern == "Executive Vice President",
                FilterRule.user_id == authenticated_user["id"],
            )
        ).first()
        assert rule is not None
        rule_id = rule.id

    resp_del = client.delete(f"/api/settings/rules/{rule_id}")
    assert resp_del.status_code == 200

    resp_models = client.get("/api/settings/ollama/models?ollama_base_url=http://127.0.0.1:11434")
    assert resp_models.status_code == 200
    assert "ollama_model" in resp_models.text

    resp_weights = client.post(
        "/api/settings/scoring-weights",
        data={
            "weight_skills": "80",
            "weight_title": "10",
            "weight_location": "5",
            "weight_experience": "5",
            "weight_vector": "15",
        },
    )
    assert resp_weights.status_code == 200
    assert "Scoring Weights Saved" in resp_weights.text
    with Session(engine) as session:
        assert get_user_setting(session, authenticated_user["id"], "weight_skills") == 80.0


def test_tailscale_settings_render_and_persist(
    authenticated_client: TestClient,
    authenticated_user: dict,
) -> None:
    """Render and save the safe Tailscale SSH connection preferences."""
    client = authenticated_client
    settings_view = client.get("/web/views/settings")
    assert settings_view.status_code == 200
    assert "Tailscale SSH Remote Access" in settings_view.text
    assert "/api/settings/tailscale/status" in settings_view.text

    response = client.post(
        "/api/settings/remote-access",
        data={
            "tailscale_enabled": "true",
            "tailscale_hostname": "jobot-host.example.ts.net",
            "tailscale_ssh_user": "jobot-user",
            "tailscale_ssh_port": "22",
            "tailscale_app_port": "8000",
            "tailscale_magic_dns": "true",
        },
    )

    assert response.status_code == 200
    assert "settings saved" in response.text
    with Session(engine) as session:
        user_id = authenticated_user["id"]
        assert get_user_setting(session, user_id, "tailscale_enabled") is True
        assert get_user_setting(session, user_id, "tailscale_hostname") == "jobot-host.example.ts.net"
        assert get_user_setting(session, user_id, "tailscale_ssh_user") == "jobot-user"


def test_tailscale_settings_reject_unsafe_host(authenticated_client: TestClient) -> None:
    """Reject host input that could turn copied SSH guidance into a shell payload."""
    response = authenticated_client.post(
        "/api/settings/remote-access",
        data={
            "tailscale_hostname": "host; shutdown",
            "tailscale_ssh_user": "jobot-user",
            "tailscale_ssh_port": "22",
            "tailscale_app_port": "8000",
        },
    )

    assert response.status_code == 422


def test_tailscale_status_when_client_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
    authenticated_client: TestClient,
) -> None:
    """Status endpoint remains responsive when the Tailscale CLI is unavailable."""
    monkeypatch.setattr("app.api.settings.shutil.which", lambda command: None)

    response = authenticated_client.get("/api/settings/tailscale/status")

    assert response.status_code == 200
    assert "Not installed" in response.text
