"""Unit and integration tests for Persistent Task Queue and Background Worker."""

import json
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.ai.client import MockAIClient
from app.db.database import engine, init_db
from app.db.models import Job, ScrapeTask, UserProfile
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


def test_queue_status_web_component():
    """Test rendering the live queue status widget."""
    with TestClient(app) as client:
        resp = client.get("/web/components/queue-status")
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

        task = TaskQueue.enqueue(
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
    with Session(engine) as session:
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


def test_queue_web_view_and_control_endpoints():
    """Test GET /web/views/queue and web queue control endpoints."""
    with TestClient(app) as client:
        # GET AI Queue View
        resp = client.get("/web/views/queue")
        assert resp.status_code == 200
        assert "Active AI Queue Jobs & Control Center" in resp.text
        assert "All Tasks" in resp.text

        # Toggle pause
        resp_pause = client.post("/web/queue/pause-toggle")
        assert resp_pause.status_code == 200
        assert "Worker Paused" in resp_pause.text or "Worker Active" in resp_pause.text
