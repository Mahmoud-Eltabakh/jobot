"""Unit and integration tests for AI-Assisted Web Scraping & Query Strategy."""

import json
from unittest.mock import AsyncMock

import pytest
from sqlmodel import Session, select

from app.ai.client import AIProviderError, MockAIClient, get_ai_client
from app.db.database import engine, init_db, set_user_setting
from app.db.models import FilterRule, Job, ScrapeTask, User, UserProfile
from app.queue.task_queue import TaskQueue
from app.queue.worker import QueueWorker
from app.scrapers.ai_extractor import AIScraperExtractor
from app.scrapers.query_strategist import AIQueryStrategist
from app.scrapers.scheduler import ScraperPipeline
from app.scrapers.stepstone import StepStoneScraper


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


@pytest.mark.asyncio
async def test_ai_scraper_extractor_clean_and_extract():
    """Verify HTML cleaning and AI-assisted extraction of unstructured job postings."""
    raw_html = """
    <html>
      <head><title>Job Page</title></head>
      <body>
        <script>var x = 123;</script>
        <div class="header">Navigation Bar</div>
        <div class="job-container">
          <h1>Lead Python Backend Architect</h1>
          <div class="company-name">Quantum Cloud Systems</div>
          <div class="location-badge">Berlin, Germany (100% Homeoffice / Remote)</div>
          <div class="salary-box">Compensation: 85,000 € - 110,000 EUR per year</div>
          <p>We are seeking an experienced architect to lead our FastAPI and Kubernetes services. Must have 5+ years of Python.</p>
        </div>
      </body>
    </html>
    """

    cleaned = AIScraperExtractor.clean_html_to_markdown_text(raw_html)
    assert "Navigation Bar" in cleaned or "Lead Python Backend Architect" in cleaned
    assert "var x = 123" not in cleaned

    mock_ai = MockAIClient(default_response=json.dumps({
        "title": "Lead Python Backend Architect",
        "company": "Quantum Cloud Systems",
        "location": "Berlin, Germany",
        "is_remote": True,
        "salary_min": 85000,
        "salary_max": 110000,
        "salary_currency": "EUR",
        "description": "Lead architect position focused on FastAPI and Kubernetes.",
        "required_skills": ["Python", "FastAPI", "Kubernetes"],
        "visa_sponsorship": "available",
        "language_requirement": "English",
        "is_legitimate_job": True,
    }))

    scraped = await AIScraperExtractor.extract_from_html(
        html_or_text=raw_html,
        source_url="https://example.com/job/lead-python",
        source="stepstone",
        ai_client=mock_ai,
    )

    assert scraped is not None
    assert scraped.title == "Lead Python Backend Architect"
    assert scraped.company == "Quantum Cloud Systems"
    assert scraped.is_remote is True
    assert scraped.salary_min == 85000
    assert scraped.salary_max == 110000
    assert scraped.salary_currency == "EUR"


@pytest.mark.asyncio
async def test_ai_scraper_extractor_spam_filter():
    """Verify that spam/promotional non-job listings are discarded."""
    spam_html = """
    <div>
      <h2>Learn Python in 30 Days Bootcamp - 50% Off!</h2>
      <p>Enroll now in our online certificate course for only $499.</p>
    </div>
    """

    mock_ai = MockAIClient(default_response=json.dumps({
        "title": "Course Promotion",
        "company": "Bootcamp Inc",
        "location": "Online",
        "is_remote": True,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "description": "Educational course advertisement.",
        "required_skills": [],
        "visa_sponsorship": None,
        "language_requirement": None,
        "is_legitimate_job": False,
    }))

    scraped = await AIScraperExtractor.extract_from_html(
        html_or_text=spam_html,
        source_url="https://example.com/ad",
        source="web",
        ai_client=mock_ai,
    )
    assert scraped is None


