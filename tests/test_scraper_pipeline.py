"""Tests for scraper data contracts, deduplication hashing, and database persistence."""

import pytest
from sqlmodel import Session

from app.db.database import engine, init_db
from app.db.models import JobStatus
from app.scrapers.base import ScrapedJob
from app.scrapers.dedup import compute_dedup_hash, save_scraped_jobs


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def test_scraped_job_model_validation() -> None:
    """Verify ScrapedJob model field constraints and defaults."""
    job = ScrapedJob(
        source="linkedin",
        title="Python Developer",
        company="TechCorp Inc.",
        location="Berlin, Germany",
        url="https://linkedin.com/jobs/view/100",
        description="Great python opportunity.",
        is_remote=True,
        salary_min=80000.0,
        salary_max=95000.0,
        salary_currency="EUR",
    )
    assert job.source == "linkedin"
    assert job.is_remote is True
    assert job.salary_min == 80000.0


def test_compute_dedup_hash_normalization() -> None:
    """Verify hash normalization handles case differences, symbols, and whitespace."""
    hash1 = compute_dedup_hash("TechCorp Inc.", "Senior Python Engineer", "Berlin, Germany")
    hash2 = compute_dedup_hash("techcorp inc", "  senior python engineer ", "berlin  germany")
    hash3 = compute_dedup_hash("DifferentCorp", "Senior Python Engineer", "Berlin, Germany")

    assert hash1 == hash2
    assert hash1 != hash3


def test_save_scraped_jobs_deduplication() -> None:
    """Verify save_scraped_jobs inserts unique jobs and skips duplicate hashes."""
    jobs = [
        ScrapedJob(
            source="linkedin",
            title="Backend Engineer",
            company="Alpha Software",
            location="Remote",
            url="https://linkedin.com/jobs/view/201",
            description="Backend role in Python.",
        ),
        ScrapedJob(
            source="google",
            title="Backend Engineer",
            company="Alpha Software",
            location="Remote",  # Duplicate of above
            url="https://google.com/search?q=job201",
            description="Same backend role.",
        ),
        ScrapedJob(
            source="stepstone",
            title="Frontend Engineer",
            company="Beta Web",
            location="Berlin",
            url="https://stepstone.de/jobs/301",
            description="React & TypeScript role.",
        ),
    ]

    with Session(engine) as session:
        inserted, skipped = save_scraped_jobs(jobs, session)
        assert len(inserted) == 2
        assert skipped == 1
        assert inserted[0].status == JobStatus.NEW.value

        # Re-running the same batch should insert 0 and skip all 3
        inserted_second_run, skipped_second_run = save_scraped_jobs(jobs, session)
        assert len(inserted_second_run) == 0
        assert skipped_second_run == 3
