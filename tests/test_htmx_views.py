"""Tests for HTMX partial views (Kanban board, Table view, Job Inspector)."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.database import engine, init_db
from app.db.models import Job, JobStatus


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def test_kanban_view(authenticated_client: TestClient, authenticated_user: dict) -> None:
    """Verify /web/views/kanban renders all 8 columns and job cards."""
    with Session(engine) as session:
        job = Job(
            user_id=authenticated_user["id"],
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

    resp = authenticated_client.get("/web/views/kanban")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "NEW" in resp.text
    assert "Applied" in resp.text
    assert "Senior Python Architect" in resp.text
    assert "92%" in resp.text


def test_table_view(authenticated_client: TestClient, authenticated_user: dict) -> None:
    """Verify /web/views/table renders tabular rows."""
    with Session(engine) as session:
        job = Job(
            user_id=authenticated_user["id"],
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

    resp = authenticated_client.get("/web/views/table")
    assert resp.status_code == 200
    assert "<table" in resp.text
    assert "FastAPI Backend Engineer" in resp.text
    assert "EuroSoft" in resp.text


def test_queue_poll_replaces_only_its_own_panel(authenticated_client: TestClient) -> None:
    """Queue polling must not replace the shared navigation target."""
    response = authenticated_client.get("/web/views/queue")

    assert response.status_code == 200
    assert 'hx-target="this"' in response.text
    assert 'hx-sync="this:replace"' in response.text


def test_job_inspector(authenticated_client: TestClient, authenticated_user: dict) -> None:
    """Verify /web/job/{id}/inspect renders detail drawer."""
    with Session(engine) as session:
        job = Job(
            user_id=authenticated_user["id"],
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

    resp = authenticated_client.get(f"/web/job/{job_id}/inspect")
    assert resp.status_code == 200
    assert "Fullstack AI Developer" in resp.text
    assert "FastAPI expertise" in resp.text
    assert "Rust" in resp.text
    assert "Timezone offset" in resp.text


def test_update_status_and_add_notes(authenticated_client: TestClient, authenticated_user: dict) -> None:
    """Verify updating job status and posting candidate notes."""
    with Session(engine) as session:
        job = Job(
            user_id=authenticated_user["id"],
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

    # Exercise both mutations through the same authenticated browser session.
    resp_status = authenticated_client.put(
        f"/api/jobs/{job_id}/status",
        data={"new_status": "applied", "notes": "Applied on company careers portal"},
    )
    assert resp_status.status_code == 200
    assert resp_status.headers.get("HX-Trigger") == "refreshView"

    resp_note = authenticated_client.post(
        f"/api/jobs/{job_id}/notes",
        data={"note_text": "Spoke with recruiter Sarah. Next round scheduled for Tuesday.", "sentiment": "positive"},
    )
    assert resp_note.status_code == 200
    assert "Spoke with recruiter Sarah" in resp_note.text
    assert "positive" in resp_note.text.lower()
