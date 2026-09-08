"""Tests for candidate feedback vector recording and adaptive fit score re-weighting."""

import shutil
import tempfile
from collections.abc import Generator

import pytest
from sqlmodel import Session

from app.ai.client import MockAIClient
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
        )

    # Check score adjustment for similar disliked text
    score_delta, reasons = await FeedbackManager.compute_feedback_score_adjustment(
        job_text="Title: Onsite PHP Maintenance\nCompany: OldTech\nStatus: not a good fit\nCandidate Note: Onsite only, no remote, legacy maintenance",
        vector_store=temp_vector_store,
        ai_client=mock_ai,
    )

    # Identical query should yield high cosine similarity resulting in negative score penalty
    assert score_delta < 0
    assert len(reasons) >= 1
    assert "penalty" in reasons[0]
