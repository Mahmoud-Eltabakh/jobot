"""Unit and integration tests for Profile Management, LinkedIn Analysis, and Skill-Driven Scraping."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.ai.client import MockAIClient
from app.ai.embeddings import ProfileEmbedder
from app.ai.linkedin_analyzer import LinkedInProfileAnalyzer
from app.ai.profile_extractor import ExtractedProfile
from app.db.database import engine, init_db
from app.db.models import UserProfile
from app.db.vector import get_vector_store
from app.scrapers.scheduler import ScraperPipeline


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def test_profile_model_and_api(authenticated_client: TestClient):
    """Test retrieving and updating candidate profile via REST API."""
    payload = {
    "full_name": "Jane Doe",
    "headline": "Lead Python Engineer & AI Architect",
    "bio": "Experienced architect specializing in FastAPI and ChromaDB vector search.",
    "experience_years": 6.5,
    "target_titles": ["Lead Python Developer", "AI Backend Architect"],
    "target_locations": ["Remote", "Munich", "Berlin"],
    "target_salary_min": 95000,
    "work_preference": "remote_only",
    "skills": ["Python", "FastAPI", "Docker", "ChromaDB", "Kubernetes", "PostgreSQL"],
    "active_search_skills": ["Python", "FastAPI", "ChromaDB"],
    "linkedin_url": "https://www.linkedin.com/in/janedoe",
    }

    resp = authenticated_client.post("/api/profile/update", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    get_resp = authenticated_client.get("/api/profile")
    assert get_resp.status_code == 200
    data = get_resp.json()["profile"]
    assert data["full_name"] == "Jane Doe"
    assert data["headline"] == "Lead Python Engineer & AI Architect"
    assert data["experience_years"] == 6.5
    assert "FastAPI" in data["skills"]
    assert data["active_search_skills"] == ["Python", "FastAPI", "ChromaDB"]
    assert data["work_preference"] == "remote_only"


@pytest.mark.asyncio
async def test_profile_embeddings_sync():
    """Test chunking and ChromaDB embedding synchronization for candidate profile."""
    profile = ExtractedProfile(
        full_name="Alex Tech",
        headline="Senior Backend Engineer",
        summary="Specialist in microservices and distributed databases.",
        skills=["Python", "FastAPI", "Docker", "PostgreSQL", "Kafka"],
        active_search_skills=["Python", "FastAPI"],
        experience_years=5.0,
        target_titles=["Senior Backend Engineer", "Python Developer"],
        target_locations=["Remote", "Germany"],
        work_preference="remote_first",
    )

    chunks = ProfileEmbedder.chunk_profile(profile)
    assert len(chunks) == 3
    chunk_types = [c["metadata"]["chunk_type"] for c in chunks]
    assert "summary" in chunk_types
    assert "skills" in chunk_types
    assert "experience" in chunk_types

    vector_store = get_vector_store()
    mock_ai = MockAIClient()

    stored_count = await ProfileEmbedder.embed_and_store_profile(
        profile=profile,
        vector_store=vector_store,
        ai_client=mock_ai,
    )
    assert stored_count == 3


@pytest.mark.asyncio
async def test_linkedin_analyzer_text_extraction():
    """Test AI analysis and extraction of raw LinkedIn profile text."""
    raw_linkedin = """
    Jane Developer
    Senior Python & AI Engineer at TechCorp
    About: Passionate backend engineer with 7+ years of experience building scalable systems in Python and Docker.
    Experience:
    - Senior Backend Engineer at CloudSystems (3 yrs)
    - Python Developer at DataCorp (4 yrs)
    Skills: Python, FastAPI, Docker, Kubernetes, PostgreSQL, Playwright
    """

    mock_ai = MockAIClient(default_response=json.dumps({
        "full_name": "Jane Developer",
        "headline": "Senior Python & AI Engineer",
        "summary": "Passionate backend engineer with 7+ years building scalable systems in Python and Docker.",
        "skills": ["Python", "FastAPI", "Docker", "Kubernetes", "PostgreSQL", "Playwright"],
        "active_search_skills": ["Python", "FastAPI", "Docker"],
        "experience_years": 7.0,
        "target_titles": ["Senior Python Engineer", "Backend Architect"],
        "target_locations": ["Remote", "Germany"],
        "experience_history": [],
        "education": [],
    }))

    extracted = await LinkedInProfileAnalyzer.analyze_profile_text(
        raw_text=raw_linkedin,
        ai_client=mock_ai,
        linkedin_url="https://www.linkedin.com/in/janedev",
    )

    assert extracted.full_name == "Jane Developer"
    assert "FastAPI" in extracted.skills
    assert extracted.experience_years == 7.0
    assert extracted.linkedin_url == "https://www.linkedin.com/in/janedev"


def test_skill_driven_scraper_query_builder():
    """Test generating role + skill query pairs from candidate profile."""
    with Session(engine) as db_session:
        # Create test profile in SQLite
        profile = UserProfile(
            full_name="Sam Smith",
            headline="Fullstack Python Engineer",
            target_titles_json=json.dumps(["Python Developer", "Backend Engineer"]),
            skills_json=json.dumps(["Python", "FastAPI", "Docker", "SQLModel"]),
            active_search_skills_json=json.dumps(["FastAPI", "Docker"]),
            target_locations_json=json.dumps(["Germany", "Remote"]),
        )
        db_session.add(profile)
        db_session.commit()

        queries = ScraperPipeline.build_profile_search_queries(session=db_session)
        assert len(queries) >= 2

        query_texts = [q[1] for q in queries]
        # Primary role
        assert "Python Developer" in query_texts
        # Role + skill combinations
        assert any("FastAPI" in q for q in query_texts)
        assert all(q[2] == "Germany" for q in queries)


def test_web_profile_view_and_form_update(authenticated_client: TestClient):
    """Test rendering the Profile tab and updating via HTML form."""
    # Verify the form reads and writes the registered account's profile.
    resp = authenticated_client.get("/web/views/profile")
    assert resp.status_code == 200
    assert "Candidate Profile" in resp.text or "General Information" in resp.text
    assert "LinkedIn Profile Ingestion" in resp.text

    form_data = {
        "full_name": "Alice Wonderland",
        "headline": "Senior Cloud Engineer",
        "bio": "Building scalable cloud infrastructure.",
        "experience_years": "5.0",
        "target_titles": "Cloud Engineer, Platform Engineer",
        "target_locations": "Remote, Germany",
        "target_salary_min": "80000",
        "work_preference": "remote_first",
        "skills": "Python, AWS, Terraform, Docker",
        "active_skills": ["Python", "AWS"],
    }

    post_resp = authenticated_client.post("/web/profile/update", data=form_data)
    assert post_resp.status_code == 200
    assert "Alice Wonderland" in post_resp.text
    assert "Senior Cloud Engineer" in post_resp.text


def test_web_profile_update_cv_data_and_rescore(authenticated_client: TestClient):
    """Test editing extracted CV data/history and calling rescore & filter."""
    form_data = {
        "full_name": "Charlie Programmer",
        "headline": "Fullstack Developer",
        "bio": "Experienced developer.",
        "experience_years": "4.0",
        "target_titles": "Fullstack Engineer",
        "target_locations": "Remote",
        "target_salary_min": "70000",
        "work_preference": "remote_first",
        "skills": "Python, TypeScript, React",
        "active_skills": ["Python", "React"],
        "experience_history_text": '[{"title": "Lead Dev", "company": "Acme", "duration": "2020-2024", "description": "Built web apps"}]',
        "education_text": '[{"school": "MIT", "degree": "B.Sc.", "field_of_study": "CS"}]',
        "cv_raw_text": "Charlie Programmer - Experienced Fullstack Developer with Python and React skills.",
    }

    post_resp = authenticated_client.post("/web/profile/update", data=form_data)
    assert post_resp.status_code == 200
    assert "Charlie Programmer" in post_resp.text
    assert "Parsed Resume / CV Data & Career History" in post_resp.text

    rescore_resp = authenticated_client.post("/web/profile/rescore-filter")
    assert rescore_resp.status_code == 200
    assert "Rescored and Filtered" in rescore_resp.text


def test_scrape_modal_and_run_routes(authenticated_client: TestClient):
    """Test GET /web/components/scrape-modal and POST /web/scrape/run popup endpoints."""
    resp_modal = authenticated_client.get("/web/components/scrape-modal")
    assert resp_modal.status_code == 200
    assert "Start Job Scraping Discovery" in resp_modal.text
    assert "Start Fresh" in resp_modal.text
    assert "Search More Jobs" in resp_modal.text

    resp_fresh = authenticated_client.post("/web/scrape/run?mode=fresh")
    assert resp_fresh.status_code == 200
    assert "Fresh discovery queued" in resp_fresh.text

    resp_inc = authenticated_client.post("/web/scrape/run?mode=incremental")
    assert resp_inc.status_code == 200
    assert "Incremental search discovery queued" in resp_inc.text


@pytest.mark.asyncio
async def test_ai_bio_generation_function():
    """Verify generate_candidate_bio creates an executive summary using AI/fallback."""
    from app.ai.client import MockAIClient
    from app.ai.profile_extractor import generate_candidate_bio

    mock_client = MockAIClient(default_response="Accomplished Senior Cloud Engineer with 5+ years of experience in AWS and Terraform.")
    
    bio = await generate_candidate_bio(
        profile_data={
            "full_name": "Alice Wonderland",
            "headline": "Senior Cloud Engineer",
            "experience_years": 5.0,
            "target_titles": ["Cloud Engineer"],
            "skills": ["Python", "AWS", "Terraform"],
        },
        ai_client=mock_client,
    )

    assert "Senior Cloud Engineer" in bio or "Alice Wonderland" in bio
    assert len(bio) > 20


def test_web_profile_generate_bio_route(authenticated_client: TestClient):
    """Test POST /web/profile/generate-bio route returns updated textarea HTMX partial."""
    resp = authenticated_client.post(
            "/web/profile/generate-bio",
            data={
                "full_name": "Bob Builder",
                "headline": "DevOps Architect",
                "experience_years": "7.0",
                "target_titles": "DevOps Engineer",
                "skills": "Kubernetes, Docker, Ansible",
                "work_preference": "remote_first",
            },
    )
    assert resp.status_code == 200
    assert "bio-textarea-container" in resp.text
    assert "Generate Bio with AI" in resp.text
    assert "Executive summary generated automatically with AI" in resp.text


def test_linkedin_api_public_id_extraction():
    """Verify extract_public_id_from_url parses usernames correctly from LinkedIn URLs."""
    from app.ai.linkedin_analyzer import extract_public_id_from_url

    assert extract_public_id_from_url("https://www.linkedin.com/in/john-doe-123/") == "john-doe-123"
    assert extract_public_id_from_url("https://de.linkedin.com/in/melta/?sub=1") == "melta"
    assert extract_public_id_from_url("john-doe") == "john-doe"


@pytest.mark.asyncio
async def test_fetch_profile_via_joeyism_scraper_empty_cookie():
    """Verify fetch_profile_via_joeyism_scraper handles empty inputs safely without throwing."""
    res = await LinkedInProfileAnalyzer.fetch_profile_via_joeyism_scraper(
        linkedin_url="https://www.linkedin.com/in/test-invalid",
        session_cookie="",
    )
    assert res is None
