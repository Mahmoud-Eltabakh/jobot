"""Tests for JobSpy scraper integration and DataFrame mapping."""

from unittest.mock import patch

import pandas as pd
import pytest

from app.scrapers.jobspy_scraper import JobSpyScraper, resolve_jobspy_country


@pytest.mark.parametrize(
    ("location", "explicit", "expected"),
    [
        ("", None, "usa"),
        (None, None, "usa"),
        ("Germany", None, "Germany"),
        ("Berlin, Germany", None, "Germany"),
        ("Remote", None, "usa"),
        ("Berlin", "germany", "germany"),
    ],
)
def test_resolve_jobspy_country_never_returns_invalid(location, explicit, expected) -> None:
    """Blank or city-style locations must map to a country JobSpy accepts."""
    assert resolve_jobspy_country(location, explicit) == expected


@pytest.mark.asyncio
async def test_jobspy_scraper_mapping() -> None:
    """Verify JobSpyScraper maps DataFrame columns to ScrapedJob objects."""
    mock_df = pd.DataFrame([
        {
            "id": "li-101",
            "site": "linkedin",
            "title": "Senior Python Developer",
            "company": "TechNova",
            "location": "Berlin, Germany",
            "job_url": "https://linkedin.com/jobs/view/101",
            "description": "Building microservices with FastAPI and Docker.",
            "min_amount": 80000,
            "max_amount": 100000,
            "currency": "EUR",
            "is_remote": True,
            "date_posted": "2026-09-01",
        },
        {
            "id": "goog-202",
            "site": "google",
            "title": "AI Platform Engineer",
            "company": "DataCorp",
            "location": "Munich, Germany",
            "job_url": "https://google.com/jobs/view/202",
            "description": "MLOps and backend LLM pipelines.",
            "min_amount": 90000,
            "max_amount": 115000,
            "currency": "EUR",
            "is_remote": False,
            "date_posted": "2026-09-02",
        },
    ])

    scraper = JobSpyScraper()

    def mock_scrape_jobs(site_name, **kwargs):
        # Return only the rows matching the requested site
        return mock_df[mock_df["site"].isin(site_name)]

    with patch("app.scrapers.jobspy_scraper.scrape_jobs", side_effect=mock_scrape_jobs):
        jobs = await scraper.scrape(
            search_term="Python",
            location="Germany",
            results_wanted=2,
        )

        assert len(jobs) == 2
        assert jobs[0].source == "linkedin"
        assert jobs[0].title == "Senior Python Developer"
        assert jobs[0].salary_min == 80000.0
        assert jobs[0].is_remote is True
        assert jobs[1].source == "google"
        assert jobs[1].company == "DataCorp"


@pytest.mark.asyncio
async def test_jobspy_scraper_empty_or_error_handling() -> None:
    """Verify JobSpyScraper handles exceptions and empty DataFrames without raising."""
    scraper = JobSpyScraper()

    # Empty DataFrame
    with patch("app.scrapers.jobspy_scraper.scrape_jobs", return_value=pd.DataFrame()):
        jobs_empty = await scraper.scrape(search_term="NonExistentQuery", location="Nowhere")
        assert jobs_empty == []

    # Exception thrown
    with patch("app.scrapers.jobspy_scraper.scrape_jobs", side_effect=RuntimeError("Rate limit exceeded")):
        jobs_error = await scraper.scrape(search_term="Python", location="Berlin")
        assert jobs_error == []
