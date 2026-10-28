"""Maintain profile and job vectors in one fixed local embedding space.

Generation routing must not move private text to a cloud embedding API.
The independent resolver pins production requests to nomic-embed-text.
Legacy generation arguments remain accepted but cannot override that rule.
Explicit embedding injection is a separate seam for isolated transport tests.
Every profile chunk is embedded before the first persistent upsert.
Nonempty, finite, homogeneous vectors must match any existing collection.
Incompatible collections require an explicit backed-up operator re-index.
No reset, destructive migration or automatic re-embedding is performed here.
Empty collections alone may return neutral similarity without a request.
Existing collection IDs/visibility are preserved, not redesigned by routing.
"""

import logging
import math
from typing import Any

from sqlmodel import Session, select

from app.ai.client import AIProviderError, BaseAIClient, _provider_error, get_embedding_client
from app.ai.profile_extractor import ExtractedProfile
from app.db.models import User, UserProfile
from app.db.ownership import decrypt_profile
from app.db.vector import VectorStore

logger = logging.getLogger("jobot.ai.embeddings")


def validate_local_vectors(vector_store: VectorStore, collection_name: str, embeddings: list[list[float]]) -> None:
    """Check the whole batch and existing space before a write or query.

    Sampling a stored vector is read-only and avoids relying on Chroma's
    version-specific dimension exceptions. Incompatible data remains intact;
    re-indexing is an explicit operator action, never an automatic recovery.
    """
    failure = AIProviderError("ollama", "nomic-embed-text", "embedding_dimension")
    failure.message = "Embedding dimensions are incompatible. Explicit re-index required after backup."
    failure.args = (f"embedding_dimension: {failure.message}",)
    if not embeddings or any(not isinstance(vector, (list, tuple)) or not vector for vector in embeddings):
        raise failure
    dimensions = {len(vector) for vector in embeddings}
    if len(dimensions) != 1 or any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for vector in embeddings for value in vector
    ):
        raise failure
    collection = vector_store.get_or_create_collection(collection_name)
    if collection.count():
        stored = collection.get(limit=1, include=["embeddings"]).get("embeddings")
        if stored is None or len(stored) == 0 or len(stored[0]) != len(embeddings[0]):
            raise failure


