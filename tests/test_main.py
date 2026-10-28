"""Tests for main FastAPI application endpoints."""

from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Verify /health endpoint returns expected status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "Jobot"
    assert data["version"] == "0.1.0"


def test_lifespan_starts_worker_and_runs_backfills_with_disposable_storage(monkeypatch, tmp_path):
    from unittest.mock import MagicMock

    from fastapi.testclient import TestClient

    from app.ai.embeddings import ProfileEmbedder
    from app.ai.feedback import FeedbackManager
    from app.db import vector
    from app.main import app
    from app.queue import worker as worker_module
    from app.scrapers import scheduler as scheduler_module

    store = vector.VectorStore(persist_dir=str(tmp_path / "chroma"))
    fake_worker, fake_scheduler = MagicMock(), MagicMock()
    feedback_backfill = MagicMock(return_value={})
    cv_backfill = MagicMock(return_value=0)
    monkeypatch.delenv("JOBOT_TESTING", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(vector, "get_vector_store", lambda persist_dir=None: store)
    monkeypatch.setattr(worker_module, "get_queue_worker", lambda: fake_worker)
    monkeypatch.setattr(scheduler_module, "get_scheduler", lambda: fake_scheduler)
    monkeypatch.setattr(FeedbackManager, "backfill_feedback_owners", feedback_backfill)
    monkeypatch.setattr(ProfileEmbedder, "backfill_legacy_cv_vectors", cv_backfill)

    with TestClient(app):
        fake_worker.start.assert_called_once()
        fake_scheduler.start.assert_called_once()
        assert feedback_backfill.call_args.args[1] is store
        assert cv_backfill.call_args.args[1] is store
        fake_worker.stop.assert_not_called()
    fake_worker.stop.assert_called_once()
    fake_scheduler.shutdown.assert_called_once()


def test_lifespan_backfill_failure_does_not_block_startup(monkeypatch):
    from unittest.mock import MagicMock

    from fastapi.testclient import TestClient

    from app.ai.feedback import FeedbackManager
    from app.main import app
    from app.queue import worker as worker_module
    from app.scrapers import scheduler as scheduler_module

    fake_worker = MagicMock()
    monkeypatch.delenv("JOBOT_TESTING", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(worker_module, "get_queue_worker", lambda: fake_worker)
    monkeypatch.setattr(scheduler_module, "get_scheduler", lambda: MagicMock())
    monkeypatch.setattr(FeedbackManager, "backfill_feedback_owners", MagicMock(side_effect=RuntimeError("boom")))
    with TestClient(app) as test_client:
        assert test_client.get("/health").status_code == 200
        fake_worker.start.assert_called_once()