@pytest.mark.asyncio
async def test_ai_query_strategist():
    """Verify AI search query generation combining candidate skills and blacklist awareness."""
    with Session(engine) as session:
        profile = UserProfile(
            full_name="Alex Johnson",
            target_titles_json=json.dumps(["Senior Python Engineer", "Backend Developer"]),
            skills_json=json.dumps(["Python", "FastAPI", "Docker", "PostgreSQL", "ChromaDB"]),
            active_search_skills_json=json.dumps(["Python", "FastAPI", "Docker"]),
            target_locations_json=json.dumps(["Munich", "Remote"]),
            work_preference="remote_first",
        )
        session.add(profile)

        rule = FilterRule(rule_type="title", pattern="Junior")
        session.add(rule)
        session.commit()

        mock_ai = MockAIClient(default_response=json.dumps([
            {"platform": "linkedin", "keywords": "Python FastAPI Remote", "location": "Munich"},
            {"platform": "stepstone", "keywords": "Senior Python Backend", "location": "Remote"},
            {"platform": "google", "keywords": "Docker Python Engineer", "location": "Germany"},
        ]))

        queries = await AIQueryStrategist.generate_search_queries(
            session=session,
            max_queries=3,
            ai_client=mock_ai,
        )

        assert len(queries) == 3
        platforms = [q[0] for q in queries]
        keywords = [q[1] for q in queries]
        assert "linkedin" in platforms
        assert "Python FastAPI Remote" in keywords


def test_stepstone_unstructured_markup_yields_no_fabricated_job():
    """Non-card markup must not be turned into a heuristic job."""
    unstructured_html = """
    <section>
      <h1>Cloud Infrastructure Engineer</h1>
      <h3>Global Tech Solutions</h3>
      <p>Looking for a talented cloud architect with Python experience. 80.000 - 95.000 EUR. Homeoffice enabled.</p>
    </section>
    """

    jobs = StepStoneScraper.parse_cards_from_html(unstructured_html, base_url="https://stepstone.de")
    assert jobs == []


@pytest.mark.asyncio
async def test_extractor_routes_owned_scraping(monkeypatch):
    calls = []
    client = MockAIClient(default_response='{"title":"Engineer","company":"Test"}')

    def resolve(session, user_id, *, task_type):
        calls.append((session, user_id, task_type))
        return client

    monkeypatch.setattr("app.scrapers.ai_extractor.get_ai_client", resolve)
    with Session(engine) as session:
        job = await AIScraperExtractor.extract_from_html(
            "<h1>Engineer</h1>", session=session, user_id=42,
        )
        assert job.title == "Engineer"
        assert calls == [(session, 42, "scraping")]


@pytest.mark.asyncio
@pytest.mark.parametrize("response", ["not-json", "[]", "{}", '{"title":42}'])
async def test_extractor_invalid_response_is_not_a_heuristic_job(response):
    with pytest.raises(AIProviderError) as error:
        await AIScraperExtractor.extract_from_html("Engineer\nTest", ai_client=MockAIClient(response))
    assert error.value.category == "invalid_response"


@pytest.mark.asyncio
async def test_scraping_provider_failure_is_not_synthetic_success(authenticated_user):
    client = MockAIClient()
    failure = AIProviderError("openai", "test-model", "rate_limit", 429)
    client.generate = AsyncMock(side_effect=failure)
    with pytest.raises(AIProviderError) as error:
        await AIScraperExtractor.extract_from_html("Engineer\nTest", ai_client=client)
    assert error.value is failure
    with Session(engine) as session:
        owner = authenticated_user["id"]
        session.add(UserProfile(user_id=owner, full_name="Test", skills_json='["Python"]'))
        session.commit()
        with pytest.raises(AIProviderError) as error:
            await AIQueryStrategist.generate_search_queries(session, ai_client=client, user_id=owner)
        assert error.value is failure
    assert client.generate.await_count == 2


@pytest.mark.asyncio
async def test_strategist_routes_owner_and_accepts_queries_envelope(monkeypatch, authenticated_user):
    client = MockAIClient('{"queries":[{"platform":"all","keywords":"Python Engineer","location":"Berlin"}]}')
    calls = []

    def resolve(session, user_id, *, task_type):
        calls.append((session, user_id, task_type))
        return client

    monkeypatch.setattr("app.scrapers.query_strategist.get_ai_client", resolve)
    with Session(engine) as session:
        owner = authenticated_user["id"]
        session.add(UserProfile(user_id=owner, full_name="Test", skills_json='["Python"]'))
        session.commit()
        assert await AIQueryStrategist.generate_search_queries(session, user_id=owner) == [
            ("all", "Python Engineer", "Berlin")
        ]
        assert calls == [(session, owner, "scraping")]


