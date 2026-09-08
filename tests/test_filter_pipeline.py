"""Tests for JobFilterPipeline and blacklist evaluation."""

import pytest
from sqlmodel import Session

from app.db.database import engine, init_db
from app.db.models import FilterRule, Job, JobStatus
from app.scrapers.base import ScrapedJob
from app.scrapers.filter_pipeline import JobFilterPipeline


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def test_evaluate_job_title_substring() -> None:
    """Test filtering by title substring."""
    rules = [
        FilterRule(rule_type="title", pattern="Staff", is_regex=False, is_active=True),
        FilterRule(rule_type="title", pattern="Director", is_regex=False, is_active=True),
    ]

    job1 = ScrapedJob(
        source="linkedin",
        title="Staff Software Engineer",
        company="TechCorp",
        url="https://example.com/1",
        description="Senior backend engineering role.",
    )
    result1 = JobFilterPipeline.evaluate_job(job1, rules)
    assert result1.is_filtered is True
    assert "Staff" in result1.reason

    job2 = ScrapedJob(
        source="linkedin",
        title="Senior Python Developer",
        company="TechCorp",
        url="https://example.com/2",
        description="Senior backend engineering role.",
    )
    result2 = JobFilterPipeline.evaluate_job(job2, rules)
    assert result2.is_filtered is False


def test_evaluate_job_company_and_keyword() -> None:
    """Test filtering by company and keyword."""
    rules = [
        FilterRule(rule_type="company", pattern="SpamAgency", is_regex=False, is_active=True),
        FilterRule(rule_type="keyword", pattern="No Remote", is_regex=False, is_active=True),
    ]

    job_spam = ScrapedJob(
        source="stepstone",
        title="Python Dev",
        company="SpamAgency GmbH",
        url="https://example.com/3",
        description="Looking for python devs.",
    )
    assert JobFilterPipeline.evaluate_job(job_spam, rules).is_filtered is True

    job_no_remote = ScrapedJob(
        source="google",
        title="Python Dev",
        company="GoodCorp",
        url="https://example.com/4",
        description="Must be 100% on-site, No Remote allowed.",
    )
    assert JobFilterPipeline.evaluate_job(job_no_remote, rules).is_filtered is True


def test_evaluate_job_regex_rule() -> None:
    """Test regex pattern matching."""
    rules = [
        FilterRule(rule_type="title", pattern=r"\b(intern|trainee)\b", is_regex=True, is_active=True),
    ]

    job_intern = ScrapedJob(
        source="linkedin",
        title="Software Engineer Intern",
        company="BigTech",
        url="https://example.com/5",
        description="Summer internship.",
    )
    assert JobFilterPipeline.evaluate_job(job_intern, rules).is_filtered is True

    job_international = ScrapedJob(
        source="linkedin",
        title="International Solutions Architect",
        company="BigTech",
        url="https://example.com/6",
        description="Global architecture.",
    )
    # "International" contains "intern" as substring, but regex word boundary \b prevents false positive
    assert JobFilterPipeline.evaluate_job(job_international, rules).is_filtered is False


def test_apply_filters_and_save_database() -> None:
    """Test applying filters to database Job entities."""
    with Session(engine) as session:
        # Create active filter rule
        rule = FilterRule(rule_type="title", pattern="UnwantedLead", is_regex=False, is_active=True)
        session.add(rule)
        session.commit()

        j1 = Job(
            source="linkedin",
            title="UnwantedLead Developer",
            company="Company A",
            location="Remote",
            url="https://example.com/j1",
            status=JobStatus.SEEN.value,
            dedup_hash="hash-filter-test-1",
        )
        j2 = Job(
            source="linkedin",
            title="Python Engineer",
            company="Company B",
            location="Remote",
            url="https://example.com/j2",
            status=JobStatus.SEEN.value,
            dedup_hash="hash-filter-test-2",
        )
        session.add(j1)
        session.add(j2)
        session.commit()
        session.refresh(j1)
        session.refresh(j2)

        approved, filtered = JobFilterPipeline.apply_filters_and_save([j1, j2], session)
        assert len(approved) == 1
        assert approved[0].id == j2.id
        assert len(filtered) == 1
        assert filtered[0].id == j1.id
        assert filtered[0].status == JobStatus.NOT_A_FIT.value
