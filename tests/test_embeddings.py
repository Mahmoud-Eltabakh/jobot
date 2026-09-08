"""Tests for candidate profile vector embeddings and ChromaDB RAG search."""

import shutil
import tempfile
from collections.abc import Generator

import pytest

from app.ai.client import MockAIClient
from app.ai.embeddings import ProfileEmbedder
from app.ai.profile_extractor import ExtractedProfile
from app.db.vector import VectorStore


@pytest.fixture
def temp_vector_store() -> Generator[VectorStore, None, None]:
    """Provide VectorStore backed by an isolated temporary directory."""
    temp_dir = tempfile.mkdtemp(prefix="jobot_chroma_embed_test_")
    store = VectorStore(persist_dir=temp_dir)
    yield store
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_chunk_profile() -> None:
    """Verify ProfileEmbedder splits profile into semantic chunks."""
    profile = ExtractedProfile(
        full_name="Alice Senior Dev",
        summary="Experienced Python backend developer with cloud and container expertise.",
        skills=["Python", "FastAPI", "Docker", "ChromaDB"],
        experience_years=5.5,
        target_titles=["Senior Python Developer", "Backend Lead"],
        target_locations=["Berlin", "Remote"],
    )

    chunks = ProfileEmbedder.chunk_profile(profile)
    assert len(chunks) == 3
    chunk_ids = [c["id"] for c in chunks]
    assert "profile_summary" in chunk_ids
    assert "profile_skills" in chunk_ids
    assert "profile_experience" in chunk_ids

    skills_chunk = next(c for c in chunks if c["id"] == "profile_skills")
    assert "FastAPI" in skills_chunk["text"]
    assert skills_chunk["metadata"]["skill_count"] == 4


@pytest.mark.asyncio
async def test_embed_and_store_profile(temp_vector_store: VectorStore) -> None:
    """Test embedding and storing profile chunks in ChromaDB."""
    mock_client = MockAIClient()
    profile = ExtractedProfile(
        full_name="Bob Engineer",
        summary="Fullstack dev specializing in FastAPI and React.",
        skills=["FastAPI", "React", "Docker"],
        experience_years=4.0,
        target_titles=["Fullstack Developer"],
        target_locations=["Remote"],
    )

    count = await ProfileEmbedder.embed_and_store_profile(
        profile=profile,
        vector_store=temp_vector_store,
        ai_client=mock_client,
    )

    assert count == 3
    assert temp_vector_store.count(VectorStore.COLLECTION_CV_PROFILE) == 3


@pytest.mark.asyncio
async def test_compute_semantic_similarity(temp_vector_store: VectorStore) -> None:
    """Test semantic similarity computation against candidate vectors."""
    mock_client = MockAIClient()
    profile = ExtractedProfile(
        full_name="Charlie Coder",
        summary="Python backend engineer with FastAPI expertise.",
        skills=["Python", "FastAPI"],
        experience_years=3.0,
        target_titles=["Backend Engineer"],
        target_locations=["Remote"],
    )

    await ProfileEmbedder.embed_and_store_profile(
        profile=profile,
        vector_store=temp_vector_store,
        ai_client=mock_client,
    )

    score = await ProfileEmbedder.compute_semantic_similarity(
        job_text="Senior Python Developer with FastAPI and Postgres skills in Berlin.",
        vector_store=temp_vector_store,
        ai_client=mock_client,
    )

    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0
