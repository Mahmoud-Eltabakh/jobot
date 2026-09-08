"""Tests for automatic blacklist rule suggester and search query optimizer."""

import pytest
from sqlmodel import Session

from app.ai.blacklist_suggester import BlacklistSuggester
from app.db.database import engine, init_db
from app.db.models import FeedbackNote, FilterRule, Job, JobStatus
from app.scrapers.query_optimizer import SearchQueryOptimizer


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


@pytest.mark.asyncio
async def test_blacklist_suggester_extracts_negative_themes() -> None:
    """Verify BlacklistSuggester proposes rules based on recurring critique keywords."""
    with Session(engine) as session:
        # Create jobs marked as not a fit
        j1 = Job(
            source="linkedin",
            title="Senior PHP Dev",
            company="LegacyCo",
            location="Remote",
            url="https://example.com/b1",
            status=JobStatus.NOT_A_FIT.value,
            dedup_hash="hash-sug-1",
        )
        j2 = Job(
            source="stepstone",
            title="PHP Fullstack",
            company="WebAgency",
            location="Remote",
            url="https://example.com/b2",
            status=JobStatus.NOT_A_FIT.value,
            dedup_hash="hash-sug-2",
        )
        session.add(j1)
        session.add(j2)
        session.commit()
        session.refresh(j1)
        session.refresh(j2)

        # Add negative notes with recurring theme "on-site"
        n1 = FeedbackNote(job_id=j1.id, sentiment="negative", note_text="Requires German language and on-site commute")
        n2 = FeedbackNote(job_id=j2.id, sentiment="negative", note_text="Mandatory German language requirements")
        session.add(n1)
        session.add(n2)
        session.commit()

        # Generate suggestions
        suggestions = await BlacklistSuggester.analyze_rejections_and_suggest_rules(
            session=session,
            min_occurrences=2,
        )

        patterns = [s.pattern.lower() for s in suggestions]
        assert "german" in patterns or "php" in patterns


def test_search_query_optimizer_positive_history() -> None:
    """Verify SearchQueryOptimizer extracts top skills from applied/interview jobs."""
    with Session(engine) as session:
        j1 = Job(
            source="linkedin",
            title="Senior FastAPI Backend Developer",
            company="FinTech A",
            location="Remote",
            url="https://example.com/q1",
            status=JobStatus.APPLIED.value,
            dedup_hash="hash-opt-1",
        )
        j2 = Job(
            source="google",
            title="FastAPI Cloud Engineer",
            company="CloudCo B",
            location="Remote",
            url="https://example.com/q2",
            status=JobStatus.INTERVIEW_1.value,
            dedup_hash="hash-opt-2",
        )
        session.add(j1)
        session.add(j2)
        session.commit()

        terms = SearchQueryOptimizer.get_optimized_search_terms(session, min_occurrences=2)
        assert any("Fastapi" in t for t in terms)
