"""ChromaDB local persistent vector database client and collection manager."""

import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from app.core.config import get_settings

logger = logging.getLogger("jobot.vector")


class VectorStore:
    """Manages local persistent vector storage using ChromaDB."""

    COLLECTION_CV_PROFILE = "cv_profile"
    COLLECTION_JOB_DESCRIPTIONS = "job_descriptions"
    COLLECTION_USER_FEEDBACK = "user_feedback"

    KNOWN_COLLECTIONS = {
        COLLECTION_CV_PROFILE,
        COLLECTION_JOB_DESCRIPTIONS,
        COLLECTION_USER_FEEDBACK,
    }

    def __init__(self, persist_dir: str | None = None) -> None:
        """Initialize ChromaDB PersistentClient."""
        settings = get_settings()
        self.persist_dir = persist_dir or settings.chroma_dir
        
        # Ensure persistence directory exists
        path = Path(self.persist_dir)
        if not path.exists():
            os.makedirs(path, exist_ok=True)
            
        logger.info("Initializing ChromaDB PersistentClient at %s", self.persist_dir)
        self.client: ClientAPI = chromadb.PersistentClient(path=str(path))

    def get_or_create_collection(self, collection_name: str) -> Collection:
        """Get existing collection or create a new one."""
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_documents(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> None:
        """Insert or update documents in the specified collection."""
        collection = self.get_or_create_collection(collection_name)
        
        kwargs: dict[str, Any] = {
            "ids": ids,
            "documents": documents,
        }
        if metadatas is not None:
            kwargs["metadatas"] = metadatas
        if embeddings is not None:
            kwargs["embeddings"] = embeddings

        collection.upsert(**kwargs)
        logger.debug("Upserted %d documents into %s", len(ids), collection_name)

    def query_similar(
        self,
        collection_name: str,
        query_texts: list[str] | None = None,
        query_embeddings: list[list[float]] | None = None,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query collection for semantically similar documents."""
        collection = self.get_or_create_collection(collection_name)
        
        kwargs: dict[str, Any] = {"n_results": n_results}
        if query_texts is not None:
            kwargs["query_texts"] = query_texts
        if query_embeddings is not None:
            kwargs["query_embeddings"] = query_embeddings
        if where is not None:
            kwargs["where"] = where

        results = collection.query(**kwargs)
        return dict(results)

    def delete_documents(self, collection_name: str, ids: list[str]) -> None:
        """Delete documents by ID from a collection."""
        collection = self.get_or_create_collection(collection_name)
        collection.delete(ids=ids)
        logger.debug("Deleted %d documents from %s", len(ids), collection_name)

    def count(self, collection_name: str) -> int:
        """Count total documents stored in a collection."""
        collection = self.get_or_create_collection(collection_name)
        return collection.count()

    def reset_collection(self, collection_name: str) -> None:
        """Delete and recreate a collection to purge all documents."""
        try:
            self.client.delete_collection(collection_name)
            logger.info("Purged collection %s", collection_name)
        except Exception as e:
            logger.warning("Error deleting collection %s: %s", collection_name, e)
        self.get_or_create_collection(collection_name)


_vector_store_instance: VectorStore | None = None


def get_vector_store(persist_dir: str | None = None) -> VectorStore:
    """Return shared or new VectorStore instance."""
    global _vector_store_instance
    if _vector_store_instance is None or persist_dir is not None:
        _vector_store_instance = VectorStore(persist_dir=persist_dir)
    return _vector_store_instance
