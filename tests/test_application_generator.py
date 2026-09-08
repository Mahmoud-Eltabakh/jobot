"""Unit and integration tests for AI Cover Letter Generator & Resume Tailoring Engine."""

import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.ai.application_generator import ApplicationGenerator
from app.ai.client import MockAIClient
from app.db.database import engine, init_db
from app.db.models import ApplicationMaterial, Job, UserProfile
from app.main import app


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def create_sample_job_and_profile(session: Session) -> tuple[Job, UserProfile]:
    """Helper to create sample job and user profile records in SQLite."""
    job = Job(
        title="Senior Python & Backend Engineer",
        company="Fintech Dynamics GmbH",
        location="Frankfurt, Germany",
        is_remote=True,
        source="linkedin",
        url="https://linkedin.com/jobs/view/123456",
        description="We are seeking an experienced Senior Python Engineer skilled in FastAPI, Docker, and PostgreSQL.",
        fit_score=90,
        pros_json=json.dumps(["5+ years Python", "FastAPI and Docker expertise"]),
        cons_json=json.dumps(["No previous fintech experience"]),
        missing_skills_json=json.dumps(["Kafka"]),
        dedup_hash="test_app_gen_hash_12345",
    )
    session.add(job)

    profile = UserProfile(
        full_name="Morgan Chase",
        headline="Senior Python Engineer & Cloud Developer",
        bio="Passionate engineer with extensive expertise in distributed systems and FastAPI microservices.",
        experience_years=6.0,
        target_titles_json=json.dumps(["Senior Python Engineer", "Backend Architect"]),
        skills_json=json.dumps(["Python", "FastAPI", "Docker", "PostgreSQL", "ChromaDB"]),
        active_search_skills_json=json.dumps(["Python", "FastAPI"]),
        target_locations_json=json.dumps(["Frankfurt", "Remote"]),
    )
    session.add(profile)
    session.commit()
    session.refresh(job)
    session.refresh(profile)
    return job, profile


@pytest.mark.asyncio
async def test_application_generator_cover_letter():
    """Verify generating cover letters with custom tones using AI generator."""
    with Session(engine) as session:
        job, profile = create_sample_job_and_profile(session)

        mock_ai = MockAIClient(default_response="""# Application for Senior Python Engineer

Dear Fintech Dynamics GmbH Team,

I am writing to express my strong enthusiasm for the Senior Python & Backend Engineer position...
""")

        content = await ApplicationGenerator.generate_cover_letter(
            job=job,
            user_profile=profile,
            tone="enthusiastic",
            ai_client=mock_ai,
        )

        assert "Senior Python" in content
        assert "Fintech Dynamics GmbH" in content or "Application" in content

        # Save material
        material = ApplicationGenerator.save_material(
            session=session,
            job_id=job.id,
            material_type="cover_letter",
            content_markdown=content,
            tone="enthusiastic",
        )
        assert material.id is not None
        assert material.tone == "enthusiastic"


@pytest.mark.asyncio
async def test_application_generator_tailored_resume():
    """Verify generating ATS tailored resume bullet points."""
    with Session(engine) as session:
        job, profile = create_sample_job_and_profile(session)

        mock_ai = MockAIClient(default_response="""### Tailored Accomplishments
- **Architected Scalable FastAPI Services**: Designed distributed backend microservices...
- **Optimized PostgreSQL Workflows**: Reduced latency by 40%...
""")

        content = await ApplicationGenerator.generate_tailored_resume_points(
            job=job,
            user_profile=profile,
            ai_client=mock_ai,
        )

        assert "FastAPI" in content or "Architected" in content

        material = ApplicationGenerator.save_material(
            session=session,
            job_id=job.id,
            material_type="tailored_resume",
            content_markdown=content,
        )
        assert material.id is not None
        assert material.material_type == "tailored_resume"


def test_applications_rest_api():
    """Test REST endpoints for generating and fetching application materials."""
    with Session(engine) as session:
        job, _ = create_sample_job_and_profile(session)
        job_id = job.id

    with TestClient(app) as client:
        # 1. Generate Cover Letter via API
        gen_resp = client.post(
            f"/api/jobs/{job_id}/cover-letter/generate",
            json={"tone": "direct", "custom_instructions": "Highlight remote productivity."},
        )
        assert gen_resp.status_code == 200
        data = gen_resp.json()
        assert data["status"] == "ok"
        assert data["material_type"] == "cover_letter"
        material_id = data["material_id"]

        # 2. Generate Tailored Resume via API
        resume_resp = client.post(f"/api/jobs/{job_id}/tailor-resume/generate")
        assert resume_resp.status_code == 200
        assert resume_resp.json()["material_type"] == "tailored_resume"

        # 3. Get All Job Materials
        list_resp = client.get(f"/api/jobs/{job_id}/materials")
        assert list_resp.status_code == 200
        materials = list_resp.json()["materials"]
        assert len(materials) >= 2

        # 4. Update Material
        put_resp = client.put(
            f"/api/jobs/materials/{material_id}",
            json={"content_markdown": "# Updated Cover Letter Content\nReady to interview."},
        )
        assert put_resp.status_code == 200
        assert "Updated Cover Letter" in put_resp.json()["content_markdown"]


def test_job_inspector_drawer_and_htmx_endpoints():
    """Test rendering the Job Inspector drawer with application tabs and HTMX generation endpoints."""
    with Session(engine) as session:
        job, _ = create_sample_job_and_profile(session)
        job_id = job.id

    with TestClient(app) as client:
        # 1. GET Inspector HTML
        resp = client.get(f"/web/job/{job_id}/inspect")
        assert resp.status_code == 200
        assert "AI Cover Letter" in resp.text
        assert "Tailored Resume" in resp.text

        # 2. POST Generate Cover Letter via HTMX endpoint
        cl_resp = client.post(
            f"/web/job/{job_id}/cover-letter/generate",
            data={"tone": "professional"},
        )
        assert cl_resp.status_code == 200
        assert "cover-letter-text" in cl_resp.text
        assert "Copy to Clipboard" in cl_resp.text

        # 3. POST Generate Tailored Resume via HTMX endpoint
        cv_resp = client.post(f"/web/job/{job_id}/tailor-resume/generate")
        assert cv_resp.status_code == 200
        assert "tailored-resume-text" in cv_resp.text

        # 4. POST Save Material Changes
        save_resp = client.post(
            f"/web/job/{job_id}/materials/save",
            data={
                "material_type": "cover_letter",
                "content_markdown": "Final custom saved letter.",
                "tone": "professional",
            },
        )
        assert save_resp.status_code == 200
        assert "Saved!" in save_resp.text
