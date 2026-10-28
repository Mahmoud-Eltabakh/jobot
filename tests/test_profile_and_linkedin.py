"""Unit and integration tests for Profile Management, LinkedIn Analysis, and Skill-Driven Scraping."""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.ai.client import MockAIClient, OllamaAIClient
from app.ai.client import AIProviderError
from app.ai.embeddings import ProfileEmbedder
from app.ai.linkedin_analyzer import LinkedInProfileAnalyzer
from app.ai.profile_extractor import ExtractedProfile
from app.db.database import engine, init_db
from app.db.models import UserProfile
from app.db.vector import get_vector_store
from app.scrapers.scheduler import ScraperPipeline


@pytest.fixture(autouse=True)
def setup_db(monkeypatch) -> None:
    init_db()
    monkeypatch.setattr(OllamaAIClient, "generate", AsyncMock(return_value="A professional executive summary grounded in the supplied candidate background."))
    monkeypatch.setattr(OllamaAIClient, "embed", AsyncMock(return_value=[1.0, 0.0]))


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
        experience_history=[{"title": "Backend Engineer", "company": "Acme", "duration": "2020-2024", "description": "Built Kafka pipelines"}],
    )

    chunks = ProfileEmbedder.chunk_profile(profile)
    assert len(chunks) == 4
    chunk_types = [c["metadata"]["chunk_type"] for c in chunks]
    assert "summary" in chunk_types
    assert "skills" in chunk_types
    assert "experience" in chunk_types
    history = next(c for c in chunks if c["metadata"]["chunk_type"] == "history")
    assert "Acme" in history["text"] and "Kafka pipelines" in history["text"]
    profile.experience_history = []
    assert len(ProfileEmbedder.chunk_profile(profile)) == 3
    profile.experience_history = [{"title": "Backend Engineer", "company": "Acme", "duration": "2020-2024", "description": "Built Kafka pipelines"}]

    vector_store = get_vector_store()
    mock_ai = MockAIClient()

    stored_count = await ProfileEmbedder.embed_and_store_profile(
        profile=profile,
        vector_store=vector_store,
        ai_client=mock_ai,
    )
    assert stored_count == 4


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
    assert "Import LinkedIn Profile PDF" in resp.text

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
    """Test GET /web/components/scrape-modal and POST /web/scrape/run popup endpoints with location and work type from UI."""
    resp_modal = authenticated_client.get("/web/components/scrape-modal")
    assert resp_modal.status_code == 200
    assert "Start Job Scraping Discovery" in resp_modal.text
    assert "Target Location(s)" in resp_modal.text
    assert "Work Type / Model" in resp_modal.text
    assert "Start Fresh" in resp_modal.text
    assert "Search More Jobs" in resp_modal.text

    resp_fresh = authenticated_client.post(
        "/web/scrape/run?mode=fresh",
        data={"target_locations": "Berlin, Germany", "work_preference": "remote_first"},
    )
    assert resp_fresh.status_code == 200
    assert "Fresh discovery queued" in resp_fresh.text

    resp_inc = authenticated_client.post(
        "/web/scrape/run?mode=incremental",
        data={"target_locations": "Frankfurt", "work_preference": "hybrid"},
    )
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


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["bio", "cv", "linkedin"])
async def test_profile_generation_provider_errors_are_not_success(operation):
    """Private-profile operations must not turn provider failure into invented content."""
    from app.ai.profile_extractor import generate_candidate_bio, extract_profile_from_text
    client = MockAIClient()
    client.generate = AsyncMock(side_effect=AIProviderError("openai", "gpt-4o-mini", "quota", status_code=402))
    with pytest.raises(AIProviderError):
        if operation == "bio":
            await generate_candidate_bio({"full_name": "Private Owner"}, client)
        elif operation == "cv":
            await extract_profile_from_text("Private Owner\nSkills: Python", client)
        else:
            await LinkedInProfileAnalyzer.analyze_profile_text("Private Owner\nSkills: Python", client)


def test_profile_partial_embedding_failure_is_truthful(authenticated_client, monkeypatch):
    """A durable profile save is distinguishable from failed local vector synchronization."""
    monkeypatch.setattr(ProfileEmbedder, "embed_and_store_profile", AsyncMock(side_effect=AIProviderError("ollama", "nomic-embed-text", "unavailable")))
    response = authenticated_client.post("/api/profile/update", json={"full_name": "Saved Owner", "skills": ["Python"]})
    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert response.json()["embeddings_synced"] is False
    assert authenticated_client.get("/api/profile").json()["profile"]["full_name"] == "Saved Owner"


