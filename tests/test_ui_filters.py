"""Tests for multi-criteria live filtering and sorting toolbar queries."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.database import engine, init_db
from app.db.models import Job, JobStatus
from app.main import app


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def test_multi_criteria_filtering_and_sorting() -> None:
    """Verify filtering across search terms, score thresholds, remote flags, and status exclusions."""
    with Session(engine) as session:
        j1 = Job(
            source="linkedin",
            title="Senior Python Backend Engineer",
            company="AlphaCorp",
            location="Berlin",
            is_remote=True,
            salary_min=90000,
            url="https://example.com/f1",
            status=JobStatus.SEEN.value,
            fit_score=95,
            dedup_hash="hash-filter-1",
        )
        j2 = Job(
            source="stepstone",
            title="Junior Frontend React Dev",
            company="BetaWeb",
            location="Munich",
            is_remote=False,
            salary_min=50000,
            url="https://example.com/f2",
            status=JobStatus.REJECTED.value,
            fit_score=45,
            dedup_hash="hash-filter-2",
        )
        j3 = Job(
            source="google",
            title="Python Data Scientist",
            company="DataCo",
            location="Remote",
            is_remote=True,
            salary_min=75000,
            url="https://example.com/f3",
            status=JobStatus.NOT_A_FIT.value,
            fit_score=65,
            dedup_hash="hash-filter-3",
        )
        session.add(j1)
        session.add(j2)
        session.add(j3)
        session.commit()

    with TestClient(app) as client:
        # 1. Search keyword filter
        resp_q = client.get("/web/views/table?q=Python")
        assert resp_q.status_code == 200
        assert "Senior Python Backend Engineer" in resp_q.text
        assert "Junior Frontend React Dev" not in resp_q.text

        # 2. Minimum fit score filter (min_score=80)
        resp_score = client.get("/web/views/table?min_score=80")
        assert "Senior Python Backend Engineer" in resp_score.text
        assert "Python Data Scientist" not in resp_score.text

        # 3. Work model filter (remote only)
        resp_remote = client.get("/web/views/table?work_model=remote")
        assert "Senior Python Backend Engineer" in resp_remote.text
        assert "Junior Frontend React Dev" not in resp_remote.text

        # 4. Hide rejected and not a fit toggles
        resp_hide = client.get("/web/views/table?hide_rejected=true&hide_not_fit=true")
        assert "Senior Python Backend Engineer" in resp_hide.text
        assert "Junior Frontend React Dev" not in resp_hide.text
        assert "Python Data Scientist" not in resp_hide.text
