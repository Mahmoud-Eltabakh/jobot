"""End-to-end integration workflow test verifying the entire Jobot pipeline."""

import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.ai.client import AIProviderError, MockAIClient, get_ai_client
from app.ai.embeddings import ProfileEmbedder
from app.ai.evaluator import JobEvaluator
from app.ai.feedback import FeedbackManager
from app.ai.profile_extractor import ExtractedProfile
from app.db.database import engine, init_db
from app.db.models import ApplicationMaterial, FilterRule, Job, JobStatus, ScrapeTask, UserProfile, UserSetting
from app.db.vector import VectorStore
from app.main import app
from app.queue.task_queue import TaskQueue
from app.queue.worker import QueueWorker
from app.scrapers.base import ScrapedJob
from app.scrapers.dedup import save_scraped_jobs
from app.scrapers.filter_pipeline import JobFilterPipeline


@pytest.fixture(autouse=True)
def setup_clean_state() -> None:
    init_db()


@pytest.mark.asyncio
async def test_full_pipeline_e2e_workflow(tmp_path) -> None:
    """Test full workflow: Scraping -> Dedup -> Filter -> Vector RAG -> Fit Score -> Feedback -> Re-scoring."""
    ai_client = MockAIClient()
    vector_store = VectorStore(str(tmp_path / "legacy-workflow-vectors"))
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
            embedding_client=ai_client,
        )
        assert doc_id is not None
        assert vector_store.count(VectorStore.COLLECTION_USER_FEEDBACK) >= 1

        # 7. Adaptive Re-weighting calculation with identical feedback text
        exact_doc_text = f"Title: {good_job_db.title}\nCompany: {good_job_db.company}\nLocation: {good_job_db.location}\nStatus: {JobStatus.APPLIED.value}\nCandidate Note: Loved the tech stack FastAPI and Docker remote setup\nDescription snippet: {good_job_db.description[:400]}"
        delta, reasons = await FeedbackManager.compute_feedback_score_adjustment(
            job_text=exact_doc_text,
            vector_store=vector_store,
            ai_client=ai_client,
            embedding_client=ai_client,
        )
        # Should receive positive fit bonus
        assert delta > 0