@pytest.mark.asyncio
async def test_worker_owner_stages_and_safe_manual_retry(monkeypatch, authenticated_user, caplog):
    owner = authenticated_user["id"]
    scraping = MockAIClient('{"queries":[{"keywords":"Python Engineer"}]}')
    scoring = MockAIClient()
    failure = AIProviderError("openai", "owner-model", "rate_limit", 429)
    calls = []

    def resolve(session, user_id, *, task_type="scoring"):
        calls.append((user_id, task_type))
        return scraping if task_type == "scraping" else scoring

    async def evaluate(**kwargs):
        assert kwargs["ai_client"] is scoring
        assert kwargs["user_id"] == owner
        raise failure from RuntimeError("credential-secret-must-not-leak")

    monkeypatch.setattr("app.queue.worker.get_ai_client", resolve)
    monkeypatch.setattr("app.queue.worker.JobEvaluator.evaluate_and_update_job", evaluate)
    with Session(engine) as session:
        session.add(UserProfile(user_id=owner, full_name="Test", skills_json='["Python"]'))
        job = Job(user_id=owner, title="Engineer", company="Test", location="Remote", source="test", url="https://example.com", dedup_hash="routing", fit_score=71)
        session.add(job)
        session.commit()
        discovery = TaskQueue.enqueue(session, "full_discovery", {}, user_id=owner)
        failed = TaskQueue.enqueue(session, "evaluate_job", {"job_id": job.id}, user_id=owner)
        worker = QueueWorker()
        await worker._process_task(discovery, session)
        await worker._process_task(failed, session)
        session.refresh(failed)
        assert calls == [(owner, "scraping"), (owner, "scoring")]
        assert discovery.status == "completed"
        assert failed.status == "failed"
        diagnostic = json.loads(failed.error_message)
        assert diagnostic["provider"] == "openai"
        assert diagnostic["model"] == "owner-model"
        assert diagnostic["category"] == "rate_limit"
        assert diagnostic["status_code"] == 429
        assert "credential-secret" not in failed.error_message + caplog.text
        assert session.get(Job, job.id).fit_score == 71
        queued = session.exec(select(ScrapeTask).where(ScrapeTask.task_type == "scrape_query")).all()
        assert len(queued) == 1 and queued[0].user_id == owner
        assert TaskQueue.retry_task(session, failed.id, user_id=owner).status == "pending"


@pytest.mark.asyncio
async def test_scheduler_separate_clients_and_error_resets_running(monkeypatch, authenticated_user):
    owner = authenticated_user["id"]
    scraping, scoring = MockAIClient(), MockAIClient()
    calls = []

    def resolve(session, user_id, *, task_type="scoring"):
        calls.append((user_id, task_type))
        return scraping if task_type == "scraping" else scoring

    async def queries(**kwargs):
        assert kwargs["ai_client"] is scraping
        return []

    monkeypatch.setattr("app.scrapers.scheduler.get_ai_client", resolve)
    monkeypatch.setattr(AIQueryStrategist, "generate_search_queries", queries)
    with Session(engine) as session:
        stats = await ScraperPipeline.run_full_pipeline(session, user_id=owner)
        assert stats["scraped_total"] == 0
        assert calls == [(owner, "scraping"), (owner, "scoring")]
        failure = AIProviderError("openai", "test", "rate_limit", 429)

        async def fail_queries(**kwargs):
            raise failure

        monkeypatch.setattr(AIQueryStrategist, "generate_search_queries", fail_queries)
        with pytest.raises(AIProviderError) as error:
            await ScraperPipeline.run_full_pipeline(session, user_id=owner)
        assert error.value is failure
        assert not ScraperPipeline.is_running()


