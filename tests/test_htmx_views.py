"""Tests for HTMX partial views (Kanban board, Table view, Job Inspector)."""

import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.database import engine, init_db
from app.db.models import Job, JobStatus, JobStatusHistory
from app.main import app


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def test_kanban_view() -> None:
    """Verify /web/views/kanban renders all 8 columns and job cards."""
    with Session(engine) as session:
        job = Job(
            source="linkedin",
            title="Senior Python Architect",
            company="CloudTech",
            location="Berlin",
            is_remote=True,
            salary_min=85000,
            salary_max=105000,
            url="https://linkedin.com/jobs/view/901",
            status=JobStatus.SEEN.value,
            fit_score=92,
            dedup_hash="hash-kanban-test-1",
        )
        session.add(job)
        session.commit()

    with TestClient(app) as client:
        resp = client.get("/web/views/kanban")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "New Matches" in resp.text
        assert "Applied" in resp.text
        assert "Senior Python Architect" in resp.text
        assert "92%" in resp.text


def test_table_view() -> None:
    """Verify /web/views/table renders tabular rows."""
    with Session(engine) as session:
        job = Job(
            source="stepstone",
            title="FastAPI Backend Engineer",
            company="EuroSoft",
            location="Munich",
            url="https://stepstone.de/jobs/902",
            status=JobStatus.APPLIED.value,
            fit_score=84,
            dedup_hash="hash-table-test-1",
        )
        session.add(job)
        session.commit()

    with TestClient(app) as client:
        resp = client.get("/web/views/table")
        assert resp.status_code == 200
        assert "<table" in resp.text
        assert "FastAPI Backend Engineer" in resp.text
        assert "EuroSoft" in resp.text


def test_job_inspector() -> None:
    """Verify /web/job/{id}/inspect renders detail drawer."""
    with Session(engine) as session:
        job = Job(
            source="google",
            title="Fullstack AI Developer",
            company="DeepMind Labs",
            location="Remote",
            url="https://google.com/jobs/view/903",
            description="Leading AI developments using Python and TypeScript.",
            status=JobStatus.INTERVIEW_1.value,
            fit_score=95,
            fit_summary="Phenomenal alignment with candidate tech stack.",
            pros_json=json.dumps(["FastAPI expertise", "LLM experience"]),
            cons_json=json.dumps(["Timezone offset"]),
            missing_skills_json=json.dumps(["Rust"]),
            dedup_hash="hash-inspect-test-1",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

    with TestClient(app) as client:
        resp = client.get(f"/web/job/{job_id}/inspect")
        assert resp.status_code == 200
        assert "Fullstack AI Developer" in resp.text
        assert "FastAPI expertise" in resp.text
        assert "Rust" in resp.text
        assert "Timezone offset" in resp.text


def test_update_status_and_add_notes() -> None:
    """Verify updating job status and posting candidate notes."""
    with Session(engine) as session:
        job = Job(
            source="linkedin",
            title="DevOps Engineer",
            company="InfraCorp",
            location="Remote",
            url="https://linkedin.com/jobs/view/904",
            status=JobStatus.SEEN.value,
            dedup_hash="hash-notes-test-1",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

    with TestClient(app) as client:
        # Update status
        resp_status = client.put(
            f"/api/jobs/{job_id}/status",
            data={"new_status": "applied", "notes": "Applied on company careers portal"},
        )
        assert resp_status.status_code == 200
        assert resp_status.headers.get("HX-Trigger") == "refreshView"

        # Add candidate note
        resp_note = client.post(
            f"/api/jobs/{job_id}/notes",
            data={"note_text": "Spoke with recruiter Sarah. Next round scheduled for Tuesday.", "sentiment": "positive"},
        )
        assert resp_note.status_code == 200
        assert "Spoke with recruiter Sarah" in resp_note.text
        assert "positive" in resp_note.text.lower()
