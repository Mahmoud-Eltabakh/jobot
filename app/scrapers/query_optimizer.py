"""Search query optimizer analyzing high-performing job patterns."""

import collections
import logging
import re
from typing import Optional
from sqlmodel import Session, select

from app.db.models import Job, JobStatus, SearchConfig

logger = logging.getLogger("jobot.scrapers.query_optimizer")


class SearchQueryOptimizer:
    """Analyzes positive applied/interview positions to suggest higher-yield search keywords."""

    POSITIVE_STATUSES = {
        JobStatus.APPLIED.value,
        JobStatus.INTERVIEW_1.value,
        JobStatus.INTERVIEW_2.value,
        JobStatus.INTERVIEW_3.value,
    }

    STOPWORDS = {
        "senior", "junior", "lead", "staff", "developer", "engineer", "specialist",
        "consultant", "architect", "in", "for", "with", "and", "the", "gmbh", "ag",
        "inc", "corp", "germany", "berlin", "munich", "remote", "hybrid"
    }

    @classmethod
    def get_optimized_search_terms(
        cls,
        session: Session,
        min_occurrences: int = 2,
    ) -> list[str]:
        """Extract high-yield search keyword phrases from positive job history."""
        positive_jobs = session.exec(
            select(Job).where(Job.status.in_(cls.POSITIVE_STATUSES))
        ).all()

        if not positive_jobs:
            return []

        # Tokenize positive job titles
        tokens: list[str] = []
        for j in positive_jobs:
            if j.title:
                words = re.findall(r"\b[A-Za-z0-9#\+]{2,}\b", j.title.lower())
                tokens.extend([w for w in words if w not in cls.STOPWORDS])

        counts = collections.Counter(tokens)
        top_skills = [word.capitalize() for word, freq in counts.most_common(5) if freq >= min_occurrences]

        suggestions: list[str] = []
        if top_skills:
            suggestions.append(f"{' '.join(top_skills[:2])} Developer")
            for skill in top_skills:
                suggestions.append(f"{skill} Engineer")

        logger.info("SearchQueryOptimizer generated %d optimized search terms", len(suggestions))
        return list(dict.fromkeys(suggestions))  # Deduplicate preserving order
