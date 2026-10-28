"""Integration and unit tests for parallel multi-source scraping and concurrent AI scoring."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.ai.client import MockAIClient
from app.db.database import engine, init_db, get_app_setting, get_user_setting
from app.db.models import Job, ScrapeTask
from app.queue.task_queue import TaskQueue
from app.queue.worker import QueueWorker
from app.scrapers.base import ScrapedJob
from app.scrapers.jobspy_scraper import JobSpyScraper
from app.scrapers.scheduler import ScraperPipeline


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def test_task_queue_type_specific_claiming():
    """Verify TaskQueue.claim_next_task isolates tasks by type for decoupled worker loops."""
    with Session(engine) as session:
        # Enqueue 1 scraping task and 1 evaluation task
        t_scrape = TaskQueue.enqueue(
            session=session,
            task_type="scrape_query",
            payload={"keywords": "Python", "location": "Remote"},
        )
        t_eval = TaskQueue.enqueue(
            session=session,
            task_type="evaluate_job",
            payload={"job_id": 101},
        )

        # 1. Scraper loop should claim only scrape_query / full_discovery
        claimed_scrape = TaskQueue.claim_next_task(session, task_types=["scrape_query", "full_discovery"])
        assert claimed_scrape is not None
        assert claimed_scrape.id == t_scrape.id
        assert claimed_scrape.task_type == "scrape_query"

        # 2. Evaluator loop should claim only evaluate_job / feedback_tune
        claimed_eval = TaskQueue.claim_next_task(session, task_types=["evaluate_job", "feedback_tune"])
        assert claimed_eval is not None
        assert claimed_eval.id == t_eval.id
        assert claimed_eval.task_type == "evaluate_job"

        # 3. No more tasks should remain pending
        assert TaskQueue.claim_next_task(session) is None


@pytest.mark.asyncio
async def test_jobspy_multi_site_parallel_scraping():
    """Verify JobSpyScraper scrapes multiple sites concurrently in parallel threads."""
    scraper = JobSpyScraper(default_sites=["linkedin", "google"])

    mock_linkedin_job = ScrapedJob(
        source="linkedin",
        title="Backend Engineer",
        company="LinkedIn Corp",
        location="Remote",
        url="https://linkedin.com/jobs/view/1001",
        description="Python backend position.",
    )
    mock_google_job = ScrapedJob(
        source="google",
        title="Software Engineer",
        company="Google LLC",
        location="Remote",
        url="https://google.com/jobs/view/1002",
        description="Cloud engineering position.",
    )

    with patch.object(JobSpyScraper, "_sync_scrape") as mock_sync:
        def side_effect(search_term, location, results_wanted, site_name, is_remote, hours_old, country_indeed):
            if "linkedin" in site_name:
                return [mock_linkedin_job]
            elif "google" in site_name:
                return [mock_google_job]
            return []

        mock_sync.side_effect = side_effect

        results = await scraper.scrape(
            search_term="Python",
            location="Remote",
            site_name=["linkedin", "google"],
        )

        assert len(results) == 2
        sources = {j.source for j in results}
        assert "linkedin" in sources
        assert "google" in sources
        assert mock_sync.call_count == 2


@pytest.mark.asyncio
async def test_queue_worker_parallel_multi_source_scrape_handling():
    """Verify QueueWorker._handle_scrape_query executes all target websites in parallel."""
    mock_linkedin = ScrapedJob(
        source="linkedin",
        title="FastAPI Engineer",
        company="Alpha Corp",
        location="Berlin",
        url="https://linkedin.com/jobs/view/2001",
        description="FastAPI role.",
    )
    mock_stepstone = ScrapedJob(
        source="stepstone",
        title="Python Developer",
        company="Beta GmbH",
        location="Munich",
        url="https://stepstone.de/jobs/2002",
        description="Python developer position.",
    )

    with (
        patch("app.scrapers.jobspy_scraper.JobSpyScraper.scrape", new_callable=AsyncMock) as mock_js,
        patch("app.scrapers.stepstone.StepStoneScraper.scrape", new_callable=AsyncMock) as mock_ss,
    ):
        mock_js.return_value = [mock_linkedin]
        mock_ss.return_value = [mock_stepstone]

        worker = QueueWorker()
        payload = {"platform": "all", "keywords": "Python", "location": "Germany"}

        with Session(engine) as session:
            await worker._handle_scrape_query(payload, session, user_id=None)

            # Check that newly scraped jobs were inserted and evaluate_job tasks were enqueued
            jobs = session.exec(select(Job)).all()
            assert len(jobs) == 2

            eval_tasks = session.exec(
                select(ScrapeTask).where(ScrapeTask.task_type == "evaluate_job")
            ).all()
            assert len(eval_tasks) == 2


@pytest.mark.asyncio
async def test_scraper_pipeline_parallel_batch_scoring(monkeypatch, tmp_path):
    """Verify ScraperPipeline executes multi-source scraping and batch AI scoring in parallel."""
    mock_jobs = [
        ScrapedJob(
            source="linkedin",
            title="Senior Architect",
            company="TechCorp",
            location="Remote",
            url="https://linkedin.com/jobs/view/3001",
            description="Python architect role.",
        ),
        ScrapedJob(
            source="stepstone",
            title="Lead Developer",
            company="EuroTech",
            location="Frankfurt",
            url="https://stepstone.de/jobs/3002",
            description="Lead Python engineer.",
        ),
    ]

    mock_ai = MockAIClient(default_response=json.dumps({
        "fit_score": 88,
        "fit_summary": "Strong match for candidate.",
        "pros": ["Architecture skills"],
        "cons": [],
        "missing_skills": [],
        "recommendation": "Strong Match",
    }))
    monkeypatch.setattr("app.ai.evaluator.get_embedding_client", lambda *args, **kwargs: mock_ai)
    # Private Chroma store avoids embedding_dimension clashes with other tests' shared collections
    from app.db.vector import VectorStore
    store = VectorStore(str(tmp_path / "vectors"))
    monkeypatch.setattr("app.ai.evaluator.get_vector_store", lambda: store)

    with (
        patch("app.scrapers.jobspy_scraper.JobSpyScraper.scrape", new_callable=AsyncMock) as mock_js,
        patch("app.scrapers.stepstone.StepStoneScraper.scrape", new_callable=AsyncMock) as mock_ss,
    ):
        mock_js.return_value = [mock_jobs[0]]
        mock_ss.return_value = [mock_jobs[1]]

        with Session(engine) as session:
            stats = await ScraperPipeline.run_full_pipeline(
                session=session,
                ai_client=mock_ai,
                override_keywords="Python",
                override_location="Remote",
            )

            assert stats["scraped_total"] == 2
            assert stats["new_inserted"] == 2
            assert stats["ai_evaluated"] == 2


def test_concurrency_settings_api_and_ui(authenticated_client: TestClient, authenticated_user: dict):
    """Test updating worker concurrency settings via API and rendering sliders in Settings UI."""
    user_id = authenticated_user["id"]

    # 1. Update concurrency limits via API
    resp = authenticated_client.post(
        "/api/settings/concurrency",
        data={
            "concurrency_max_scrapers": 4,
            "concurrency_max_evaluators": 6,
        },
    )
    assert resp.status_code == 200
    assert "Concurrency Limits Saved" in resp.text

    # 2. Verify settings are persisted
    with Session(engine) as session:
        assert get_user_setting(session, user_id, "concurrency_max_scrapers") == 4
        assert get_user_setting(session, user_id, "concurrency_max_evaluators") == 6
        assert get_app_setting("concurrency_max_scrapers") == 4
        assert get_app_setting("concurrency_max_evaluators") == 6

    # 3. Verify GET /api/settings returns updated concurrency
    settings_resp = authenticated_client.get("/api/settings")
    assert settings_resp.status_code == 200
    data = settings_resp.json()
    assert data["concurrency"]["max_scrapers"] == 4
    assert data["concurrency"]["max_evaluators"] == 6

    # 4. Verify Settings HTML renders concurrency sliders
    ui_resp = authenticated_client.get("/web/views/settings")
    assert ui_resp.status_code == 200
    assert "Max Concurrent Scraping Queries" in ui_resp.text
    assert "Max Concurrent AI Job Evaluators" in ui_resp.text
    assert "concurrency_max_scrapers" in ui_resp.text


def test_queue_view_parallel_metrics(authenticated_client: TestClient):
    """Verify AI Queue View renders parallel worker concurrency metrics."""
    resp = authenticated_client.get("/web/views/queue")
    assert resp.status_code == 200
    assert "Concurrent Scraping:" in resp.text
    assert "Concurrent AI Scoring:" in resp.text
    assert "Multi-Source Parallel:" in resp.text


@pytest.mark.asyncio
async def test_queue_worker_separate_location_and_work_type():
    """Verify location (city, country) and work type (remote/hybrid/onsite) are handled as distinct parameters."""
    mock_job = ScrapedJob(
        source="linkedin",
        title="Python Backend Developer",
        company="CityTech",
        location="Berlin, Germany",
        is_remote=True,
        url="https://linkedin.com/jobs/view/4001",
        description="FastAPI role in Berlin with full remote flexibility.",
    )

    with patch("app.scrapers.jobspy_scraper.JobSpyScraper.scrape", new_callable=AsyncMock) as mock_js:
        mock_js.return_value = [mock_job]

        worker = QueueWorker()
        payload = {
            "platform": "linkedin",
            "keywords": "Python FastAPI",
            "location": "Berlin, Germany",
            "is_remote": True,
        }

        with Session(engine) as session:
            await worker._handle_scrape_query(payload, session, user_id=None)

            # Assert JobSpy scraper was called with explicit separated location and is_remote parameters
            mock_js.assert_called_once()
            _, kwargs = mock_js.call_args
            assert kwargs["location"] == "Berlin, Germany"
            assert kwargs["is_remote"] is True


def test_scrape_modal_platform_selection_and_run(authenticated_client: TestClient):
    """Verify scrape discovery popup allows selecting target platforms and separated location/work type."""
    # 1. Check modal contains platform checkboxes and distinct location/work type fields
    modal_resp = authenticated_client.get("/web/components/scrape-modal")
    assert modal_resp.status_code == 200
    assert "Target Location(s)" in modal_resp.text
    assert "Work Type / Model" in modal_resp.text
    assert 'name="platforms"' in modal_resp.text
    assert "StepStone" in modal_resp.text

    # 2. Trigger scrape with selected platforms and custom location/work type
    run_resp = authenticated_client.post(
        "/web/scrape/run?mode=incremental",
        data={
            "target_locations": "Munich, Germany",
            "work_preference": "hybrid",
            "platforms": ["linkedin", "stepstone"],
            "custom_platforms": "indeed",
        },
    )
    assert run_resp.status_code == 200
    assert "Incremental search discovery queued" in run_resp.text

    # 3. Verify enqueued task payload has separated parameters and target platforms
    with Session(engine) as session:
        task = session.exec(
            select(ScrapeTask).where(ScrapeTask.task_type == "full_discovery").order_by(ScrapeTask.created_at.desc())
        ).first()
        assert task is not None
        payload = json.loads(task.payload_json)
        assert payload["location"] == "Munich, Germany"
        assert payload["work_preference"] == "hybrid"
        assert "linkedin" in payload["platforms"]
        assert "stepstone" in payload["platforms"]
        assert "indeed" in payload["platforms"]


@pytest.mark.asyncio
async def test_failed_owner_does_not_stop_other_owner_scoring(authenticated_client, authenticated_user, provider_transport, tmp_path, monkeypatch, caplog):
    """Concurrent task sessions retain owner routing after a neighbor's 429.

    Exercise the existing worker dispatch without starting perpetual loops.
    Empty disposable vector collections deliberately avoid no-data embeds;
    the separate E2E matrix exercises populated collections through Ollama.
    """
    import httpx
    from app.db.vector import VectorStore
    from app.main import app

    owner = authenticated_user["id"]
    store = VectorStore(str(tmp_path / "owner-progress-vectors"))
    monkeypatch.setattr("app.ai.evaluator.get_vector_store", lambda: store)
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append((request.url.host, payload["model"], request.headers["authorization"]))
        assert request.url.path.endswith("/chat/completions")
        if request.url.host == "api.groq.com":
            return httpx.Response(429, json={"error": {"message": "private-failed-owner <script>quota</script>"}})
        assert request.url.host == "api.openai.com"
        assert request.headers["authorization"] == "Bearer private-progress-owner"
        return httpx.Response(200, json={"id": "progress", "object": "chat.completion", "created": 0,
            "model": payload["model"], "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps({"fit_score": 86, "fit_summary": "Other owner completed",
                "pros": ["Python"], "cons": [], "missing_skills": [], "recommendation": "Strong Match"})}}]})

    provider_transport(respond)
    with TestClient(app) as other_client:
        response = other_client.post("/api/auth/register", json={"email": "parallel-owner@example.com", "password": "OtherPassword123", "full_name": "Other Owner"})
        assert response.status_code == 200
        other = response.json()["id"]
        for client, provider, key in ((authenticated_client, "groq", "private-failed-owner"), (other_client, "openai", "private-progress-owner")):
            assert client.post("/api/settings/ai", data={"task_scoring_provider": provider,
                "task_scoring_model": f"{provider}-owned-model", f"provider_{provider}_key": key}).status_code == 200
        with Session(engine) as session:
            tasks = []
            for user_id in (owner, other):
                job = Job(user_id=user_id, source="test", title="Python Engineer", company="Example", location="Remote",
                          url=f"https://example.test/{user_id}", description="Python engineering", dedup_hash=f"parallel-{user_id}", fit_score=73)
                session.add(job)
                session.commit()
                task = TaskQueue.enqueue(session, "evaluate_job", {"job_id": job.id}, user_id=user_id)
                tasks.append((task.id, job.id))
            limits_before = (get_app_setting("concurrency_max_scrapers"), get_app_setting("concurrency_max_evaluators"))

        async def process(task_id):
            with Session(engine) as task_session:
                await QueueWorker()._process_task(task_session.get(ScrapeTask, task_id), task_session)

        await asyncio.gather(*(process(task_id) for task_id, job_id in tasks))
        with Session(engine) as session:
            failed, completed = [session.get(ScrapeTask, task_id) for task_id, job_id in tasks]
            assert failed.user_id == owner and failed.status == "failed"
            assert completed.user_id == other and completed.status == "completed"
            assert json.loads(failed.error_message)["category"] == "rate_limit"
            assert session.get(Job, tasks[0][1]).fit_score == 73
            assert session.get(Job, tasks[1][1]).fit_score == 86
            assert (get_app_setting("concurrency_max_scrapers"), get_app_setting("concurrency_max_evaluators")) == limits_before
        assert sorted(requests) == sorted([
            ("api.groq.com", "groq-owned-model", "Bearer private-failed-owner"),
            ("api.openai.com", "openai-owned-model", "Bearer private-progress-owner"),
        ])
        assert "private-" not in caplog.text
