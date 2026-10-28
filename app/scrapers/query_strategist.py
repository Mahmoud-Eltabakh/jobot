"""Build search queries using an owner's independent scraping assignment.

Explicit active SearchConfig rows bypass AI and retain deterministic behavior.
Otherwise only the selected account's profile and filters enter the prompt.
Generation clients are resolved per call rather than cached across accounts.
The JSON object envelope works with providers requiring object-mode output.
Legacy injected clients may still return the established bare array format.
Both forms undergo the same query-field and platform validation.
Malformed output and transport errors never produce replacement search jobs.
No retry, alternate model, or rule-based recovery follows a provider failure.
"""

import json
import logging

from sqlmodel import Session, select

from app.ai.client import AIProviderError, BaseAIClient, _provider_error, get_ai_client
from app.ai.evaluator import extract_keywords_from_profile
from app.db.models import FilterRule, SearchConfig, UserProfile
from app.db.ownership import get_user_profile

logger = logging.getLogger("jobot.scrapers.query_strategist")

QUERY_STRATEGY_SYSTEM_PROMPT = """You are an expert technical recruitment sourcer and Boolean search engineer.
Given the candidate's target roles, core technical skills, and negative blacklist filters,
formulate 3-5 optimized search queries for web scrapers across LinkedIn, StepStone, and Google Jobs.

Return a JSON object containing a queries array:
{"queries": [
  {
    "platform": "all",  // "linkedin", "stepstone", "google", or "all"
    "keywords": "string", // Optimized search query string
    "location": "string",
    "rationale": "string"
  }
]}

Ensure:
1. Include high-yield skill combinations (e.g., 'Python FastAPI Remote', 'Backend Engineer SQLModel').
2. Avoid generic single-word terms.
3. Respect negative blacklist keywords by omitting them.
Return ONLY the raw JSON object without markdown blocks.
"""


class AIQueryStrategist:
    """Generates intelligent multi-platform search queries using candidate skills and AI."""

    @classmethod
    async def generate_search_queries(
        cls,
        session: Session,
        max_queries: int | None = 5,
        ai_client: BaseAIClient | None = None,
        user_id: int | None = None,
        override_location: str | None = None,
        override_work_preference: str | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Generate (platform, keywords, location) tuples for the current owner.

        Explicit configured searches are authoritative unless a location
        override asks for new strategy generation. Profile-less calls retain
        their existing deterministic no-data behavior without contacting AI.
        UI overrides affect search content, never provider routing or keys.
        The queries envelope is unwrapped before validating individual items.
        A partly malformed batch fails as a whole instead of silently issuing
        a different subset of queries. No AI response is logged on failure.
        max_queries only limits successfully validated output, not requests.
        Existing positional arguments and injected clients remain supported.
        """
        # 1. Check if user configured explicit SearchConfig records
        config_stmt = select(SearchConfig).where(SearchConfig.is_active.is_(True))
        if user_id is not None:
            config_stmt = config_stmt.where(SearchConfig.user_id == user_id)
        configs = session.exec(config_stmt).all()
        if configs and not override_location:
            return [(c.source, c.keywords, c.location) for c in configs]

        profile = get_user_profile(session, user_id, decrypt=True) if user_id is not None else session.exec(select(UserProfile)).first()
        if not profile:
            if override_location:
                return [("all", "Software Engineer", override_location)]
            return []

        titles = json.loads(profile.target_titles_json or "[]")
        skills = extract_keywords_from_profile(profile)

        # Resolve target locations from override or UI profile
        if override_location and override_location.strip():
            locations = [l.strip() for l in override_location.split(",") if l.strip()]
        else:
            locations = json.loads(profile.target_locations_json or "[]")

        work_pref = override_work_preference or profile.work_preference or "remote_first"

        rule_stmt = select(FilterRule).where(FilterRule.is_active.is_(True))
        if user_id is not None:
            rule_stmt = rule_stmt.where(FilterRule.user_id == user_id)
        rules = session.exec(rule_stmt).all()
        blacklists = [r.pattern for r in rules]

        primary_loc = locations[0] if locations else ""
        headline = profile.headline or ""
        primary_title = titles[0] if titles else (headline or (skills[0] if skills else "Software Developer"))
        client = ai_client or get_ai_client(session, user_id, task_type="scraping")

        prompt = f"""Candidate Profile:
Headline: {headline}
Target Titles: {', '.join(titles)}
Active Skills: {', '.join(skills)}
Preferred Target Locations (from UI): {', '.join(locations) if locations else 'Any'}
Work Model Preference (from UI): {work_pref}
Bio: {(profile.bio or '')[:500]}
Excluded / Blacklist Patterns: {', '.join(blacklists)}

Generate optimized search queries combining candidate target titles and profile skills across the target locations.
"""

        try:
            response = await client.generate(
                prompt=prompt,
                system_prompt=QUERY_STRATEGY_SYSTEM_PROMPT,
                json_mode=True,
            )

            clean_json = response.strip()
            clean_json = clean_json.removeprefix("```json")
            clean_json = clean_json.removeprefix("```")
            clean_json = clean_json.removesuffix("```")
            clean_json = clean_json.strip()

            parsed = json.loads(clean_json)
            if isinstance(parsed, dict):
                parsed = parsed.get("queries")
            results: list[tuple[str, str, str]] = []
            if isinstance(parsed, list):
                for item in parsed:
                    if not isinstance(item, dict):
                        raise ValueError("Invalid query item")
                    platform = item.get("platform", "all")
                    kw = item.get("keywords", "")
                    loc = item.get("location", primary_loc)
                    if (platform not in ("all", "linkedin", "stepstone", "google")
                            or not isinstance(kw, str) or not kw.strip() or not isinstance(loc, str)):
                        raise ValueError("Invalid query fields")
                    results.append((platform, kw, loc))

            if results:
                logger.info("AI Query Strategist generated %d intelligent queries", len(results))
                return results[:max_queries] if max_queries is not None else results
            raise ValueError("Missing search queries")
        except AIProviderError:
            raise
        except Exception as err:
            raise _provider_error(
                getattr(client, "provider", "ollama"), getattr(client, "model", ""), err,
            ) from None
