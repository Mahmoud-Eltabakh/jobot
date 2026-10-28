"""Tests for candidate feedback vector recording and adaptive fit score re-weighting."""

import shutil
import tempfile
from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest
from sqlmodel import Session

from app.ai.client import AIProviderError, MockAIClient
from app.ai.feedback import FeedbackManager
from app.db.database import engine, init_db
from app.db.models import Job, JobStatus
from app.db.vector import VectorStore


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


@pytest.fixture
def temp_vector_store() -> Generator[VectorStore, None, None]:
    temp_dir = tempfile.mkdtemp(prefix="jobot_feedback_test_")
    store = VectorStore(persist_dir=temp_dir)
    yield store
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_record_feedback_vector(temp_vector_store: VectorStore) -> None:
    """Verify recording positive and negative feedback vectors in ChromaDB."""
    mock_ai = MockAIClient()

    with Session(engine) as session:
        job_pos = Job(
            source="linkedin",
            title="Senior Python Backend Engineer",
            company="GoodCompany",
            location="Remote",
            url="https://example.com/pos",
            status=JobStatus.APPLIED.value,
            dedup_hash="hash-feedback-pos",
        )
        job_neg = Job(
            source="stepstone",
            title="Legacy PHP Developer",
            company="BadCompany",
            location="Onsite",
            url="https://example.com/neg",
            status=JobStatus.NOT_A_FIT.value,
            dedup_hash="hash-feedback-neg",
        )
        session.add(job_pos)
        session.add(job_neg)
        session.commit()
        session.refresh(job_pos)
        session.refresh(job_neg)

        # Record positive
        vec_id_pos = await FeedbackManager.record_job_feedback(
            job_id=job_pos.id,
            status=JobStatus.APPLIED.value,
            note_text="Loved the modern stack and remote flexibility",
            session=session,
            vector_store=temp_vector_store,
            ai_client=mock_ai,
            embedding_client=mock_ai,
        )
        assert vec_id_pos is not None

        # Record negative
        vec_id_neg = await FeedbackManager.record_job_feedback(
            job_id=job_neg.id,
            status=JobStatus.NOT_A_FIT.value,
            note_text="Requires 100% onsite in small town and legacy PHP",
            session=session,
            vector_store=temp_vector_store,
            ai_client=mock_ai,
            embedding_client=mock_ai,
        )
        assert vec_id_neg is not None

        assert temp_vector_store.count(VectorStore.COLLECTION_USER_FEEDBACK) == 2


@pytest.mark.asyncio
async def test_compute_feedback_score_adjustment(temp_vector_store: VectorStore) -> None:
    """Verify score adjustments calculate delta when checking similar job descriptions."""
    mock_ai = MockAIClient()

    with Session(engine) as session:
        job_disliked = Job(
            source="stepstone",
            title="Onsite PHP Maintenance",
            company="OldTech",
            location="Stuttgart",
            url="https://example.com/old",
            status=JobStatus.NOT_A_FIT.value,
            dedup_hash="hash-feedback-calc-1",
        )
        session.add(job_disliked)
        session.commit()
        session.refresh(job_disliked)

        await FeedbackManager.record_job_feedback(
            job_id=job_disliked.id,
            status=JobStatus.NOT_A_FIT.value,
            note_text="Onsite only, no remote, legacy maintenance",
            session=session,
            vector_store=temp_vector_store,
            ai_client=mock_ai,
            embedding_client=mock_ai,
        )

    # Check score adjustment for similar disliked text
    score_delta, reasons = await FeedbackManager.compute_feedback_score_adjustment(
        job_text="Title: Onsite PHP Maintenance\nCompany: OldTech\nStatus: not a good fit\nCandidate Note: Onsite only, no remote, legacy maintenance",
        vector_store=temp_vector_store,
        ai_client=mock_ai,
        embedding_client=mock_ai,
    )

    # Identical query should yield high cosine similarity resulting in negative score penalty
    assert score_delta < 0
    assert len(reasons) >= 1
    assert "penalty" in reasons[0]


@pytest.mark.asyncio
async def test_feedback_vectors_use_job_owner_and_local_client(temp_vector_store, monkeypatch, authenticated_user):
    cloud, local = MockAIClient(), MockAIClient()
    cloud.embed = AsyncMock(return_value=[1.0, 0.0])
    local.embed = AsyncMock(return_value=[1.0, 0.0])
    calls = []

    def resolve(session=None, user_id=None):
        calls.append((session, user_id))
        return local

    monkeypatch.setattr("app.ai.feedback.get_embedding_client", resolve, raising=False)
    owner = authenticated_user["id"]
    with Session(engine) as session:
        job = Job(user_id=owner, title="Python", company="Test", location="Remote", source="test", url="https://example.com", dedup_hash="owned-feedback")
        session.add(job)
        session.commit()
        vector_id = await FeedbackManager.record_job_feedback(job.id, "applied", "Good", session, temp_vector_store, cloud)
        assert vector_id
        assert cloud.embed.await_count == 0
        assert calls == [(session, owner)]
        delta, reasons = await FeedbackManager.compute_feedback_score_adjustment(
            "Python", temp_vector_store, cloud, session=session, user_id=owner,
        )
        assert delta == 10 and reasons
        assert cloud.embed.await_count == 0
        assert calls == [(session, owner), (session, owner)]
        assert await FeedbackManager.record_job_feedback(
            job.id, "rejected", "Foreign", session, temp_vector_store, cloud, user_id=owner + 1,
        ) is None
        assert local.embed.await_count == 2


@pytest.mark.asyncio
async def test_other_owners_feedback_does_not_trigger_embedding(temp_vector_store):
    collection_name = VectorStore.COLLECTION_USER_FEEDBACK
    temp_vector_store.upsert_documents(
        collection_name,
        ["u2:feedback"],
        ["Other owner's saved feedback"],
        [{"user_id": 2, "sentiment": "positive"}],
        [[1.0, 0.0]],
    )
    local = MockAIClient()
    local.embed = AsyncMock(return_value=[1.0, 0.0])

    result = await FeedbackManager.compute_feedback_score_adjustment(
        "Owner one's job text",
        temp_vector_store,
        embedding_client=local,
        user_id=1,
    )

    assert result == (0, [])
    assert local.embed.await_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["unavailable", "embedding_dimension"])
async def test_feedback_failure_is_explicit_and_non_destructive(temp_vector_store, category):
    collection_name = VectorStore.COLLECTION_USER_FEEDBACK
    temp_vector_store.upsert_documents(collection_name, ["old"], ["Saved"], [{"sentiment":"positive"}], [[1.0, 0.0]])
    local = MockAIClient()
    if category == "unavailable":
        local.embed = AsyncMock(side_effect=AIProviderError("ollama", "nomic-embed-text", category))
    else:
        local.embed = AsyncMock(return_value=[1.0, 0.0, 0.0])
    with Session(engine) as session:
        job = Job(title="Python", company="Test", location="Remote", source="test", url="https://example.com", dedup_hash="failed-feedback")
        session.add(job)
        session.commit()
        with pytest.raises(AIProviderError) as error:
            await FeedbackManager.record_job_feedback(job.id, "applied", "New", session, temp_vector_store, embedding_client=local)
        assert error.value.category == category
        with pytest.raises(AIProviderError) as error:
            await FeedbackManager.compute_feedback_score_adjustment("Python", temp_vector_store, embedding_client=local)
        assert error.value.category == category
    assert temp_vector_store.get_or_create_collection(collection_name).get()["documents"] == ["Saved"]
