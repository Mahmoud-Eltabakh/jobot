"""Record and query feedback without coupling vectors to generation routing.

Private notes and job text use the fixed local nomic-embed-text resolver.
Record writes derive their owner from the loaded job, not global settings.
An explicit authenticated owner must match before any embedding request.
Retrieval receives the evaluator's separate local client and owner context.
Legacy positional generation arguments never become embedding overrides.
Both paths validate vector shape and existing dimensions before Chroma I/O.
Provider errors propagate without fabricated success or neutral adjustments.
Empty collections alone retain the historical no-feedback behavior.
No account-partitioning migration or collection reset is performed here.
"""

import logging
import time

from sqlmodel import Session

from app.ai.client import AIProviderError, BaseAIClient, _provider_error, get_embedding_client
from app.ai.embeddings import validate_local_vectors
from app.db.models import Job, JobStatus
from app.db.vector import VectorStore

logger = logging.getLogger("jobot.ai.feedback")


class FeedbackManager:
    """Manages recording positive/negative user feedback vectors in ChromaDB and adjusting fit scores."""

    POSITIVE_STATUSES = {
        JobStatus.APPLIED.value,
        JobStatus.INTERVIEW_1.value,
        JobStatus.INTERVIEW_2.value,
        JobStatus.INTERVIEW_3.value,
    }
    NEGATIVE_STATUSES = {
        JobStatus.NOT_A_FIT.value,
        JobStatus.REJECTED.value,
    }

    @classmethod
    async def record_job_feedback(
        cls,
        job_id: int,
        status: str,
        note_text: str | None,
        session: Session,
        vector_store: VectorStore,
        ai_client: BaseAIClient | None = None,
        *,
        embedding_client: BaseAIClient | None = None,
        user_id: int | None = None,
        sentiment_override: str | None = None,
    ) -> str | None:
        """
        Record candidate feedback locally using the loaded job's owner.

        A supplied authenticated owner must match the record before text is
        embedded. The legacy generation argument is retained but never used
        for vectors; only explicit embedding injection can replace resolution.
        Failed embedding or dimension validation writes nothing and propagates.
        
        Returns:
            feedback_vector_id if recorded, None otherwise.
        """
        job = session.get(Job, job_id)
        if not job or (user_id is not None and job.user_id != user_id):
            logger.warning("Job id=%d not found for feedback recording", job_id)
            return None

        sentiment = "neutral"
        if status in cls.POSITIVE_STATUSES:
            sentiment = "positive"
        elif status in cls.NEGATIVE_STATUSES:
            sentiment = "negative"
        # An explicit note sentiment is the user's own judgement and wins over the status.
        if sentiment_override in ("positive", "negative"):
            sentiment = sentiment_override

        if sentiment == "neutral" and not note_text:
            return None

        # Compose rich semantic feedback text
        feedback_parts = [
            f"Title: {job.title}",
            f"Company: {job.company}",
            f"Location: {job.location}",
            f"Status: {status}",
        ]
        if note_text and note_text.strip():
            feedback_parts.append(f"Candidate Note: {note_text.strip()}")
        if job.description:
            feedback_parts.append(f"Description snippet: {job.description[:400]}")

        doc_text = "\n".join(feedback_parts)
        doc_id = f"feedback_{job_id}_{int(job.updated_at.timestamp())}"
        if sentiment_override:
            # Keep note vectors from overwriting the status vector of the same job.
            doc_id += f"_note_{int(time.time() * 1000)}"

        try:
            client = embedding_client or get_embedding_client(session, job.user_id)
            emb = await client.embed(doc_text)
            validate_local_vectors(vector_store, VectorStore.COLLECTION_USER_FEEDBACK, [emb])
            vector_store.upsert_documents(
                collection_name=VectorStore.COLLECTION_USER_FEEDBACK,
                ids=[doc_id],
                documents=[doc_text],
                metadatas=[{
                    "job_id": job.id,
                    "user_id": job.user_id if job.user_id is not None else 0,
                    "sentiment": sentiment,
                    "status": status,
                    "title": job.title,
                    "company": job.company,
                }],
                embeddings=[emb],
            )
            logger.info("Recorded %s feedback vector id='%s' for Job id=%d", sentiment, doc_id, job.id)
            return doc_id
        except AIProviderError:
            raise
        except Exception as err:
            raise _provider_error("ollama", "nomic-embed-text", err) from None

    @classmethod
    def backfill_feedback_owners(cls, session: Session, vector_store: VectorStore) -> dict[str, int]:
        """Stamp legacy feedback vectors lacking an owner with their job's user_id.

        Vectors whose job is gone or itself unowned are left untouched, and
        nothing is deleted or re-embedded. Idempotent. The shared cv_profile
        collection stores no job reference, so its owner is not determinable.
        """
        collection = vector_store.get_or_create_collection(VectorStore.COLLECTION_USER_FEEDBACK)
        stored = collection.get(include=["metadatas"])
        ids: list[str] = []
        metadatas: list[dict] = []
        skipped = 0
        for doc_id, meta in zip(stored.get("ids") or [], stored.get("metadatas") or []):
            meta = dict(meta or {})
            if meta.get("user_id"):
                continue
            job = session.get(Job, meta["job_id"]) if isinstance(meta.get("job_id"), int) else None
            if job is None or job.user_id is None:
                skipped += 1
                continue
            meta["user_id"] = job.user_id
            ids.append(doc_id)
            metadatas.append(meta)
        if ids:
            collection.update(ids=ids, metadatas=metadatas)
            logger.info("Backfilled owner on %d legacy feedback vectors (%d undeterminable)", len(ids), skipped)
        return {"updated": len(ids), "skipped": skipped}

    @classmethod
    async def compute_feedback_score_adjustment(
        cls,
        job_text: str,
        vector_store: VectorStore,
        ai_client: BaseAIClient | None = None,
        *,
        embedding_client: BaseAIClient | None = None,
        session: Session | None = None,
        user_id: int | None = None,
    ) -> tuple[int, list[str]]:
        """
        Compute fit score delta and explanations by checking cosine similarity against feedback vectors.
        
        Formula:
          Score Delta = (+ Boost for high similarity to positive) - (Penalty for high similarity to negative)
        
        Returns:
            (score_delta: int, feedback_reasons: list[str])
        """
        try:
            owner_filter = {"user_id": user_id} if user_id is not None else None
            if vector_store.count(VectorStore.COLLECTION_USER_FEEDBACK, where=owner_filter) == 0:
                return 0, []
            client = embedding_client or get_embedding_client(session, user_id)
            job_emb = await client.embed(job_text[:3000])
            validate_local_vectors(vector_store, VectorStore.COLLECTION_USER_FEEDBACK, [job_emb])
            results = vector_store.query_similar(
                collection_name=VectorStore.COLLECTION_USER_FEEDBACK,
                query_embeddings=[job_emb],
                n_results=5,
                where=owner_filter,
            )

            ids = results.get("ids", [[]])[0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            if not ids or not distances:
                return 0, []

            positive_sims: list[float] = []
            negative_sims: list[float] = []
            negative_titles: list[str] = []

            for doc_id, dist, meta in zip(ids, distances, metadatas):
                sim = max(0.0, min(1.0, 1.0 - float(dist)))
                sent = meta.get("sentiment", "neutral")
                title = meta.get("title", "Position")

                if sent == "positive" and sim >= 0.75:
                    positive_sims.append(sim)
                elif sent == "negative" and sim >= 0.70:
                    negative_sims.append(sim)
                    negative_titles.append(title)

            score_delta = 0
            reasons: list[str] = []

            # Apply positive boost
            if positive_sims:
                avg_pos = sum(positive_sims) / len(positive_sims)
                boost = int(round(avg_pos * 10))  # Up to +10
                score_delta += boost
                reasons.append(f"Positive feedback alignment (+{boost}% fit bonus)")

            # Apply negative penalty
            if negative_sims:
                avg_neg = sum(negative_sims) / len(negative_sims)
                penalty = int(round(avg_neg * 25))  # Up to -25
                score_delta -= penalty
                reasons.append(f"High similarity to disliked/rejected role ({', '.join(negative_titles[:2])}) (-{penalty}% penalty)")

            return score_delta, reasons

        except AIProviderError:
            raise
        except Exception as err:
            raise _provider_error("ollama", "nomic-embed-text", err) from None
