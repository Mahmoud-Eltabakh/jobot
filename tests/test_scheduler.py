"""Tests for ScraperPipeline orchestrator, JobotScheduler, and REST API endpoints."""

from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.ai.client import MockAIClient
from app.db.database import engine, init_db
from app.db.models import FilterRule, Job, SearchConfig, UserProfile
from app.main import app
from app.scrapers.base import ScrapedJob
from app.scrapers.scheduler import ScraperPipeline


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


@pytest.mark.asyncio
async def test_scraper_pipeline_full_run() -> None:
    """Test ScraperPipeline coordinates scraping, deduplication, filtering, and AI scoring."""
    mock_jobs = [
        ScrapedJob(
            source="linkedin",
            title="Senior Python Developer",
            company="AlphaCorp",
            location="Berlin",
            url="https://linkedin.com/jobs/view/777",
            description="FastAPI, Python, and Docker.",
        ),
        ScrapedJob(
            source="stepstone",
            title="Intern Python Helper",
            company="BetaCorp",
            location="Munich",
            url="https://stepstone.de/jobs/888",
            description="Internship role.",
        ),
    ]

    mock_ai = MockAIClient()

    with Session(engine) as session:
        # Add a filter rule to catch the intern job
        rule = FilterRule(rule_type="title", pattern="Intern", is_active=True)
        session.add(rule)
        session.commit()

    with (
        patch("app.scrapers.jobspy_scraper.JobSpyScraper.scrape", new_callable=AsyncMock) as mock_js,
        patch("app.scrapers.stepstone.StepStoneScraper.scrape", new_callable=AsyncMock) as mock_ss,
    ):
        mock_js.return_value = [mock_jobs[0]]
        mock_ss.return_value = [mock_jobs[1]]

        with Session(engine) as session:
            stats = await ScraperPipeline.run_full_pipeline(
                session=session,
                ai_client=mock_ai,
                override_keywords="Python",
                override_location="Germany",
            )

            assert stats["scraped_total"] == 2
            assert stats["new_inserted"] == 2
            assert stats["filtered_out"] == 1
            assert stats["ai_evaluated"] == 1


def test_scraper_api_endpoints() -> None:
    """Test REST API trigger and status endpoints."""
    with patch("app.scrapers.scheduler.ScraperPipeline.run_full_pipeline", new_callable=AsyncMock):
        with TestClient(app) as client:
            # Status endpoint
            resp_status = client.get("/api/scrapers/status")
            assert resp_status.status_code == 200
            data_status = resp_status.json()
            assert "is_running" in data_status
            assert "active_configs" in data_status

            # Trigger endpoint
            resp_run = client.post(
                "/api/scrapers/run",
                json={"keywords": "Python", "location": "Remote", "results_wanted": 5},
            )
            assert resp_run.status_code == 200
            data_run = resp_run.json()
            assert data_run["status"] in ("triggered", "already_running")
