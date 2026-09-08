"""Automatic blacklist rule suggester analyzing negative candidate feedback."""

import collections
import logging
import re

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.ai.client import BaseAIClient
from app.db.models import FeedbackNote, FilterRule, Job, JobStatus

logger = logging.getLogger("jobot.ai.blacklist_suggester")


class SuggestedRule(BaseModel):
    """Proposed blacklist rule extracted from candidate critique themes."""

    rule_type: str = Field(description="Rule type: 'title', 'keyword', or 'company'")
    pattern: str = Field(description="Pattern string to exclude")
    reason: str = Field(description="Rationale based on recurring feedback")
    frequency: int = Field(default=1, description="Number of occurrences in feedback history")


class BlacklistSuggester:
    """Analyzes candidate notes on rejected/disliked jobs to propose actionable FilterRules."""

    COMMON_STOPWORDS = {
        "the", "and", "a", "an", "is", "in", "to", "for", "with", "of", "on", "at",
        "this", "that", "it", "not", "too", "very", "much", "role", "job", "candidate",
        "only", "required", "position", "company", "years", "experience", "looking"
    }

    @classmethod
    async def analyze_rejections_and_suggest_rules(
        cls,
        session: Session,
        ai_client: BaseAIClient | None = None,
        min_occurrences: int = 2,
    ) -> list[SuggestedRule]:
        """Analyze negative notes and rejected jobs to propose new blacklist FilterRules."""
        # 1. Fetch existing active rules to avoid duplicate suggestions
        existing_rules = session.exec(select(FilterRule)).all()
        existing_patterns = {r.pattern.lower().strip() for r in existing_rules}

        # 2. Fetch negative feedback notes
        negative_notes = session.exec(
            select(FeedbackNote).where(FeedbackNote.sentiment == "negative")
        ).all()

        # 3. Fetch jobs explicitly marked as not a good fit or rejected
        disliked_jobs = session.exec(
            select(Job).where(
                Job.status.in_([JobStatus.NOT_A_FIT.value, JobStatus.REJECTED.value])
            )
        ).all()

        if not negative_notes and not disliked_jobs:
            return []

        # Extract negative words / phrases
        text_corpus: list[str] = []
        for n in negative_notes:
            if n.note_text:
                text_corpus.append(n.note_text.lower())
        for j in disliked_jobs:
            if j.fit_summary and "filtered by" not in j.fit_summary.lower():
                text_corpus.append(j.fit_summary.lower())

        combined_text = " ".join(text_corpus)
        words = re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", combined_text)
        filtered_words = [w for w in words if w not in cls.COMMON_STOPWORDS]

        counts = collections.Counter(filtered_words)
        suggestions: list[SuggestedRule] = []

        # Identify frequent keywords (e.g., 'onsite', 'german', 'travel', 'contract')
        for word, freq in counts.most_common(8):
            if freq >= min_occurrences and word not in existing_patterns:
                suggestions.append(
                    SuggestedRule(
                        rule_type="keyword",
                        pattern=word.title() if len(word) > 3 else word.upper(),
                        reason=f"Mentioned in {freq} negative candidate feedback notes",
                        frequency=freq,
                    )
                )

        # Identify recurring disliked job title patterns
        disliked_titles = [j.title.strip() for j in disliked_jobs if j.title]
        title_counts = collections.Counter(disliked_titles)
        for title, freq in title_counts.most_common(5):
            if freq >= min_occurrences and title.lower() not in existing_patterns:
                suggestions.append(
                    SuggestedRule(
                        rule_type="title",
                        pattern=title,
                        reason=f"Repeatedly marked as not a fit ({freq} times)",
                        frequency=freq,
                    )
                )

        logger.info("Generated %d blacklist rule suggestions from feedback history", len(suggestions))
        return suggestions
