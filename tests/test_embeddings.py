"""Tests for candidate profile vector embeddings and ChromaDB RAG search."""

import shutil
import tempfile
from collections.abc import Generator
from unittest.mock import AsyncMock

import pytest

from app.ai.client import AIProviderError, MockAIClient
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
        embedding_client=mock_client,
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
        embedding_client=mock_client,
    )

    score = await ProfileEmbedder.compute_semantic_similarity(
        job_text="Senior Python Developer with FastAPI and Postgres skills in Berlin.",
        vector_store=temp_vector_store,
        ai_client=mock_client,
        embedding_client=mock_client,
    )

    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


@pytest.mark.asyncio
async def test_profile_and_job_vectors_ignore_cloud_generation(temp_vector_store, monkeypatch):
    cloud, local = MockAIClient(), MockAIClient()
    cloud.embed = AsyncMock(return_value=[1.0, 0.0])
    local.embed = AsyncMock(return_value=[1.0, 0.0])
    calls = []

    def resolve(session=None, user_id=None):
        calls.append((session, user_id))
        return local

    monkeypatch.setattr("app.ai.embeddings.get_embedding_client", resolve, raising=False)
    profile = ExtractedProfile(full_name="Local Only", skills=["Python"])
    await ProfileEmbedder.embed_and_store_profile(profile, temp_vector_store, cloud)
    assert cloud.embed.await_count == 0
    score = await ProfileEmbedder.compute_semantic_similarity("Python", temp_vector_store, cloud)
    assert score == 1.0
    assert cloud.embed.await_count == 0
    assert local.embed.await_count == 4
    assert calls == [(None, None), (None, None)]


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [[], [float("nan"), 0.0], [float("inf"), 1.0], [1.0, 0.0, 0.0]])
async def test_incompatible_vectors_preserve_collection(temp_vector_store, bad):
    collection_name = VectorStore.COLLECTION_CV_PROFILE
    temp_vector_store.upsert_documents(collection_name, ["original"], ["Saved"], embeddings=[[1.0, 0.0]])
    collection = temp_vector_store.get_or_create_collection(collection_name)
    before = collection.get(include=["documents", "embeddings"])
    local = MockAIClient()
    local.embed = AsyncMock(return_value=bad)
    with pytest.raises(AIProviderError) as error:
        await ProfileEmbedder.embed_and_store_profile(
            ExtractedProfile(full_name="Changed", skills=["Python"]), temp_vector_store,
            MockAIClient(), embedding_client=local,
        )
    assert error.value.category == "embedding_dimension"
    after = collection.get(include=["documents", "embeddings"])
    assert after["ids"] == before["ids"]
    assert after["documents"] == before["documents"]
    assert (after["embeddings"] == before["embeddings"]).all()
    with pytest.raises(AIProviderError):
        await ProfileEmbedder.compute_semantic_similarity("Changed", temp_vector_store, embedding_client=local)
    assert collection.count() == 1


@pytest.mark.asyncio
async def test_profile_partial_embedding_failure_has_no_writes(temp_vector_store):
    local = MockAIClient()
    failure = AIProviderError("ollama", "nomic-embed-text", "unavailable")
    local.embed = AsyncMock(side_effect=[[1.0, 0.0], failure])
    with pytest.raises(AIProviderError) as error:
        await ProfileEmbedder.embed_and_store_profile(
            ExtractedProfile(full_name="Test", skills=["Python"]), temp_vector_store,
            embedding_client=local,
        )
    assert error.value is failure
    assert temp_vector_store.count(VectorStore.COLLECTION_CV_PROFILE) == 0


@pytest.mark.asyncio
async def test_mixed_dimension_batch_never_partially_replaces_profile(temp_vector_store):
    collection_name = VectorStore.COLLECTION_CV_PROFILE
    temp_vector_store.upsert_documents(collection_name, ["profile_summary"], ["Original"], embeddings=[[1.0, 0.0]])
    local = MockAIClient()
    local.embed = AsyncMock(side_effect=[[1.0, 0.0], [1.0], [1.0, 0.0]])
    with pytest.raises(AIProviderError) as error:
        await ProfileEmbedder.embed_and_store_profile(
            ExtractedProfile(full_name="Changed", skills=["Python"]), temp_vector_store, embedding_client=local,
        )
    assert error.value.category == "embedding_dimension"
    assert "re-index" in str(error.value)
    collection = temp_vector_store.get_or_create_collection(collection_name)
    assert collection.get()["documents"] == ["Original"]
    assert collection.get(include=["embeddings"])["embeddings"].tolist() == [[1.0, 0.0]]


@pytest.mark.asyncio
async def test_profile_upsert_failure_preserves_stale_owner_vectors(temp_vector_store, monkeypatch):
    collection_name = VectorStore.COLLECTION_CV_PROFILE
    local = MockAIClient()
    local.embed = AsyncMock(return_value=[1.0, 0.0])
    await ProfileEmbedder.embed_and_store_profile(
        ExtractedProfile(
            full_name="Old Candidate",
            summary="Old profile",
            skills=["Python"],
            experience_history=[{"title": "Engineer", "company": "Old Company"}],
        ),
        temp_vector_store,
        embedding_client=local,
        user_id=7,
    )
    collection = temp_vector_store.get_or_create_collection(collection_name)
    before = collection.get(include=["documents", "metadatas", "embeddings"])

    def fail_upsert(*args, **kwargs):
        raise RuntimeError("injected replacement failure")

    monkeypatch.setattr(temp_vector_store, "upsert_documents", fail_upsert)
    with pytest.raises(AIProviderError):
        await ProfileEmbedder.embed_and_store_profile(
            ExtractedProfile(full_name="New Candidate", summary="New profile", skills=["Go"]),
            temp_vector_store,
            embedding_client=local,
            user_id=7,
        )

    after = collection.get(include=["documents", "metadatas", "embeddings"])
    assert after["ids"] == before["ids"]
    assert after["documents"] == before["documents"]
    assert after["metadatas"] == before["metadatas"]
    assert (after["embeddings"] == before["embeddings"]).all()