def test_web_ui_dashboard_e2e_interaction(
    authenticated_client: TestClient,
    authenticated_user: dict,
) -> None:
    """Verify Web Dashboard displays jobs and allows status updates via API/HTMX."""
    timestamp = int(time.time() * 1000)

    # Insert a unique job
    with Session(engine) as session:
        job = Job(
            user_id=authenticated_user["id"],
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
    res_home = authenticated_client.get("/")
    assert res_home.status_code == 200
    assert "Jobot" in res_home.text

    # 2. Verify GET /web/views/kanban
    res_kanban = authenticated_client.get("/web/views/kanban")
    assert res_kanban.status_code == 200
    assert "Fullstack Python Engineer" in res_kanban.text

    # 3. Verify GET /web/views/table
    res_table = authenticated_client.get("/web/views/table")
    assert res_table.status_code == 200
    assert "ModernStack" in res_table.text

    # 4. Verify PUT /api/jobs/{id}/status via Form data
    res_update = authenticated_client.put(f"/api/jobs/{job_id}/status", data={"new_status": "1. interview"})
    assert res_update.status_code == 200


@pytest.fixture(scope="module")
def workflow_vectors(tmp_path_factory):
    """One disposable Chroma client avoids exhausting its process-wide segment cache."""
    return VectorStore(str(tmp_path_factory.mktemp("phase17-workflow-vectors")))


@pytest.fixture
def routed_workflow(authenticated_client, authenticated_user, provider_transport, workflow_vectors, monkeypatch):
    """Real saved owner routes and vector stores; only the HTTP boundary is fake.

    A request to any unassigned host/path fails, including cloud embeddings.
    Distinct response schemas keep discovery, scoring and applying observable.
    No worker loop or live provider service starts in this fixture.
    """
    owner = authenticated_user["id"]
    assignments = {"scraping": "anthropic", "scoring": "groq", "applying": "gemini"}
    values = {f"task_{stage}_{field}": provider if field == "provider" else f"owned-{stage}"
              for stage, provider in assignments.items() for field in ("provider", "model")}
    values.update({f"provider_{provider}_key": f"private-{provider}-key" for provider in assignments.values()})
    values.update(ollama_base_url="http://owner-local.invalid:11434", ollama_model="owner-local-model",
                  provider_ollama_key="private-local-key")
    response = authenticated_client.post("/api/settings/ai", data=values)
    assert response.status_code == 200, response.text
    store = workflow_vectors
    for collection_name in (VectorStore.COLLECTION_CV_PROFILE, VectorStore.COLLECTION_USER_FEEDBACK):
        records = store.get_or_create_collection(collection_name).get()["ids"]
        if records:
            store.delete_documents(collection_name, records)
    monkeypatch.setattr("app.ai.evaluator.get_vector_store", lambda: store)
    requests = []
    state = {"failure": None, "dimension": 2}
    evaluation = {"fit_score": 87, "fit_summary": "Verified Python match", "pros": ["Python"],
                  "cons": [], "missing_skills": [], "recommendation": "Strong Match"}

    def respond(request):
        payload = json.loads(request.content)
        host, path = request.url.host, request.url.path
        requests.append((host, path, payload, dict(request.headers)))
        assert request.method == "POST"
        if host == "owner-local.invalid" and path == "/api/embeddings":
            assert request.headers["authorization"] == "Bearer private-local-key"
            assert payload["model"] == "nomic-embed-text"
            if state["failure"] == "vector-timeout":
                raise httpx.ReadTimeout("private-local-key raw response", request=request)
            return httpx.Response(200, json={"embedding": [1.0] + [0.0] * (state["dimension"] - 1)})
        if state["failure"] in (429, 402) and host in ("api.groq.com", "generativelanguage.googleapis.com"):
            return httpx.Response(state["failure"], json={"error": {"message": "private-groq-key private-gemini-key <script>hostile</script>"}})
        if state["failure"] == "timeout" and host in ("api.groq.com", "generativelanguage.googleapis.com"):
            raise httpx.ReadTimeout("private-groq-key private-gemini-key raw response", request=request)
        if host == "api.anthropic.com" and path == "/v1/messages":
            assert request.headers["x-api-key"] == "private-anthropic-key"
            assert payload["model"] == "owned-scraping"
            content = json.dumps({"queries": [{"platform": "linkedin", "keywords": "Python Engineer", "location": "Remote"}]})
            return httpx.Response(200, json={"stop_reason": "end_turn", "content": [{"type": "text", "text": content}]})
        if host == "api.groq.com" and path == "/openai/v1/chat/completions":
            assert request.headers["authorization"] == "Bearer private-groq-key"
            assert payload["model"] == "owned-scoring"
            return httpx.Response(200, json={"id": "score", "object": "chat.completion", "created": 0,
                "model": payload["model"], "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(evaluation)}}]})
        if host == "generativelanguage.googleapis.com" and path == "/v1beta/models/owned-applying:generateContent":
            assert request.headers["x-goog-api-key"] == "private-gemini-key"
            return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "Owned generated application"}]}}]})
        if host == "owner-local.invalid" and path == "/api/chat":
            assert payload["model"] == "owner-local-model"
            return httpx.Response(200, json={"message": {"role": "assistant", "content": json.dumps(evaluation)}})
        pytest.fail(f"Unexpected provider destination: {host}{path}")

    provider_transport(respond)
    with Session(engine) as session:
        session.add(UserProfile(user_id=owner, full_name="Private Candidate", skills_json='["Python"]',
                                bio="Private Python history", target_titles_json='["Python Engineer"]'))
        job = Job(user_id=owner, source="test", title="Python Engineer", company="Example", location="Remote",
                  url="https://example.test/owned", description="Python backend engineering", dedup_hash="routed-e2e",
                  fit_score=71, fit_summary="Prior saved score")
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id
    return authenticated_client, owner, job_id, store, state, requests


def _vector_snapshot(store):
    """Include vector values, not merely counts, in non-destructive assertions."""
    snapshots = {}
    for collection in (VectorStore.COLLECTION_CV_PROFILE, VectorStore.COLLECTION_USER_FEEDBACK):
        data = store.get_or_create_collection(collection).get(include=["documents", "embeddings", "metadatas"])
        snapshots[collection] = (data["ids"], data["documents"], data["metadatas"],
                                 data["embeddings"].tolist() if len(data["ids"]) else [])
    return snapshots


