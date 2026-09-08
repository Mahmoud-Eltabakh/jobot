"""Tests for base web router and settings API endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.database import engine, init_db, get_app_setting
from app.db.models import FilterRule, UserProfile
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


def test_settings_api_routes() -> None:
    """Verify settings REST API endpoints."""
    with TestClient(app) as client:
        # Get settings
        resp_get = client.get("/api/settings")
        assert resp_get.status_code == 200
        data = resp_get.json()
        assert "ai_provider" in data

        # Update AI settings
        resp_post = client.post(
            "/api/settings/ai",
            data={
                "ai_provider": "openai",
                "openai_model": "gpt-4o",
                "openai_api_key": "sk-test-secret",
            },
        )
        assert resp_post.status_code == 200
        assert get_app_setting("ai_provider") == "openai"

        # Create filter rule
        resp_rule = client.post(
            "/api/settings/rules",
            data={"rule_type": "title", "pattern": "Executive Vice President"},
        )
        assert resp_rule.status_code == 200

        with Session(engine) as session:
            rule = session.exec(select(FilterRule).where(FilterRule.pattern == "Executive Vice President")).first()
            assert rule is not None
            rule_id = rule.id

        # Delete rule
        resp_del = client.delete(f"/api/settings/rules/{rule_id}")
        assert resp_del.status_code == 200

        # Fetch Ollama models endpoint
        resp_models = client.get("/api/settings/ollama/models?ollama_base_url=http://127.0.0.1:11434")
        assert resp_models.status_code == 200
        assert "ollama_model" in resp_models.text

        # Update scoring weights endpoint
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
        assert get_app_setting("weight_skills") == 80.0