@pytest.mark.asyncio
async def test_cv_vectors_are_isolated_between_users(temp_vector_store):
    one, two = MockAIClient(), MockAIClient()
    one.embed = AsyncMock(return_value=[1.0, 0.0])
    two.embed = AsyncMock(return_value=[0.0, 1.0])
    await ProfileEmbedder.embed_and_store_profile(
        ExtractedProfile(full_name="One", skills=["Python"]), temp_vector_store, embedding_client=one, user_id=1)
    await ProfileEmbedder.embed_and_store_profile(
        ExtractedProfile(full_name="Two", skills=["Go"]), temp_vector_store, embedding_client=two, user_id=2)
    name = VectorStore.COLLECTION_CV_PROFILE
    # Second upload must not overwrite the first user's chunks.
    assert temp_vector_store.count(name, where={"user_id": 1}) == 3
    assert temp_vector_store.count(name, where={"user_id": 2}) == 3
    assert temp_vector_store.count(name) == 6
    query = MockAIClient()
    query.embed = AsyncMock(return_value=[1.0, 0.0])
    assert await ProfileEmbedder.compute_semantic_similarity("x", temp_vector_store, embedding_client=query, user_id=1) == 1.0
    assert await ProfileEmbedder.compute_semantic_similarity("x", temp_vector_store, embedding_client=query, user_id=2) == 0.0
    assert await ProfileEmbedder.compute_semantic_similarity("x", temp_vector_store, embedding_client=query, user_id=3) == 0.5
    ProfileEmbedder.delete_user_profile(temp_vector_store, 1)
    assert temp_vector_store.count(name, where={"user_id": 1}) == 0
    assert temp_vector_store.count(name, where={"user_id": 2}) == 3


def test_legacy_cv_vectors_backfill_only_for_single_account(temp_vector_store):
    from sqlmodel import Session, select

    from app.db.database import engine
    from app.db.models import User

    name = VectorStore.COLLECTION_CV_PROFILE
    temp_vector_store.upsert_documents(
        name, ["profile_summary", "profile_skills"], ["a", "b"],
        [{"chunk_type": "summary"}, {"chunk_type": "skills"}], [[1.0, 0.0], [0.0, 1.0]])
    with Session(engine) as session:
        session.add(User(email="a@example.com", password_hash="x"))
        session.add(User(email="b@example.com", password_hash="x"))
        session.commit()
        assert ProfileEmbedder.backfill_legacy_cv_vectors(session, temp_vector_store) == 0
        session.delete(session.exec(select(User).where(User.email == "b@example.com")).one())
        session.commit()
        owner = session.exec(select(User)).one().id
        assert ProfileEmbedder.backfill_legacy_cv_vectors(session, temp_vector_store) == 2
        assert ProfileEmbedder.backfill_legacy_cv_vectors(session, temp_vector_store) == 0
    assert temp_vector_store.count(name, where={"user_id": owner}) == 2
    assert temp_vector_store.get_or_create_collection(name).get(ids=["profile_summary"])["ids"] == []


def test_legacy_cv_vectors_multi_account_rekeyed_only_on_exact_profile_match(temp_vector_store):
    from sqlmodel import Session

    from app.db.database import engine
    from app.db.models import User, UserProfile
    from app.db.ownership import encrypt_profile

    name = VectorStore.COLLECTION_CV_PROFILE
    summary = "Candidate: Alice Owner\nHeadline: Backend\nSummary: Builds APIs."
    temp_vector_store.upsert_documents(
        name, ["profile_summary", "profile_skills"], [summary, "skills"],
        [{"chunk_type": "summary"}, {"chunk_type": "skills"}], [[1.0, 0.0], [0.0, 1.0]])
    with Session(engine) as session:
        alice = User(email="alice@example.com", password_hash="x")
        bob = User(email="bob@example.com", password_hash="x")
        session.add(alice)
        session.add(bob)
        session.commit()
        for user, full_name, bio in ((alice, "Alice Owner", "Builds APIs."), (bob, "Bob Other", "Other.")):
            profile = UserProfile(user_id=user.id, full_name=full_name, headline="Backend", bio=bio)
            session.add(encrypt_profile(profile, user.id))
        session.commit()
        alice_id = alice.id
        assert ProfileEmbedder.backfill_legacy_cv_vectors(session, temp_vector_store) == 2
    assert temp_vector_store.count(name, where={"user_id": alice_id}) == 2


def test_legacy_cv_vectors_multi_account_ambiguous_stays_unowned(temp_vector_store):
    from sqlmodel import Session

    from app.db.database import engine
    from app.db.models import User, UserProfile
    from app.db.ownership import encrypt_profile

    name = VectorStore.COLLECTION_CV_PROFILE
    temp_vector_store.upsert_documents(
        name, ["profile_summary"], ["Candidate: Same Name\nSummary: x"], [{"chunk_type": "summary"}], [[1.0, 0.0]])
    with Session(engine) as session:
        for email in ("a@example.com", "b@example.com"):
            user = User(email=email, password_hash="x")
            session.add(user)
            session.commit()
            session.add(encrypt_profile(UserProfile(user_id=user.id, full_name="Same Name", bio="x"), user.id))
        session.commit()
        assert ProfileEmbedder.backfill_legacy_cv_vectors(session, temp_vector_store) == 0