@pytest.mark.asyncio
async def test_saved_three_stage_workflow_and_all_vectors_use_owner_transports(routed_workflow):
    client, owner, job_id, store, state, requests = routed_workflow
    with Session(engine) as session:
        cloud = get_ai_client(session, owner, task_type="scoring")
        count = await ProfileEmbedder.embed_and_store_profile(
            ExtractedProfile(full_name="Private Candidate", skills=["Python"]), store, cloud,
            session=session, user_id=owner,
        )
        assert count == 3
        assert await ProfileEmbedder.compute_semantic_similarity("Python", store, cloud, session=session, user_id=owner) == 1.0
        assert await FeedbackManager.record_job_feedback(job_id, "applied", "Private note", session, store, cloud, user_id=owner)
        delta, reasons = await FeedbackManager.compute_feedback_score_adjustment("Python", store, cloud, session=session, user_id=owner)
        assert delta == 10 and reasons
        discovery = TaskQueue.enqueue(session, "full_discovery", {}, user_id=owner)
        score = TaskQueue.enqueue(session, "evaluate_job", {"job_id": job_id}, user_id=owner)
        worker = QueueWorker()
        await worker._process_task(discovery, session)
        await worker._process_task(score, session)
        assert discovery.status == score.status == "completed"
        assert session.get(Job, job_id).fit_score == 87
        searches = session.exec(select(ScrapeTask).where(ScrapeTask.task_type == "scrape_query")).all()
        assert len(searches) == 1 and searches[0].user_id == owner
        assert json.loads(searches[0].payload_json)["keywords"] == "Python Engineer"
    for path in (f"/api/jobs/{job_id}/cover-letter/generate", f"/api/jobs/{job_id}/tailor-resume/generate"):
        response = client.post(path, json={"tone": "direct"})
        assert response.status_code == 200, response.text
        assert response.json()["content_markdown"] == "Owned generated application"
    response = client.post(f"/web/job/{job_id}/cover-letter/generate", data={"tone": "professional"})
    assert response.status_code == 200 and "Owned generated application" in response.text
    generations = [(host, payload.get("model")) for host, path, payload, headers in requests if path != "/api/embeddings"]
    assert generations == [("api.anthropic.com", "owned-scraping"), ("api.groq.com", "owned-scoring"),
                            *[("generativelanguage.googleapis.com", None)] * 3]
    vectors = [entry for entry in requests if entry[1] == "/api/embeddings"]
    assert len(vectors) == 8
    assert all(host == "owner-local.invalid" and payload["model"] == "nomic-embed-text" for host, path, payload, headers in vectors)
    with Session(engine) as session:
        materials = session.exec(select(ApplicationMaterial)).all()
        assert len(materials) == 2 and all(material.user_id == owner for material in materials)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,category,status", [(429, "rate_limit", 429), (402, "quota", 402),
    ("timeout", "timeout", None), ("dimension", "embedding_dimension", None)])