def test_profile_api_and_web_factories_are_owner_scoped(authenticated_client, authenticated_user, monkeypatch):
    """Both bio surfaces use scraping and every profile vector call carries its owner."""
    from app.api import profile as api
    from app.web import routes as web
    from app.ai.client import get_embedding_client
    generation = MockAIClient(default_response="An accurate owner-specific professional biography.")
    calls = []

    def factory(session=None, user_id=None, *, task_type="scoring"):
        assert isinstance(session, Session)
        assert user_id == authenticated_user["id"]
        calls.append(task_type)
        return generation

    def vectors(session=None, user_id=None):
        assert isinstance(session, Session)
        assert user_id == authenticated_user["id"]
        return get_embedding_client(session, user_id)

    monkeypatch.setattr(api, "get_ai_client", factory)
    monkeypatch.setattr(web, "get_ai_client", factory)
    monkeypatch.setattr(api, "get_embedding_client", vectors)
    monkeypatch.setattr(web, "get_embedding_client", vectors)
    assert authenticated_client.post("/api/profile/update", json={"full_name": "Scoped Owner", "skills": ["Python"]}).json()["embeddings_synced"] is True
    assert authenticated_client.post("/api/profile/generate-bio").status_code == 200
    assert authenticated_client.post("/web/profile/generate-bio").status_code == 200
    assert calls == ["scraping", "scraping"]


def test_profile_bio_failure_is_safe_and_preserves_old_bio(authenticated_client, monkeypatch):
    from app.api import profile as api
    def fail(*args, **kwargs):
        raise AIProviderError("openai", "gpt-4o-mini", "quota", 402)
    monkeypatch.setattr(api, "get_ai_client", fail)
    old = authenticated_client.get("/api/profile").json()["profile"]["bio"]
    response = authenticated_client.post("/api/profile/generate-bio")
    assert response.status_code == 502
    assert response.json()["detail"]["category"] == "quota"
    assert authenticated_client.get("/api/profile").json()["profile"]["bio"] == old


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", ["{}", "[]", "not-json"])
@pytest.mark.parametrize("surface", ["cv", "linkedin"])
async def test_profile_invalid_generation_is_not_an_empty_success(payload, surface):
    from app.ai.profile_extractor import extract_profile_from_text
    client = MockAIClient(default_response=payload)
    with pytest.raises(AIProviderError):
        if surface == "cv":
            await extract_profile_from_text("Private candidate text", client)
        else:
            await LinkedInProfileAnalyzer.analyze_profile_text("Private candidate text", client)


def test_linkedin_sync_routes_owner_generation_and_local_vectors(authenticated_client, authenticated_user, monkeypatch):
    from app.ai import linkedin_analyzer as analyzer
    generation = MockAIClient(default_response=json.dumps({"full_name": "Scoped LinkedIn Owner", "summary": "An accurate professional summary based on the owner's submitted experience.", "skills": ["Python"]}))
    local = object()
    calls = []
    def factory(session=None, user_id=None, *, task_type="scoring"):
        assert user_id == authenticated_user["id"]
        assert isinstance(session, Session)
        calls.append(task_type)
        return generation
    def vectors(session=None, user_id=None):
        assert user_id == authenticated_user["id"]
        calls.append("embeddings")
        return local
    monkeypatch.setattr(analyzer, "get_ai_client", factory)
    monkeypatch.setattr(analyzer, "get_embedding_client", vectors)
    embed = AsyncMock(return_value=3)
    monkeypatch.setattr(ProfileEmbedder, "embed_and_store_profile", embed)
    response = authenticated_client.post("/api/profile/linkedin/sync", json={"linkedin_url": "https://www.linkedin.com/in/owner", "raw_text_override": "Owner supplied profile"})
    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "Scoped LinkedIn Owner"
    assert calls == ["scraping", "embeddings"]
    assert embed.await_args.kwargs["embedding_client"] is local
    assert embed.await_args.kwargs["user_id"] == authenticated_user["id"]


def test_linkedin_vector_failure_preserves_profile(authenticated_client, monkeypatch):
    from app.ai import linkedin_analyzer as analyzer
    generation = MockAIClient(default_response=json.dumps({"full_name": "Do Not Save", "summary": "A complete valid profile summary grounded in the supplied experience.", "skills": ["Python"]}))
    monkeypatch.setattr(analyzer, "get_ai_client", lambda *args, **kwargs: generation)
    monkeypatch.setattr(ProfileEmbedder, "embed_and_store_profile", AsyncMock(side_effect=AIProviderError("ollama", "nomic-embed-text", "unavailable")))
    old = authenticated_client.get("/api/profile").json()["profile"]["full_name"]
    response = authenticated_client.post("/api/profile/linkedin/sync", json={"linkedin_url": "https://www.linkedin.com/in/owner", "raw_text_override": "Owner supplied profile"})
    assert response.status_code == 503
    assert authenticated_client.get("/api/profile").json()["profile"]["full_name"] == old


def test_web_profile_update_persists_linkedin_text_and_rejects_bad_json(authenticated_client: TestClient):
    """LinkedIn panel edits are saved; malformed history JSON surfaces an error and saves nothing."""
    from app.db.ownership import decrypt_profile

    base = {
        "full_name": "Dana Dev", "target_titles": "Engineer", "skills": "Python",
        "experience_years": "3", "work_preference": "remote_first",
    }
    ok = authenticated_client.post("/web/profile/update", data={**base, "linkedin_raw_text": "Dana LinkedIn export text"})
    assert ok.status_code == 200
    with Session(engine) as session:
        profile = session.exec(select(UserProfile)).first()
        assert decrypt_profile(profile, profile.user_id).linkedin_raw_text == "Dana LinkedIn export text"

    bad = authenticated_client.post(
        "/web/profile/update",
        data={**base, "full_name": "Changed Name", "projects_text": '[{"name": "x"'},
    )
    assert bad.status_code == 200
    assert "not valid JSON" in bad.text
    with Session(engine) as session:
        assert session.exec(select(UserProfile)).first().full_name == "Dana Dev"


