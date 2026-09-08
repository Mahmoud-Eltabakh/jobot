"""Tests for StepStone Playwright scraper card parsing and DOM extraction."""

from app.scrapers.stepstone import StepStoneScraper

SAMPLE_STEPSTONE_HTML = """
<html>
<body>
    <article data-testid="job-item">
        <a data-testid="job-item-title" href="/stellenangebote--Senior-Python-Developer-Berlin-TechSolutions--1001234.html">
            Senior Python Developer (m/w/d)
        </a>
        <span data-testid="job-item-company-name">TechSolutions GmbH</span>
        <span data-testid="job-item-location">Berlin, Homeoffice möglich</span>
        <span data-testid="job-item-salary">70.000 € - 85.000 €</span>
        <div data-testid="job-item-snippet">
            Wir suchen einen erfahrenen Python Backend Developer mit FastAPI und Docker Kenntnissen.
        </div>
    </article>
    <article data-testid="job-item">
        <a data-testid="job-item-title" href="/stellenangebote--Cloud-Architect-Munich-CloudBase--1005678.html">
            Cloud Architect (m/w/d)
        </a>
        <span data-testid="job-item-company-name">CloudBase AG</span>
        <span data-testid="job-item-location">München</span>
        <span data-testid="job-item-salary">90.000 €</span>
        <div data-testid="job-item-snippet">
            AWS and Kubernetes infrastructure design.
        </div>
    </article>
</body>
</html>
"""


def test_parse_cards_from_html() -> None:
    """Verify StepStone DOM parsing extracts titles, companies, locations, salary tags, and links."""
    jobs = StepStoneScraper.parse_cards_from_html(SAMPLE_STEPSTONE_HTML)

    assert len(jobs) == 2

    # Job 1
    j1 = jobs[0]
    assert j1.source == "stepstone"
    assert "Senior Python Developer" in j1.title
    assert j1.company == "TechSolutions GmbH"
    assert j1.location == "Berlin, Homeoffice möglich"
    assert j1.is_remote is True
    assert j1.salary_min == 70000.0
    assert j1.salary_max == 85000.0
    assert j1.salary_currency == "EUR"
    assert "1001234" in j1.url
    assert "FastAPI" in j1.description

    # Job 2
    j2 = jobs[1]
    assert j2.company == "CloudBase AG"
    assert j2.salary_min == 90000.0
    assert j2.salary_currency == "EUR"
    assert j2.is_remote is False


def test_parse_cards_empty_html() -> None:
    """Verify empty or malformed HTML returns empty list without error."""
    jobs = StepStoneScraper.parse_cards_from_html("<html><body><div>No jobs found</div></body></html>")
    assert jobs == []