async def test_failure_preservation_and_separate_owned_local_switch_retry(routed_workflow, failure, category, status, caplog):
    client, owner, job_id, store, state, requests = routed_workflow
    with TestClient(app) as other_client:
        registration = other_client.post("/api/auth/register", json={"email": "recovery-other@example.com", "password": "OtherPassword123", "full_name": "Other"})
        assert registration.status_code == 200
        other = registration.json()["id"]
        assert other_client.post("/api/settings/ai", data={"ollama_base_url": "http://other-local.invalid:11434", "task_scoring_model": "other-choice"}).status_code == 200
        with Session(engine) as session:
            session.add(ApplicationMaterial(user_id=owner, job_id=job_id, material_type="cover_letter", content_markdown="Prior material"))
            session.commit()
            task = TaskQueue.enqueue(session, "evaluate_job", {"job_id": job_id}, user_id=owner)
            task_id = task.id
            await ProfileEmbedder.embed_and_store_profile(ExtractedProfile(full_name="Before", skills=["Python"]), store, session=session, user_id=owner)
        before_vectors = _vector_snapshot(store)
        with Session(engine) as session:
            before_settings = {row.key: row.value_json for row in session.exec(select(UserSetting).where(UserSetting.user_id == owner)).all()}
            before_other = {row.key: row.value_json for row in session.exec(select(UserSetting).where(UserSetting.user_id == other)).all()}
            before_job = session.get(Job, job_id).model_dump()
            before_material = session.exec(select(ApplicationMaterial)).one().model_dump()
            state["failure"] = None if failure == "dimension" else failure
            state["dimension"] = 3 if failure == "dimension" else 2
            await QueueWorker()._process_task(session.get(ScrapeTask, task_id), session)
            failed = session.get(ScrapeTask, task_id)
            assert failed.status == "failed"
            diagnostic = json.loads(failed.error_message)
            assert diagnostic["category"] == category and diagnostic["status_code"] == status
            assert session.get(Job, job_id).model_dump() == before_job
        request_count = len(requests)
        if failure != "dimension":
            for path in (f"/api/jobs/{job_id}/cover-letter/generate", f"/api/jobs/{job_id}/tailor-resume/generate", f"/web/job/{job_id}/cover-letter/generate"):
                response = client.post(path, json={})
                assert response.status_code == 502 and category in response.text
                assert "private-" not in response.text
            assert len(requests) == request_count + 3
        assert _vector_snapshot(store) == before_vectors
        with Session(engine) as session:
            assert session.exec(select(ApplicationMaterial)).one().model_dump() == before_material
        count_before_switch = len(requests)
        assert other_client.post(f"/web/queue/tasks/{task_id}/retry").status_code == 404
        assert other_client.post(f"/api/jobs/{job_id}/cover-letter/generate", json={}).status_code == 404
        assert client.post("/api/settings/ai/preset", data={"preset": "local"}).status_code == 200
        assert len(requests) == count_before_switch
        with Session(engine) as session:
            after = {row.key: row.value_json for row in session.exec(select(UserSetting).where(UserSetting.user_id == owner)).all()}
            changed = {key for key in after if after[key] != before_settings.get(key)}
            assert changed == {f"task_{stage}_{field}" for stage in ("scraping", "scoring", "applying") for field in ("provider", "model")}
            assert {row.key: row.value_json for row in session.exec(select(UserSetting).where(UserSetting.user_id == other)).all()} == before_other
            assert session.get(ScrapeTask, task_id).status == "failed"
        assert client.post(f"/web/queue/tasks/{task_id}/retry").status_code == 200
        assert len(requests) == count_before_switch
        state.update(failure=None, dimension=2)
        with Session(engine) as session:
            claimed = TaskQueue.claim_next_task(session, ["evaluate_job"])
            assert claimed.id == task_id and claimed.user_id == owner
            await QueueWorker()._process_task(claimed, session)
            assert claimed.status == "completed"
            assert session.get(Job, job_id).fit_score == 87
        assert requests[-1][0:2] == ("owner-local.invalid", "/api/chat")
        assert "private-" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["profile", "similarity", "feedback_write", "feedback_query"])
@pytest.mark.parametrize("failure", ["vector-timeout", "dimension"])
async def test_all_local_vector_failure_paths_preserve_data(routed_workflow, operation, failure):
    client, owner, job_id, store, state, requests = routed_workflow
    with Session(engine) as session:
        profile = ExtractedProfile(full_name="Original", skills=["Python"])
        await ProfileEmbedder.embed_and_store_profile(profile, store, session=session, user_id=owner)
        await FeedbackManager.record_job_feedback(job_id, "applied", "Original note", session, store, user_id=owner)
        before = _vector_snapshot(store)
        before_job = session.get(Job, job_id).model_dump()
        state.update(failure=failure, dimension=3 if failure == "dimension" else 2)
        requests.clear()
        with pytest.raises(AIProviderError) as caught:
            if operation == "profile":
                await ProfileEmbedder.embed_and_store_profile(profile, store, session=session, user_id=owner)
            elif operation == "similarity":
                await ProfileEmbedder.compute_semantic_similarity("Changed", store, session=session, user_id=owner)
            elif operation == "feedback_write":
                await FeedbackManager.record_job_feedback(job_id, "rejected", "Changed note", session, store, user_id=owner)
            else:
                await FeedbackManager.compute_feedback_score_adjustment("Changed", store, session=session, user_id=owner)
        assert caught.value.category == ("embedding_dimension" if failure == "dimension" else "timeout")
        assert _vector_snapshot(store) == before
        assert session.get(Job, job_id).model_dump() == before_job
        assert requests and all(entry[0:2] == ("owner-local.invalid", "/api/embeddings") for entry in requests)