def test_save_profile_to_db_merges_second_source_without_overwrite():
    from app.ai.profile_extractor import save_profile_to_db

    cv = ExtractedProfile(
        full_name="Eve", skills=["Python"],
        experience_history=[{"title": "Dev", "company": "Acme"}],
        education=[{"school": "MIT", "degree": "BSc"}],
        projects=[{"name": "Alpha"}],
    )
    linkedin = ExtractedProfile(
        full_name="Eve", skills=["Go"],
        experience_history=[{"title": "Dev", "company": "Acme"}, {"title": "Lead", "company": "Beta"}],
        education=[{"school": "MIT", "degree": "BSc"}, {"school": "TUM", "degree": "MSc"}],
        projects=[{"name": "Alpha"}, {"name": "Beta"}],
    )
    with Session(engine) as session:
        save_profile_to_db(cv, "cv text", session, source_type="cv")
        save_profile_to_db(linkedin, "li text", session, source_type="linkedin")
    with Session(engine) as session:
        p = session.exec(select(UserProfile)).first()
        assert json.loads(p.skills_json) == ["Python", "Go"]
        assert [h["company"] for h in json.loads(p.experience_history_json)] == ["Acme", "Beta"]
        assert [e["school"] for e in json.loads(p.education_json)] == ["MIT", "TUM"]
        assert [x["name"] for x in json.loads(p.projects_json)] == ["Alpha", "Beta"]
        assert p.cv_raw_text == "cv text" and p.linkedin_raw_text == "li text"


# ---- Phase 7 gap closure: history embedding, production query matrix, tag editor ----

def test_web_profile_save_embeds_experience_history(authenticated_client, monkeypatch):
    spy = AsyncMock(return_value=4)
    monkeypatch.setattr(ProfileEmbedder, "embed_and_store_profile", spy)
    history = json.dumps([{"title": "Dev", "company": "Acme", "duration": "2020", "description": "APIs"}])
    resp = authenticated_client.post("/web/profile/update", data={
        "full_name": "Hist User", "target_titles": "Python Developer", "experience_history_text": history,
    })
    assert resp.status_code == 200
    assert spy.await_args.args[0].experience_history[0]["company"] == "Acme"

    # A later save without history text still embeds the stored history
    authenticated_client.post("/web/profile/update", data={"full_name": "Hist User", "target_titles": "Python Developer"})
    assert spy.await_args.args[0].experience_history[0]["company"] == "Acme"


def test_api_profile_update_embeds_stored_history(authenticated_client, monkeypatch):
    authenticated_client.post("/web/profile/update", data={
        "full_name": "Api User", "target_titles": "Dev",
        "experience_history_text": json.dumps([{"title": "Dev", "company": "Globex"}]),
    })
    spy = AsyncMock(return_value=4)
    monkeypatch.setattr(ProfileEmbedder, "embed_and_store_profile", spy)
    resp = authenticated_client.post("/api/profile/update", json={"full_name": "Api User", "target_titles": ["Dev"]})
    assert resp.json()["status"] == "ok"
    assert spy.await_args.args[0].experience_history[0]["company"] == "Globex"


@pytest.mark.asyncio
async def test_full_discovery_enqueues_profile_matrix_with_ai_queries(authenticated_client, authenticated_user, monkeypatch):
    from app.queue.worker import QueueWorker
    from app.db.models import ScrapeTask
    from app.scrapers.query_strategist import AIQueryStrategist

    authenticated_client.post("/api/profile/update", json={
        "full_name": "Q User", "target_titles": ["Python Developer"], "skills": ["FastAPI", "Docker"],
        "target_locations": ["Berlin"],
    })
    monkeypatch.setattr(
        AIQueryStrategist, "generate_search_queries",
        AsyncMock(return_value=[("linkedin", "AI Strategist Query", "Berlin"), ("all", "python developer", "Berlin")]),
    )
    with Session(engine) as session:
        await QueueWorker(ai_client=MockAIClient())._handle_full_discovery({}, session, authenticated_user["id"])
        keywords = [json.loads(t.payload_json)["keywords"] for t in session.exec(select(ScrapeTask)).all()]
    assert "AI Strategist Query" in keywords
    assert "Python Developer FastAPI" in keywords
    assert len([k for k in keywords if k.lower() == "python developer"]) == 1  # deduplicated


def test_target_titles_tag_editor_rendered(authenticated_client):
    authenticated_client.post("/web/profile/update", data={"full_name": "Tag User", "target_titles": "Backend Engineer, Cloud Architect"})
    html = authenticated_client.get("/web/views/profile").text
    assert 'id="titles-editor"' in html
    assert 'name="target_titles" id="target-titles-value" value="Backend Engineer, Cloud Architect"' in html
