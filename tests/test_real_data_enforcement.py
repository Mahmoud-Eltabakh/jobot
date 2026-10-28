"""Phase 12 gap closure: no fabricated data, actionable alerts, diagnostics endpoint."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.ai.client import MockAIClient
from app.db.database import engine
from app.db.models import ScrapeTask, User
from app.scrapers.ai_extractor import AIScraperExtractor
from app.scrapers.stepstone import StepStoneScraper


def _other_user() -> int:
    with Session(engine) as session:
        user = User(email="other-real-data@example.com", password_hash="x")
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id

LISTING_LIKE_TEXT = (
    "<html><body><section><h1>Cloud Engineer</h1><h3>Some Corp</h3>"
    "<p>Requirements: experience with Python. Salary 80.000 - 95.000 EUR, full-time developer role. "
    + "More text. " * 30 + "</p></section></body></html>"
)


def test_stepstone_never_fabricates_job_from_page_text() -> None:
    assert StepStoneScraper.parse_cards_from_html(LISTING_LIKE_TEXT, search_term="Python") == []


def test_extractor_has_no_heuristic_fallback_or_placeholder_url() -> None:
    assert not hasattr(AIScraperExtractor, "_fallback_heuristic_extractor")
    import inspect
    assert "example.com/job" not in inspect.getsource(AIScraperExtractor)


@pytest.mark.asyncio
async def test_extractor_keeps_empty_url_instead_of_placeholder() -> None:
    client = MockAIClient(default_response=json.dumps({"title": "Engineer", "company": "Acme", "description": "d"}))
    job = await AIScraperExtractor.extract_from_html("Engineer at Acme", ai_client=client)
    assert job is not None and job.url == ""


def _failed_task(user_id: int, message: str, task_type: str = "scrape_query") -> None:
    with Session(engine) as session:
        session.add(ScrapeTask(user_id=user_id, task_type=task_type, status="failed", error_message=message))
        session.commit()


def test_system_alerts_empty_without_problems(authenticated_client: TestClient) -> None:
    resp = authenticated_client.get("/web/components/system-alerts")
    assert resp.status_code == 200
    assert "data-alert" not in resp.text


def test_system_alerts_show_actionable_provider_linkedin_and_rate_limit_errors(
    authenticated_client: TestClient, authenticated_user: dict,
) -> None:
    uid = authenticated_user["id"]
    _failed_task(uid, "unavailable: Provider is unavailable.", "evaluate_job")
    _failed_task(uid, "LinkedIn session cookie invalid (authwall)")
    _failed_task(uid, "rate_limit: Provider rate limit reached.")
    # Another account's failure must not leak.
    _failed_task(_other_user(), "unavailable: Provider is unavailable. SECRET-OTHER-USER")

    text = authenticated_client.get("/web/components/system-alerts").text
    assert 'data-alert="provider_unavailable"' in text
    assert 'data-alert="linkedin_login"' in text
    assert 'data-alert="rate_limit"' in text
    assert "/web/views/settings" in text and "/web/views/profile" in text
    assert "SECRET-OTHER-USER" not in text


def test_base_template_polls_system_alerts(authenticated_client: TestClient) -> None:
    page = authenticated_client.get("/").text
    assert 'hx-get="/web/components/system-alerts"' in page and "every 15s" in page


def test_diagnostics_requires_auth_and_exposes_no_secrets(
    client: TestClient, authenticated_client: TestClient, authenticated_user: dict,
) -> None:
    assert client.get("/api/diagnostics/health").status_code in (401, 403)

    _failed_task(authenticated_user["id"], "authentication: Provider authentication failed.")
    resp = authenticated_client.get("/api/diagnostics/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == {"ok": True}
    assert body["checks"]["queue"]["failed"] == 1
    assert body["checks"]["ai"]["reachability"] == "not_probed"
    assert any(a["code"] == "provider_credentials" for a in body["alerts"])
    dumped = resp.text.lower()
    for secret_word in ("api_key", "cookie", "password", "http://", "https://"):
        assert secret_word not in dumped
