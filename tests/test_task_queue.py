"""Unit and integration tests for Persistent Task Queue and Background Worker."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.ai.client import MockAIClient
from app.db.database import engine, init_db
from app.db.models import Job
from app.main import app
from app.queue.task_queue import TaskQueue
from app.queue.worker import QueueWorker


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def test_task_queue_lifecycle():
    """Test task enqueueing, atomic claiming, completion, and retry logic."""
    with Session(engine) as session:
        # 1. Enqueue Task
        task = TaskQueue.enqueue(
            session=session,
            task_type="scrape_query",
            payload={"keywords": "Python FastAPI", "location": "Remote"},
            max_retries=2,
        )
        assert task.id is not None
        assert task.status == "pending"

        # 2. Check Stats
        stats = TaskQueue.get_stats(session)
        assert stats["pending"] >= 1

        # 3. Claim Task
        claimed = TaskQueue.claim_next_task(session)
        assert claimed is not None
        assert claimed.id == task.id
        assert claimed.status == "in_progress"

        # 4. Mark Failed (Retry 1/2)
        failed_once = TaskQueue.mark_failed(session, claimed.id, "Network timeout")
        assert failed_once.status == "pending"
        assert failed_once.retries == 1

        # 5. Claim and Fail again (Permanent failure)
        claimed_2 = TaskQueue.claim_next_task(session)
        failed_perm = TaskQueue.mark_failed(session, claimed_2.id, "Network timeout again")
        assert failed_perm.status == "failed"
        assert failed_perm.retries == 2

        # 6. Retry all failed
        reset_count = TaskQueue.retry_all_failed(session)
        assert reset_count >= 1

        claimed_3 = TaskQueue.claim_next_task(session)
        completed = TaskQueue.mark_completed(session, claimed_3.id)
        assert completed.status == "completed"


def test_queue_rest_api():
    """Test REST endpoints for queue monitoring and task enqueuing."""
    with TestClient(app) as client:
        register_response = client.post(
            "/api/auth/register",
            json={"email": "queue@example.com", "password": "Password123", "full_name": "Queue User"},
        )
        assert register_response.status_code == 200

        # 1. Enqueue via API
        resp = client.post(
            "/api/queue/enqueue",
            json={
                "task_type": "scrape_query",
                "payload": {"keywords": "Backend Engineer", "location": "Germany"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["task_type"] == "scrape_query"

        # 2. Trigger Full Discovery via API
        disc_resp = client.post("/api/queue/run-discovery")
        assert disc_resp.status_code == 200
        assert disc_resp.json()["status"] == "ok"

        # 3. Get Queue Status
        status_resp = client.get("/api/queue/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert "stats" in status_data
        assert "recent_tasks" in status_data

        # 4. Retry Failed via API
        retry_resp = client.post("/api/queue/retry-failed")
        assert retry_resp.status_code == 200


def test_queue_status_web_component(authenticated_client: TestClient):
    """Test rendering the live queue status widget."""
    resp = authenticated_client.get("/web/components/queue-status")
    assert resp.status_code == 200
    assert "Queue:" in resp.text


@pytest.mark.asyncio
async def test_queue_worker_task_execution():
    """Test QueueWorker processing an evaluate_job task in background."""
    with Session(engine) as session:
        job = Job(
            title="Python Developer",
            company="QueueTest AG",
            location="Remote",
            source="test",
            url="https://example.com/job-queue-test",
            description="Looking for Python and Docker developer.",
            dedup_hash="queue_test_hash_9999",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

        TaskQueue.enqueue(
            session=session,
            task_type="evaluate_job",
            payload={"job_id": job_id},
        )

    mock_ai = MockAIClient(default_response=json.dumps({
        "fit_score": 92,
        "fit_summary": "Excellent fit for backend role.",
        "pros": ["Python expertise"],
        "cons": [],
        "missing_skills": [],
        "recommendation": "Strong Match",
    }))

    worker = QueueWorker(ai_client=mock_ai)
    with (
        Session(engine) as session,
        patch("app.ai.embeddings.ProfileEmbedder.compute_semantic_similarity", new_callable=AsyncMock, return_value=0.5),
    ):
        claimed = TaskQueue.claim_next_task(session)
        assert claimed is not None
        await worker._process_task(claimed, session)

    with Session(engine) as session:
        updated_job = session.get(Job, job_id)
        assert updated_job.fit_score == 92


def test_queue_control_methods():
    """Test task queue control methods: pause, retry, delete, clear."""
    with Session(engine) as session:
        # Pause queue
        assert not TaskQueue.is_paused(session)
        is_paused = TaskQueue.toggle_pause(session)
        assert is_paused
        assert TaskQueue.is_paused(session)

        # Enqueue task while paused -> claim_next_task returns None
        task1 = TaskQueue.enqueue(session, "scrape_query", {"keywords": "Test"})
        assert TaskQueue.claim_next_task(session) is None

        # Resume queue
        TaskQueue.toggle_pause(session)
        assert not TaskQueue.is_paused(session)

        # Claim task
        claimed = TaskQueue.claim_next_task(session)
        assert claimed is not None
        assert claimed.id == task1.id

        # Mark completed & test clear_completed
        TaskQueue.mark_completed(session, task1.id)
        cleared = TaskQueue.clear_completed(session)
        assert cleared == 1

        # Test retry_task and delete_task
        task2 = TaskQueue.enqueue(session, "scrape_query", {"keywords": "Test2"})
        TaskQueue.mark_failed(session, task2.id, "Error")
        retried = TaskQueue.retry_task(session, task2.id)
        assert retried.status == "pending"

        deleted = TaskQueue.delete_task(session, task2.id)
        assert deleted


@pytest.mark.asyncio
async def test_provider_failure_never_commits_claimable_task(monkeypatch):
    """Another consumer must see terminal failure, not an intermediate retry."""
    from app.ai.client import AIProviderError

    worker = QueueWorker(ai_client=MockAIClient())
    monkeypatch.setattr(worker, "_handle_evaluate_job", AsyncMock(side_effect=AIProviderError(
        "openai", "test-model", "rate_limit", status_code=429,
    )))
    original_mark_failed = TaskQueue.mark_failed
    observed_claims = []

    def interleaved_failure(session, task_id, message, **kwargs):
        result = original_mark_failed(session, task_id, message, **kwargs)
        with Session(engine) as other_session:
            observed_claims.append(TaskQueue.claim_next_task(other_session))
        return result

    monkeypatch.setattr(TaskQueue, "mark_failed", interleaved_failure)
    with Session(engine) as session:
        task = TaskQueue.enqueue(session, "evaluate_job", {"job_id": 1})
        task_id = task.id
        claimed = TaskQueue.claim_next_task(session)
        with patch.object(session, "commit", wraps=session.commit) as commits:
            await worker._process_task(claimed, session)
        assert commits.call_count == 1

    assert observed_claims == [None]
    with Session(engine) as session:
        from app.db.models import ScrapeTask
        failed = session.get(ScrapeTask, task_id)
        assert failed.status == "failed"
        assert failed.retries == 1
        assert failed.max_retries > failed.retries
        assert json.loads(failed.error_message)["category"] == "rate_limit"
        assert TaskQueue.retry_task(session, task_id).status == "pending"


def test_queue_web_view_and_control_endpoints(authenticated_client: TestClient):
    """Test GET /web/views/queue and web queue control endpoints."""
    resp = authenticated_client.get("/web/views/queue")
    assert resp.status_code == 200
    assert "Active AI Queue Jobs & Control Center" in resp.text
    assert "All Tasks" in resp.text

    resp_pause = authenticated_client.post("/web/queue/pause-toggle")
    assert resp_pause.status_code == 200
    assert "Worker Paused" in resp_pause.text or "Worker Active" in resp_pause.text


def test_stranded_in_progress_task_recovered_after_restart():
    """A task claimed by a crashed process must be reclaimed when the worker starts."""
    with Session(engine) as session:
        task = TaskQueue.enqueue(session, "scrape_query", {"keywords": "x"})
        assert TaskQueue.claim_next_task(session).id == task.id
        task_id = task.id

    with Session(engine) as session:
        assert TaskQueue.claim_next_task(session) is None  # stranded before recovery
        assert TaskQueue.recover_stale_tasks(session) == 1
        assert TaskQueue.claim_next_task(session).id == task_id


def test_recover_stale_tasks_respects_lease_age():
    with Session(engine) as session:
        TaskQueue.enqueue(session, "scrape_query", {"keywords": "x"})
        TaskQueue.claim_next_task(session)
        assert TaskQueue.recover_stale_tasks(session, older_than_seconds=3600) == 0
        assert TaskQueue.recover_stale_tasks(session) == 1


@pytest.mark.asyncio
async def test_worker_start_recovers_and_honors_concurrency(monkeypatch):
    from app.db.database import set_app_setting

    set_app_setting("concurrency_max_scrapers", 2)
    set_app_setting("concurrency_max_evaluators", 4)
    with Session(engine) as session:
        TaskQueue.enqueue(session, "scrape_query", {"keywords": "x"})
        TaskQueue.claim_next_task(session)

    worker = QueueWorker(poll_interval_seconds=60)
    worker.start()
    try:
        assert len(worker._loop_tasks) == 6
        with Session(engine) as session:
            assert TaskQueue.get_stats(session)["in_progress"] == 0
    finally:
        worker.stop()


def test_running_worker_reclaims_expired_lease_only():
    from datetime import timedelta

    from app.db.models import ScrapeTask, utc_now

    with Session(engine) as session:
        task = TaskQueue.enqueue(session, "scrape_query", {"keywords": "x"})
        TaskQueue.claim_next_task(session)
        worker = QueueWorker()
        assert worker.reclaim_expired_leases() == 0  # fresh claim stays leased

        stale = session.get(ScrapeTask, task.id)
        stale.updated_at = utc_now() - timedelta(hours=2)
        session.add(stale)
        session.commit()
        assert worker.reclaim_expired_leases() == 1
        session.refresh(stale)
        assert stale.status == "pending"


@pytest.mark.asyncio
async def test_maintenance_loop_reclaims_and_resizes_pools():
    import asyncio
    from datetime import timedelta

    from sqlalchemy import update

    from app.db.database import set_app_setting
    from app.db.models import ScrapeTask, utc_now

    set_app_setting("concurrency_max_scrapers", 1)
    set_app_setting("concurrency_max_evaluators", 1)
    worker = QueueWorker(poll_interval_seconds=0.01, maintenance_interval_seconds=0.02)
    # Paused queue keeps loops from claiming the task under test
    set_app_setting("is_queue_paused", True)
    try:
        worker.start()
        assert len(worker._loop_tasks) == 2

        # Stranded after start, so only the periodic reclaim can recover it
        with Session(engine) as session:
            task_id = TaskQueue.enqueue(session, "scrape_query", {"keywords": "x"}).id
            session.exec(update(ScrapeTask).where(ScrapeTask.id == task_id).values(
                status="in_progress", updated_at=utc_now() - timedelta(hours=2)))
            session.commit()

        set_app_setting("concurrency_max_scrapers", 3)
        set_app_setting("concurrency_max_evaluators", 1)
        await asyncio.sleep(0.2)
        assert len(worker._pools["scraper"]) == 3
        with Session(engine) as session:
            assert session.get(ScrapeTask, task_id).status == "pending"

        set_app_setting("concurrency_max_scrapers", 1)
        await asyncio.sleep(0.2)
        assert len(worker._loop_tasks) == 2
    finally:
        worker.stop()
        set_app_setting("is_queue_paused", False)


@pytest.mark.asyncio
async def test_cancelled_task_is_released_not_stranded(monkeypatch):
    import asyncio

    worker = QueueWorker(ai_client=MockAIClient())
    monkeypatch.setattr(worker, "_handle_scrape_query", AsyncMock(side_effect=asyncio.CancelledError()))
    with Session(engine) as session:
        task = TaskQueue.enqueue(session, "scrape_query", {"keywords": "x"})
        task_id = task.id
        claimed = TaskQueue.claim_next_task(session)
        with pytest.raises(asyncio.CancelledError):
            await worker._process_task(claimed, session)
    with Session(engine) as session:
        from app.db.models import ScrapeTask
        released = session.get(ScrapeTask, task_id)
        assert released.status == "pending" and released.retries == 0


@pytest.mark.asyncio
async def test_unhandled_task_type_fails_instead_of_completing():
    from app.db.models import ScrapeTask

    worker = QueueWorker(ai_client=MockAIClient())
    with Session(engine) as session:
        task = TaskQueue.enqueue(session, "feedback_tune", {})
        claimed = TaskQueue.claim_next_task(session)
        await worker._process_task(claimed, session)
        failed = session.get(ScrapeTask, task.id)
        assert failed.status == "failed"
        assert "Unsupported" in failed.error_message


def test_pause_is_scoped_to_the_pausing_account():
    from app.db.models import User

    with Session(engine) as session:
        users = []
        for i in (1, 2):
            u = User(email=f"p{i}@example.com", password_hash="x", full_name=f"P{i}")
            session.add(u)
            session.commit()
            session.refresh(u)
            users.append(u.id)
        a, b = users
        task_a = TaskQueue.enqueue(session, "scrape_query", {"keywords": "a"}, user_id=a)
        task_b = TaskQueue.enqueue(session, "scrape_query", {"keywords": "b"}, user_id=a)
        task_c = TaskQueue.enqueue(session, "scrape_query", {"keywords": "c"}, user_id=b)

        assert TaskQueue.toggle_pause(session, a)
        assert not TaskQueue.is_paused(session, b)
        assert TaskQueue.get_stats(session, a)["is_paused"]
        assert not TaskQueue.get_stats(session, b)["is_paused"]

        claimed = TaskQueue.claim_next_task(session)
        assert claimed.id == task_c.id
        assert TaskQueue.claim_next_task(session) is None  # a's tasks stay held

        TaskQueue.toggle_pause(session, a)
        assert TaskQueue.claim_next_task(session).id == task_a.id


@pytest.mark.asyncio
async def test_heartbeat_keeps_long_running_task_from_being_reclaimed(monkeypatch):
    import asyncio
    from datetime import timedelta

    from sqlalchemy import update

    from app.db.models import ScrapeTask, utc_now

    worker = QueueWorker(ai_client=MockAIClient())
    worker.heartbeat_interval = 0.01
    observed = {}

    async def long_handler(payload, session, user_id):
        with Session(engine) as other:
            # Simulate a claim that is already older than the lease.
            other.exec(update(ScrapeTask).where(ScrapeTask.id == task_id).values(updated_at=utc_now() - timedelta(hours=2)))
            other.commit()
        await asyncio.sleep(0.2)
        observed["reclaimed"] = worker.reclaim_expired_leases()
        with Session(engine) as other:
            observed["status"] = other.get(ScrapeTask, task_id).status

    monkeypatch.setattr(worker, "_handle_evaluate_job", long_handler)
    with Session(engine) as session:
        task_id = TaskQueue.enqueue(session, "evaluate_job", {"job_id": 1}).id
        claimed = TaskQueue.claim_next_task(session)
        await worker._process_task(claimed, session)

    assert observed == {"reclaimed": 0, "status": "in_progress"}
    with Session(engine) as session:
        assert session.get(ScrapeTask, task_id).status == "completed"


def test_touch_task_only_refreshes_claimed_tasks():
    with Session(engine) as session:
        task = TaskQueue.enqueue(session, "scrape_query", {"keywords": "x"})
        assert TaskQueue.touch_task(session, task.id) is False  # still pending
        TaskQueue.claim_next_task(session)
        assert TaskQueue.touch_task(session, task.id) is True
