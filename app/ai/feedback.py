"""Candidate feedback vector management and adaptive fit score re-weighting in ChromaDB."""

import logging

from sqlmodel import Session

from app.ai.client import BaseAIClient
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
        ai_client: BaseAIClient,
    ) -> str | None:
        """
        Record positive or negative candidate reaction as vector embedding in ChromaDB.
        
        Returns:
            feedback_vector_id if recorded, None otherwise.
        """
        job = session.get(Job, job_id)
        if not job:
            logger.warning("Job id=%d not found for feedback recording", job_id)
            return None

        sentiment = "neutral"
        if status in cls.POSITIVE_STATUSES:
            sentiment = "positive"
        elif status in cls.NEGATIVE_STATUSES:
            sentiment = "negative"

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

        try:
            emb = await ai_client.embed(doc_text)
            vector_store.upsert_documents(
                collection_name=VectorStore.COLLECTION_USER_FEEDBACK,
                ids=[doc_id],
                documents=[doc_text],
                metadatas=[{
                    "job_id": job.id,
                    "sentiment": sentiment,
                    "status": status,
                    "title": job.title,
                    "company": job.company,
                }],
                embeddings=[emb],
            )
            logger.info("Recorded %s feedback vector id='%s' for Job id=%d", sentiment, doc_id, job.id)
            return doc_id
        except Exception as err:
            logger.warning("Failed to record feedback vector for Job id=%d: %s", job.id, err)
            return None

    @classmethod
    async def compute_feedback_score_adjustment(
        cls,
        job_text: str,
        vector_store: VectorStore,
        ai_client: BaseAIClient,
    ) -> tuple[int, list[str]]:
        """
        Compute fit score delta and explanations by checking cosine similarity against feedback vectors.
        
        Formula:
          Score Delta = (+ Boost for high similarity to positive) - (Penalty for high similarity to negative)
        
        Returns:
            (score_delta: int, feedback_reasons: list[str])
        """
        if vector_store.count(VectorStore.COLLECTION_USER_FEEDBACK) == 0:
            return 0, []

        try:
            job_emb = await ai_client.embed(job_text[:3000])
            results = vector_store.query_similar(
                collection_name=VectorStore.COLLECTION_USER_FEEDBACK,
                query_embeddings=[job_emb],
                n_results=5,
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

        except Exception as err:
            logger.warning("Feedback score adjustment calculation failed: %s", err)
            return 0, []
