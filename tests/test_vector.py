"""Tests for ChromaDB VectorStore manager and collection lifecycle."""

import shutil
import tempfile
from pathlib import Path
from typing import Generator
import pytest

from app.db.vector import VectorStore


@pytest.fixture
def temp_vector_store() -> Generator[VectorStore, None, None]:
    """Provide VectorStore backed by an isolated temporary directory."""
    temp_dir = tempfile.mkdtemp(prefix="jobot_chroma_test_")
    store = VectorStore(persist_dir=temp_dir)
    yield store
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_vector_store_collections_initialization(temp_vector_store: VectorStore) -> None:
    """Verify standard collections are created without error."""
    cv_col = temp_vector_store.get_or_create_collection(VectorStore.COLLECTION_CV_PROFILE)
    job_col = temp_vector_store.get_or_create_collection(VectorStore.COLLECTION_JOB_DESCRIPTIONS)
    fb_col = temp_vector_store.get_or_create_collection(VectorStore.COLLECTION_USER_FEEDBACK)

    assert cv_col.name == "cv_profile"
    assert job_col.name == "job_descriptions"
    assert fb_col.name == "user_feedback"


def test_upsert_query_and_delete(temp_vector_store: VectorStore) -> None:
    """Test inserting, querying, and deleting documents in ChromaDB."""
    collection = VectorStore.COLLECTION_JOB_DESCRIPTIONS

    ids = ["job-1", "job-2"]
    docs = [
        "Senior Python Engineer with FastAPI and Docker experience in Berlin",
        "Frontend React Developer with TypeScript and Next.js in Munich",
    ]
    metadatas = [
        {"job_id": 1, "company": "TechCorp", "source": "linkedin"},
        {"job_id": 2, "company": "WebStudio", "source": "stepstone"},
    ]

    # Upsert
    temp_vector_store.upsert_documents(
        collection_name=collection,
        ids=ids,
        documents=docs,
        metadatas=metadatas,
    )

    assert temp_vector_store.count(collection) == 2

    # Query
    results = temp_vector_store.query_similar(
        collection_name=collection,
        query_texts=["Python FastAPI backend developer"],
        n_results=1,
    )

    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "job-1"
    assert results["metadatas"][0][0]["company"] == "TechCorp"

    # Delete
    temp_vector_store.delete_documents(collection_name=collection, ids=["job-1"])
    assert temp_vector_store.count(collection) == 1

    # Reset collection
    temp_vector_store.reset_collection(collection)
    assert temp_vector_store.count(collection) == 0
