"""End-to-end integration workflow test verifying the entire Jobot pipeline."""

import json
import time
import pytest
from starlette.testclient import TestClient
from sqlmodel import Session, select

from app.ai.client import MockAIClient
from app.ai.evaluator import JobEvaluator
from app.ai.feedback import FeedbackManager
from app.db.database import engine, init_db
from app.db.models import FilterRule, Job, JobStatus, UserProfile
from app.db.vector import VectorStore, get_vector_store
from app.main import app
from app.scrapers.base import ScrapedJob
from app.scrapers.dedup import compute_dedup_hash, save_scraped_jobs
from app.scrapers.filter_pipeline import JobFilterPipeline
from app.scrapers.scheduler import ScraperPipeline


@pytest.fixture(autouse=True)
def setup_clean_state() -> None:
    init_db()


@pytest.mark.asyncio
async def test_full_pipeline_e2e_workflow() -> None:
    """Test full workflow: Scraping -> Dedup -> Filter -> Vector RAG -> Fit Score -> Feedback -> Re-scoring."""
    ai_client = MockAIClient()
    vector_store = get_vector_store()
    timestamp = int(time.time() * 1000)

    # 1. Store User Profile in DB & ChromaDB
    with Session(engine) as session:
        profile = UserProfile(
            full_name="Alex Tech",
            cv_raw_text="Senior Python backend engineer with 8 years experience in FastAPI, Docker, and Kubernetes.",
            skills_json=json.dumps(["Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL"]),
            experience_years=8,
            target_titles_json=json.dumps(["Senior Python Engineer", "Backend Developer"]),
        )
        session.add(profile)

        # Add a blacklist filter rule for WordPress
        rule = FilterRule(rule_type="title", pattern="WordPress", is_active=True)
        session.add(rule)
        session.commit()
        session.refresh(profile)

    # 2. Simulate Scraped Jobs (1 Good Fit, 1 Blacklisted, 1 Low Fit)
    job_good = ScrapedJob(
        title=f"Senior Python Backend Developer {timestamp}",
        company="FastAI Cloud",
        location="Remote",
        description="We are seeking an experienced Senior Python Engineer skilled in FastAPI, Docker, and Microservices.",
        url=f"https://example.com/job/good-{timestamp}",
        source="linkedin",
    )
    job_blacklisted = ScrapedJob(
        title=f"Senior WordPress Developer {timestamp}",
        company="OldWeb Co",
        location="Remote",
        description="Looking for a WordPress PHP developer to maintain legacy plugins.",
        url=f"https://example.com/job/blocked-{timestamp}",
        source="stepstone",
    )
    job_mediocre = ScrapedJob(
        title=f"Entry Level Java Developer {timestamp}",
        company="Enterprise Java",
        location="Berlin",
        description="Junior position working on Spring Boot enterprise portals.",
        url=f"https://example.com/job/med-{timestamp}",
        source="google",
    )

    # 3. Deduplication and Ingestion
    with Session(engine) as session:
        saved_jobs, dup_count = save_scraped_jobs([job_good, job_blacklisted, job_mediocre], session)
        assert len(saved_jobs) >= 1

    # 4. Filter Pipeline Execution
    with Session(engine) as session:
        rules = session.exec(select(FilterRule).where(FilterRule.is_active == True)).all()

        for job in session.exec(select(Job)).all():
            res = JobFilterPipeline.evaluate_job(job, rules)
            if res.is_filtered:
                job.status = JobStatus.NOT_A_FIT.value
                job.fit_score = 0.0
                job.fit_summary = f"Pre-filtered: {res.reason}"
                session.add(job)
        session.commit()

        # Verify WordPress was pre-filtered
        wp_job = session.exec(select(Job).where(Job.title.contains("WordPress"))).first()
        assert wp_job is not None
        assert wp_job.status == JobStatus.NOT_A_FIT.value
        assert wp_job.fit_score == 0.0

    # 5. AI Evaluation on Allowed Jobs
    with Session(engine) as session:
        good_job_db = session.exec(select(Job).where(Job.title.contains("Senior Python Backend Developer"))).first()
        assert good_job_db is not None

        evaluation = await JobEvaluator.evaluate_job(
            candidate_summary="Senior Python backend engineer with 8 years experience in FastAPI, Docker, and Kubernetes.",
            job_description=good_job_db.description or "",
            ai_client=ai_client,
        )
        assert evaluation.fit_score > 0
        good_job_db.fit_score = float(evaluation.fit_score)
        good_job_db.fit_summary = evaluation.fit_summary
        session.add(good_job_db)
        session.commit()
        session.refresh(good_job_db)

    # 6. User Feedback Vector Recording
    with Session(engine) as session:
        good_job_db = session.exec(select(Job).where(Job.title.contains("Senior Python Backend Developer"))).first()
        assert good_job_db is not None

        # User applies to this job!
        doc_id = await FeedbackManager.record_job_feedback(
            job_id=good_job_db.id,
            status=JobStatus.APPLIED.value,
            note_text="Loved the tech stack FastAPI and Docker remote setup",
            session=session,
            vector_store=vector_store,
            ai_client=ai_client,
        )
        assert doc_id is not None
        assert vector_store.count(VectorStore.COLLECTION_USER_FEEDBACK) >= 1

        # 7. Adaptive Re-weighting calculation with identical feedback text
        exact_doc_text = f"Title: {good_job_db.title}\nCompany: {good_job_db.company}\nLocation: {good_job_db.location}\nStatus: {JobStatus.APPLIED.value}\nCandidate Note: Loved the tech stack FastAPI and Docker remote setup\nDescription snippet: {good_job_db.description[:400]}"
        delta, reasons = await FeedbackManager.compute_feedback_score_adjustment(
            job_text=exact_doc_text,
            vector_store=vector_store,
            ai_client=ai_client,
        )
        # Should receive positive fit bonus
        assert delta > 0


def test_web_ui_dashboard_e2e_interaction() -> None:
    """Verify Web Dashboard displays jobs and allows status updates via API/HTMX."""
    client = TestClient(app)
    timestamp = int(time.time() * 1000)

    # Insert a unique job
    with Session(engine) as session:
        job = Job(
            source="linkedin",
            title=f"Fullstack Python Engineer {timestamp}",
            company="ModernStack",
            location="Remote",
            url=f"https://example.com/e2e-ui-{timestamp}",
            status=JobStatus.SEEN.value,
            fit_score=88.0,
            fit_summary="Strong match with FastAPI and Python expertise.",
            dedup_hash=f"e2e-ui-hash-{timestamp}",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

    # 1. Verify GET /
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert "Jobot" in res_home.text

    # 2. Verify GET /web/views/kanban
    res_kanban = client.get("/web/views/kanban")
    assert res_kanban.status_code == 200
    assert "Fullstack Python Engineer" in res_kanban.text

    # 3. Verify GET /web/views/table
    res_table = client.get("/web/views/table")
    assert res_table.status_code == 200
    assert "ModernStack" in res_table.text

    # 4. Verify PUT /api/jobs/{id}/status via Form data
    res_update = client.put(f"/api/jobs/{job_id}/status", data={"new_status": "1. interview"})
    assert res_update.status_code == 200
