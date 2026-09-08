"""Semantic candidate profile chunking, vector embedding, and similarity search."""

import logging
from typing import Any
from app.ai.client import BaseAIClient
from app.ai.profile_extractor import ExtractedProfile
from app.db.vector import VectorStore

logger = logging.getLogger("jobot.ai.embeddings")


class ProfileEmbedder:
    """Manages semantic chunking and ChromaDB vector embeddings for candidate profiles."""

    @classmethod
    def chunk_profile(cls, profile: ExtractedProfile) -> list[dict[str, Any]]:
        """Split extracted candidate profile into distinct semantic vector chunks."""
        chunks: list[dict[str, Any]] = []

        # 1. Summary Chunk
        headline_text = f"Headline: {profile.headline}\n" if profile.headline else ""
        summary_text = f"Candidate: {profile.full_name}\n{headline_text}Summary: {profile.summary}".strip()
        if summary_text:
            chunks.append({
                "id": "profile_summary",
                "text": summary_text,
                "metadata": {
                    "chunk_type": "summary",
                    "full_name": profile.full_name,
                },
            })

        # 2. Skills Chunk
        skills_str = ", ".join(profile.skills)
        active_str = ", ".join(profile.active_search_skills) if profile.active_search_skills else skills_str
        if skills_str:
            chunks.append({
                "id": "profile_skills",
                "text": f"Core Competencies and Skills: {skills_str}\nPrimary Focus Skills: {active_str}",
                "metadata": {
                    "chunk_type": "skills",
                    "skill_count": len(profile.skills),
                },
            })

        # 3. Experience & Target Roles Chunk
        exp_text = (
            f"Experience: {profile.experience_years} years.\n"
            f"Work Preference: {profile.work_preference}.\n"
            f"Target Roles: {', '.join(profile.target_titles)}\n"
            f"Target Locations: {', '.join(profile.target_locations)}"
        ).strip()
        chunks.append({
            "id": "profile_experience",
            "text": exp_text,
            "metadata": {
                "chunk_type": "experience",
                "experience_years": float(profile.experience_years),
            },
        })

        return chunks

    @classmethod
    async def embed_and_store_profile(
        cls,
        profile: ExtractedProfile,
        vector_store: VectorStore,
        ai_client: BaseAIClient,
    ) -> int:
        """Embed and upsert candidate profile chunks into ChromaDB cv_profile collection."""
        chunks = cls.chunk_profile(profile)
        if not chunks:
            return 0

        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # Generate embeddings in parallel / batch
        embeddings: list[list[float]] = []
        for doc in documents:
            emb = await ai_client.embed(doc)
            embeddings.append(emb)

        vector_store.upsert_documents(
            collection_name=VectorStore.COLLECTION_CV_PROFILE,
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        logger.info("Embedded and upserted %d candidate profile chunks into ChromaDB", len(ids))
        return len(ids)

    @classmethod
    async def compute_semantic_similarity(
        cls,
        job_text: str,
        vector_store: VectorStore,
        ai_client: BaseAIClient,
    ) -> float:
        """Compute cosine similarity score (0.0 to 1.0) between job description and candidate profile."""
        if vector_store.count(VectorStore.COLLECTION_CV_PROFILE) == 0:
            logger.warning("cv_profile collection is empty; cannot compute semantic similarity")
            return 0.5  # Neutral default

        try:
            job_embedding = await ai_client.embed(job_text[:4000])
            results = vector_store.query_similar(
                collection_name=VectorStore.COLLECTION_CV_PROFILE,
                query_embeddings=[job_embedding],
                n_results=3,
            )

            # Extract distances (ChromaDB cosine space: distance = 1 - cosine_similarity)
            distances = results.get("distances", [[]])[0]
            if not distances:
                return 0.5

            # Convert cosine distances to similarities (0.0 to 1.0)
            similarities = [max(0.0, min(1.0, 1.0 - float(d))) for d in distances]
            avg_similarity = sum(similarities) / len(similarities)
            return round(avg_similarity, 3)

        except Exception as err:
            logger.warning("Failed to compute semantic similarity (%s), returning baseline", err)
            return 0.5