@pytest.mark.asyncio
async def test_worker_two_accounts_use_saved_stage_assignments(monkeypatch, authenticated_user):
    resolutions = []
    evaluations = []

    def resolve(session, user_id, *, task_type):
        client = get_ai_client(session, user_id, task_type=task_type)
        resolutions.append((user_id, task_type, client.provider, client.model))
        client.generate = AsyncMock(return_value='{"queries":[{"keywords":"Python Engineer"}]}')
        return client

    async def evaluate(**kwargs):
        evaluations.append((kwargs["user_id"], kwargs["ai_client"].provider))
        return None

    monkeypatch.setattr("app.queue.worker.get_ai_client", resolve)
    monkeypatch.setattr("app.queue.worker.JobEvaluator.evaluate_and_update_job", evaluate)
    with Session(engine) as session:
        other = User(email="other-routing@example.com", full_name="Other", password_hash="test-only-no-login")
        session.add(other)
        session.commit()
        owners = [authenticated_user["id"], other.id]
        jobs = []
        for owner, scraping, scoring in zip(owners, ["anthropic", "gemini"], ["openai", "groq"]):
            for stage, provider in [("scraping", scraping), ("scoring", scoring)]:
                set_user_setting(session, owner, f"task_{stage}_provider", provider)
                set_user_setting(session, owner, f"task_{stage}_model", f"owner-{owner}-{stage}")
                set_user_setting(session, owner, f"provider_{provider}_key", f"fake-owner-{owner}-{provider}")
            session.add(UserProfile(user_id=owner, full_name=f"Owner {owner}", skills_json='["Python"]'))
            job = Job(user_id=owner, title="Python", company="Test", location="Remote", source="test", url="https://example.com", dedup_hash=f"owner-{owner}")
            session.add(job)
            session.commit()
            jobs.append(job)
        worker = QueueWorker()
        for owner, job in zip(owners, jobs):
            await worker._handle_full_discovery({}, session, owner)
            await worker._handle_evaluate_job({"job_id": job.id}, session, owner)
        await worker._handle_evaluate_job({"job_id": jobs[1].id}, session, owners[0])
        assert resolutions == [
            (owners[0], "scraping", "anthropic", f"owner-{owners[0]}-scraping"),
            (owners[0], "scoring", "openai", f"owner-{owners[0]}-scoring"),
            (owners[1], "scraping", "gemini", f"owner-{owners[1]}-scraping"),
            (owners[1], "scoring", "groq", f"owner-{owners[1]}-scoring"),
        ]
        assert evaluations == [(owners[0], "openai"), (owners[1], "groq")]
        tasks = session.exec(select(ScrapeTask)).all()
        # Each owner gets the AI strategist query plus the deterministic profile query
        assert {task.user_id for task in tasks} == set(owners)
        for owner in owners:
            assert "Python Engineer" in [json.loads(t.payload_json)["keywords"] for t in tasks if t.user_id == owner]


@pytest.mark.asyncio
async def test_scheduler_scoring_failure_propagates_without_success_stats(monkeypatch):
    failure = AIProviderError("openai", "selected-scoring", "rate_limit", 429)
    scoring = MockAIClient()
    job = Job(id=99, title="Python", company="Test", location="Remote", source="test", url="https://example.com", dedup_hash="scheduler-failure")

    async def evaluate(**kwargs):
        assert kwargs["ai_client"] is scoring
        raise failure

    monkeypatch.setattr("app.scrapers.scheduler.JobSpyScraper.scrape", AsyncMock(return_value=[]))
    monkeypatch.setattr("app.scrapers.scheduler.save_scraped_jobs", lambda *args, **kwargs: ([job], 0))
    monkeypatch.setattr("app.scrapers.scheduler.JobFilterPipeline.apply_filters_and_save", lambda *args, **kwargs: ([job], []))
    monkeypatch.setattr("app.scrapers.scheduler.JobEvaluator.evaluate_and_update_job", evaluate)
    stats_writer = AsyncMock()
    monkeypatch.setattr("app.scrapers.scheduler.set_app_setting", stats_writer)
    with Session(engine) as session:
        with pytest.raises(AIProviderError) as error:
            await ScraperPipeline.run_full_pipeline(session, scoring, override_keywords="Python")
        assert error.value is failure
        assert not ScraperPipeline.is_running()
        stats_writer.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["linkedin", "stepstone"])
async def test_worker_scrape_wrappers_do_not_swallow_provider_failure(monkeypatch, platform):
    failure = AIProviderError("openai", "selected-scraping", "rate_limit", 429)
    monkeypatch.setattr("app.queue.worker.get_app_setting", lambda *args, **kwargs: 0)
    monkeypatch.setattr("app.queue.worker.JobSpyScraper.scrape", AsyncMock(side_effect=failure))
    monkeypatch.setattr("app.queue.worker.StepStoneScraper.scrape", AsyncMock(side_effect=failure))
    with Session(engine) as session:
        task = TaskQueue.enqueue(session, "scrape_query", {"platform": platform, "keywords":"Python"})
        await QueueWorker()._process_task(task, session)
        assert task.status == "failed"
        assert json.loads(task.error_message)["category"] == "rate_limit"
        assert not session.exec(select(Job)).all()


