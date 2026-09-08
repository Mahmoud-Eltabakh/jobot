"""AI Query Strategist: Intelligent Boolean and semantic search query formulation."""

import json
import logging
from typing import Any, Optional
from sqlmodel import Session, select

from app.ai.client import BaseAIClient, get_ai_client
from app.ai.evaluator import extract_keywords_from_profile
from app.db.models import FilterRule, SearchConfig, UserProfile

logger = logging.getLogger("jobot.scrapers.query_strategist")

QUERY_STRATEGY_SYSTEM_PROMPT = """You are an expert technical recruitment sourcer and Boolean search engineer.
Given the candidate's target roles, core technical skills, and negative blacklist filters,
formulate 3-5 optimized search queries for web scrapers across LinkedIn, StepStone, and Google Jobs.

Return a JSON array of objects:
[
  {
    "platform": "all",  // "linkedin", "stepstone", "google", or "all"
    "keywords": "string", // Optimized search query string
    "location": "string",
    "rationale": "string"
  }
]

Ensure:
1. Include high-yield skill combinations (e.g., 'Python FastAPI Remote', 'Backend Engineer SQLModel').
2. Avoid generic single-word terms.
3. Respect negative blacklist keywords by omitting them.
Return ONLY the raw JSON array without markdown blocks.
"""


class AIQueryStrategist:
    """Generates intelligent multi-platform search queries using candidate skills and AI."""

    @classmethod
    async def generate_search_queries(
        cls,
        session: Session,
        max_queries: int = 5,
        ai_client: Optional[BaseAIClient] = None,
    ) -> list[tuple[str, str, str]]:
        """
        Generate optimized (platform, keywords, location) search queries using LLM.
        """
        # 1. Check if user configured explicit SearchConfig records
        configs = session.exec(
            select(SearchConfig).where(SearchConfig.is_active.is_(True))
        ).all()
        if configs:
            return [(c.source, c.keywords, c.location) for c in configs]

        profile = session.exec(select(UserProfile)).first()
        if not profile:
            return []

        titles = json.loads(profile.target_titles_json or "[]")
        skills = extract_keywords_from_profile(profile)
        locations = json.loads(profile.target_locations_json or "[]")
        rules = session.exec(select(FilterRule).where(FilterRule.is_active.is_(True))).all()
        blacklists = [r.pattern for r in rules]

        primary_loc = locations[0] if locations else ""
        headline = profile.headline or ""
        primary_title = titles[0] if titles else (headline or (skills[0] if skills else ""))
        client = ai_client or get_ai_client()

        prompt = f"""Candidate Profile:
Headline: {headline}
Target Titles: {', '.join(titles)}
Active Skills: {', '.join(skills)}
Preferred Locations: {', '.join(locations) if locations else primary_loc}
Work Preference: {profile.work_preference}
Bio: {(profile.bio or '')[:500]}
Excluded / Blacklist Patterns: {', '.join(blacklists)}

Generate optimized search queries combining candidate target titles and profile skills.
"""

        try:
            response = await client.generate(
                prompt=prompt,
                system_prompt=QUERY_STRATEGY_SYSTEM_PROMPT,
                json_mode=True,
            )

            clean_json = response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            parsed = json.loads(clean_json)
            results: list[tuple[str, str, str]] = []
            if isinstance(parsed, list):
                for item in parsed:
                    platform = item.get("platform", "all")
                    kw = item.get("keywords", "")
                    loc = item.get("location", primary_loc)
                    if kw:
                        results.append((platform, kw, loc))

            if results:
                logger.info("AI Query Strategist generated %d intelligent queries", len(results))
                return results[:max_queries] if max_queries is not None else results
        except Exception as err:
            logger.warning("AI Query Strategist generation failed (%s), using rule-based generator", err)

        # Fallback rule-based query matrix
        fallback_queries: list[tuple[str, str, str]] = []
        for t in (titles if titles else [primary_title]):
            if t and t.strip():
                fallback_queries.append(("all", t.strip(), primary_loc))
                for skill in skills:
                    if skill and skill.strip():
                        combo = f"{t.strip()} {skill.strip()}".strip()
                        if combo not in [q[1] for q in fallback_queries]:
                            fallback_queries.append(("all", combo, primary_loc))

        return fallback_queries[:max_queries] if max_queries is not None else fallback_queries
