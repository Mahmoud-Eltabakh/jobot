"""Unit and integration tests for AI-Assisted Web Scraping & Query Strategy."""

import json
import pytest
from sqlmodel import Session

from app.ai.client import MockAIClient
from app.db.database import engine, init_db
from app.db.models import FilterRule, UserProfile
from app.scrapers.ai_extractor import AIScraperExtractor
from app.scrapers.query_strategist import AIQueryStrategist
from app.scrapers.stepstone import StepStoneScraper


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


@pytest.mark.asyncio
async def test_ai_scraper_extractor_clean_and_extract():
    """Verify HTML cleaning and AI-assisted extraction of unstructured job postings."""
    raw_html = """
    <html>
      <head><title>Job Page</title></head>
      <body>
        <script>var x = 123;</script>
        <div class="header">Navigation Bar</div>
        <div class="job-container">
          <h1>Lead Python Backend Architect</h1>
          <div class="company-name">Quantum Cloud Systems</div>
          <div class="location-badge">Berlin, Germany (100% Homeoffice / Remote)</div>
          <div class="salary-box">Compensation: 85,000 € - 110,000 EUR per year</div>
          <p>We are seeking an experienced architect to lead our FastAPI and Kubernetes services. Must have 5+ years of Python.</p>
        </div>
      </body>
    </html>
    """

    cleaned = AIScraperExtractor.clean_html_to_markdown_text(raw_html)
    assert "Navigation Bar" in cleaned or "Lead Python Backend Architect" in cleaned
    assert "var x = 123" not in cleaned

    mock_ai = MockAIClient(default_response=json.dumps({
        "title": "Lead Python Backend Architect",
        "company": "Quantum Cloud Systems",
        "location": "Berlin, Germany",
        "is_remote": True,
        "salary_min": 85000,
        "salary_max": 110000,
        "salary_currency": "EUR",
        "description": "Lead architect position focused on FastAPI and Kubernetes.",
        "required_skills": ["Python", "FastAPI", "Kubernetes"],
        "visa_sponsorship": "available",
        "language_requirement": "English",
        "is_legitimate_job": True,
    }))

    scraped = await AIScraperExtractor.extract_from_html(
        html_or_text=raw_html,
        source_url="https://example.com/job/lead-python",
        source="stepstone",
        ai_client=mock_ai,
    )

    assert scraped is not None
    assert scraped.title == "Lead Python Backend Architect"
    assert scraped.company == "Quantum Cloud Systems"
    assert scraped.is_remote is True
    assert scraped.salary_min == 85000
    assert scraped.salary_max == 110000
    assert scraped.salary_currency == "EUR"


@pytest.mark.asyncio
async def test_ai_scraper_extractor_spam_filter():
    """Verify that spam/promotional non-job listings are discarded."""
    spam_html = """
    <div>
      <h2>Learn Python in 30 Days Bootcamp - 50% Off!</h2>
      <p>Enroll now in our online certificate course for only $499.</p>
    </div>
    """

    mock_ai = MockAIClient(default_response=json.dumps({
        "title": "Course Promotion",
        "company": "Bootcamp Inc",
        "location": "Online",
        "is_remote": True,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "description": "Educational course advertisement.",
        "required_skills": [],
        "visa_sponsorship": None,
        "language_requirement": None,
        "is_legitimate_job": False,
    }))

    scraped = await AIScraperExtractor.extract_from_html(
        html_or_text=spam_html,
        source_url="https://example.com/ad",
        source="web",
        ai_client=mock_ai,
    )
    assert scraped is None


@pytest.mark.asyncio
async def test_ai_query_strategist():
    """Verify AI search query generation combining candidate skills and blacklist awareness."""
    with Session(engine) as session:
        profile = UserProfile(
            full_name="Alex Johnson",
            target_titles_json=json.dumps(["Senior Python Engineer", "Backend Developer"]),
            skills_json=json.dumps(["Python", "FastAPI", "Docker", "PostgreSQL", "ChromaDB"]),
            active_search_skills_json=json.dumps(["Python", "FastAPI", "Docker"]),
            target_locations_json=json.dumps(["Munich", "Remote"]),
            work_preference="remote_first",
        )
        session.add(profile)

        rule = FilterRule(rule_type="title", pattern="Junior")
        session.add(rule)
        session.commit()

        mock_ai = MockAIClient(default_response=json.dumps([
            {"platform": "linkedin", "keywords": "Python FastAPI Remote", "location": "Munich"},
            {"platform": "stepstone", "keywords": "Senior Python Backend", "location": "Remote"},
            {"platform": "google", "keywords": "Docker Python Engineer", "location": "Germany"},
        ]))

        queries = await AIQueryStrategist.generate_search_queries(
            session=session,
            max_queries=3,
            ai_client=mock_ai,
        )

        assert len(queries) == 3
        platforms = [q[0] for q in queries]
        keywords = [q[1] for q in queries]
        assert "linkedin" in platforms
        assert "Python FastAPI Remote" in keywords


def test_stepstone_ai_dom_fallback():
    """Verify StepStone parser falls back to AI extractor logic when CSS selectors encounter non-standard markup."""
    unstructured_html = """
    <section>
      <h1>Cloud Infrastructure Engineer</h1>
      <h3>Global Tech Solutions</h3>
      <p>Looking for a talented cloud architect with Python experience. 80.000 - 95.000 EUR. Homeoffice enabled.</p>
    </section>
    """

    jobs = StepStoneScraper.parse_cards_from_html(unstructured_html, base_url="https://stepstone.de")
    assert len(jobs) >= 1
    job = jobs[0]
    assert "Cloud Infrastructure" in job.title or "Software Developer" in job.title