# ---- Phase 9 gap closure: AI extraction wired into StepStone, per-user toggle ----

def _fake_stepstone_playwright(monkeypatch, html: str):
    class Page:
        url = "https://www.stepstone.de/work/x-in-y"

        async def goto(self, *a, **k):
            return None

        async def wait_for_timeout(self, *a):
            return None

        async def is_visible(self, *a, **k):
            return False

        async def content(self):
            return html

    class Context:
        async def new_page(self):
            return Page()

        async def close(self):
            return None

    class Browser:
        async def new_context(self, **k):
            return Context()

        async def close(self):
            return None

    class PW:
        class chromium:
            @staticmethod
            async def launch(**k):
                return Browser()

    class CM:
        async def __aenter__(self):
            return PW()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr("app.scrapers.stepstone.async_playwright", lambda: CM())


NO_CARDS_HTML = "<html><body><h1>Python Engineer</h1><p>Acme GmbH, Berlin</p></body></html>"
AI_JOB = json.dumps({"title": "Python Engineer", "company": "Acme GmbH", "location": "Berlin", "is_legitimate_job": True})


@pytest.mark.asyncio
async def test_stepstone_ai_fallback_extracts_when_cards_missing(monkeypatch):
    _fake_stepstone_playwright(monkeypatch, NO_CARDS_HTML)
    jobs = await StepStoneScraper().scrape("python", "berlin", ai_client=MockAIClient(AI_JOB))
    assert [(j.title, j.company, j.source) for j in jobs] == [("Python Engineer", "Acme GmbH", "stepstone")]


@pytest.mark.asyncio
async def test_stepstone_without_ai_client_returns_nothing(monkeypatch):
    _fake_stepstone_playwright(monkeypatch, NO_CARDS_HTML)
    assert await StepStoneScraper().scrape("python", "berlin") == []


@pytest.mark.asyncio
async def test_stepstone_ai_fallback_discards_spam(monkeypatch):
    _fake_stepstone_playwright(monkeypatch, NO_CARDS_HTML)
    spam = json.dumps({"title": "Ad", "company": "X", "is_legitimate_job": False})
    assert await StepStoneScraper().scrape("python", "berlin", ai_client=MockAIClient(spam)) == []


@pytest.mark.asyncio
async def test_stepstone_ai_unavailable_is_honest_failure(monkeypatch):
    _fake_stepstone_playwright(monkeypatch, NO_CARDS_HTML)
    client = MockAIClient()
    client.generate = AsyncMock(side_effect=AIProviderError("ollama", "m", "connection"))
    with pytest.raises(AIProviderError):
        await StepStoneScraper().scrape("python", "berlin", ai_client=client)


@pytest.mark.asyncio
async def test_worker_passes_ai_client_only_when_setting_enabled(authenticated_user, monkeypatch):
    seen = []

    async def fake_scrape(self, search_term, location, results_wanted=None, is_remote=False, **extra):
        seen.append(extra)
        return []

    monkeypatch.setattr(StepStoneScraper, "scrape", fake_scrape)
    uid = authenticated_user["id"]
    worker = QueueWorker(ai_client=MockAIClient())
    payload = {"platforms": ["stepstone"], "keywords": "python", "location": "berlin"}
    with Session(engine) as session:
        await worker._handle_scrape_query(payload, session, uid)
        set_user_setting(session, uid, "use_ai_scraping", True)
        await worker._handle_scrape_query(payload, session, uid)
    assert seen[0] == {}
    assert isinstance(seen[1]["ai_client"], MockAIClient)


def test_ai_scraping_toggle_persists_and_badge_is_truthful(authenticated_client, authenticated_user):
    view = authenticated_client.get("/web/views/settings").text
    assert "AI extraction disabled" in view and "AI extraction enabled" not in view

    on = authenticated_client.post("/api/settings/ai-scraping", data={"use_ai_scraping": "true"})
    assert "AI extraction enabled" in on.text
    view = authenticated_client.get("/web/views/settings").text
    assert "AI extraction enabled" in view and 'name="use_ai_scraping" value="true" checked' in view

    off = authenticated_client.post("/api/settings/ai-scraping", data={})
    assert "AI extraction disabled" in off.text
    from app.db.database import get_user_setting
    with Session(engine) as session:
        assert get_user_setting(session, authenticated_user["id"], "use_ai_scraping") is False