class ProfileEmbedder:
    """Manages semantic chunking and ChromaDB vector embeddings for candidate profiles."""

    CHUNK_IDS = ("profile_summary", "profile_skills", "profile_experience", "profile_history")

    @classmethod
    def _owner_from_summary_text(cls, session: Session, users: list[User], stored: dict[str, Any], old_ids: list[str]) -> int | None:
        """Return the single account whose profile reproduces the legacy summary chunk exactly."""
        if "profile_summary" not in old_ids:
            return None
        document = list(stored["documents"])[old_ids.index("profile_summary")]
        matches: list[int] = []
        for user in users:
            profile = session.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
            if not profile or not profile.full_name:
                continue
            # Detach before decrypting so plaintext is never flushed back to the row.
            session.expunge(profile)
            try:
                decrypt_profile(profile, user.id)
            except Exception:
                continue
            headline = f"Headline: {profile.headline}\n" if profile.headline else ""
            expected = f"Candidate: {profile.full_name}\n{headline}Summary: {profile.bio or ''}".strip()
            if expected == document:
                matches.append(user.id)
        return matches[0] if len(matches) == 1 else None

    @classmethod
    def backfill_legacy_cv_vectors(cls, session: Session, vector_store: VectorStore) -> int:
        """Re-key fixed-id, ownerless CV vectors to their owner; no re-embedding.

        The owner is the sole account, or with several accounts the only one whose
        profile reproduces the stored summary chunk exactly. Otherwise the owner is
        ambiguous and legacy vectors stay unreachable (owner queries filter them
        out) rather than leak.
        """
        users = session.exec(select(User)).all()
        if not users or any(u.id is None for u in users):
            return 0
        collection = vector_store.get_or_create_collection(VectorStore.COLLECTION_CV_PROFILE)
        stored = collection.get(ids=list(cls.CHUNK_IDS), include=["documents", "metadatas", "embeddings"])
        old_ids = list(stored.get("ids") or [])
        if not old_ids:
            return 0
        if len(users) == 1:
            owner = users[0].id
        else:
            owner = cls._owner_from_summary_text(session, users, stored, old_ids)
            if owner is None:
                return 0
        embeddings = [list(map(float, e)) for e in stored["embeddings"]]
        metadatas = [{**(m or {}), "user_id": owner} for m in stored["metadatas"] or [{}] * len(old_ids)]
        # Upsert under the new ids before deleting, so a crash loses nothing.
        vector_store.upsert_documents(
            VectorStore.COLLECTION_CV_PROFILE,
            [f"u{owner}:{i}" for i in old_ids],
            list(stored["documents"]),
            metadatas,
            embeddings,
        )
        vector_store.delete_documents(VectorStore.COLLECTION_CV_PROFILE, old_ids)
        logger.info("Re-keyed %d legacy CV vectors to user %s", len(old_ids), owner)
        return len(old_ids)

    @classmethod
    def delete_user_profile(cls, vector_store: VectorStore, user_id: int) -> None:
        """Remove only this owner's CV vectors."""
        vector_store.delete_documents(
            VectorStore.COLLECTION_CV_PROFILE, [f"u{user_id}:{i}" for i in cls.CHUNK_IDS]
        )

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

        # 4. Experience history chunk (roles, companies, durations, descriptions)
        history_lines = []
        for entry in profile.experience_history:
            parts = [str(entry.get(k)).strip() for k in ("title", "company", "duration", "description") if entry.get(k)]
            if parts:
                history_lines.append(" | ".join(parts))
        if history_lines:
            chunks.append({
                "id": "profile_history",
                "text": "Career History:\n" + "\n".join(history_lines),
                "metadata": {
                    "chunk_type": "history",
                    "entry_count": len(history_lines),
                },
            })

        return chunks

    @classmethod
    async def embed_and_store_profile(
        cls,
        profile: ExtractedProfile,
        vector_store: VectorStore,
        ai_client: BaseAIClient | None = None,
        *,
        embedding_client: BaseAIClient | None = None,
        session: Session | None = None,
        user_id: int | None = None,
    ) -> int:
        """Embed profile chunks locally; generation injection is never a vector override.

        Keep the legacy positional ai_client argument for existing callers.
        Only the explicit embedding_client seam overrides local resolution in
        isolated tests. Collect and validate every vector before any upsert so
        a failed chunk cannot leave a partially replaced candidate profile.
        """
        chunks = cls.chunk_profile(profile)
        if not chunks:
            return 0

        # Owner-prefixed ids keep one account's CV from overwriting another's.
        prefix = f"u{user_id}:" if user_id is not None else ""
        ids = [prefix + c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [
            {**c["metadata"], **({"user_id": user_id} if user_id is not None else {})}
            for c in chunks
        ]
        owner_ids = [prefix + legacy for legacy in cls.CHUNK_IDS]
        client = embedding_client or get_embedding_client(session, user_id)
        try:
            embeddings = [await client.embed(doc) for doc in documents]
            validate_local_vectors(vector_store, VectorStore.COLLECTION_CV_PROFILE, embeddings)
            vector_store.upsert_documents(
                collection_name=VectorStore.COLLECTION_CV_PROFILE,
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )
            # Only remove stale chunks after replacement data is durably stored.
            stale = [i for i in owner_ids if i not in ids]
            if stale and user_id is not None:
                vector_store.delete_documents(VectorStore.COLLECTION_CV_PROFILE, stale)
        except AIProviderError:
            raise
        except Exception as err:
            raise _provider_error("ollama", "nomic-embed-text", err) from None

        logger.info("Embedded and upserted %d candidate profile chunks into ChromaDB", len(ids))
        return len(ids)

    @classmethod
    async def compute_semantic_similarity(
        cls,
        job_text: str,
        vector_store: VectorStore,
        ai_client: BaseAIClient | None = None,
        *,
        embedding_client: BaseAIClient | None = None,
        session: Session | None = None,
        user_id: int | None = None,
    ) -> float:
        """Compute similarity only after a validated local embedding succeeds.

        No-data neutrality is distinct from transport or dimension failure.
        The owner selects the local endpoint, never the generation adapter.
        """
        try:
            where = {"user_id": user_id} if user_id is not None else None
            if vector_store.count(VectorStore.COLLECTION_CV_PROFILE, where=where) == 0:
                return 0.5
            client = embedding_client or get_embedding_client(session, user_id)
            job_embedding = await client.embed(job_text[:4000])
            validate_local_vectors(vector_store, VectorStore.COLLECTION_CV_PROFILE, [job_embedding])
            results = vector_store.query_similar(
                collection_name=VectorStore.COLLECTION_CV_PROFILE,
                query_embeddings=[job_embedding],
                n_results=3,
                where=where,
            )

            # Extract distances (ChromaDB cosine space: distance = 1 - cosine_similarity)
            distances = results.get("distances", [[]])[0]
            if not distances:
                return 0.5

            # Convert cosine distances to similarities (0.0 to 1.0)
            similarities = [max(0.0, min(1.0, 1.0 - float(d))) for d in distances]
            avg_similarity = sum(similarities) / len(similarities)
            return round(avg_similarity, 3)

        except AIProviderError:
            raise
        except Exception as err:
            raise _provider_error("ollama", "nomic-embed-text", err) from None
