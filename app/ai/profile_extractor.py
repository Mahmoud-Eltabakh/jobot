"""Candidate structured profile extractor and SQLite persistence."""

import json
import logging
import re
from typing import Any, Optional
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.db.models import UserProfile, utc_now

logger = logging.getLogger("jobot.ai.profile_extractor")


class ExtractedProfile(BaseModel):
    """Structured candidate profile extracted from CV text or LinkedIn."""

    full_name: str = Field(default="", description="Full name of candidate")
    headline: Optional[str] = Field(default=None, description="Professional headline or title")
    summary: str = Field(default="", description="Executive summary / professional bio")
    skills: list[str] = Field(default_factory=list, description="Extracted technical and domain skills")
    active_search_skills: list[str] = Field(default_factory=list, description="Skills selected for active scraper queries")
    experience_years: float = Field(default=0.0, description="Estimated years of relevant experience")
    target_titles: list[str] = Field(default_factory=list, description="Target job titles or role matches")
    target_locations: list[str] = Field(default_factory=list, description="Target locations or remote preference")
    target_salary_min: Optional[float] = Field(default=None, description="Minimum expected compensation")
    work_preference: str = Field(default="remote_first", description="Work model preference")
    experience_history: list[dict[str, Any]] = Field(default_factory=list, description="Structured past work experiences")
    education: list[dict[str, str]] = Field(default_factory=list, description="Education and degrees")
    linkedin_url: Optional[str] = Field(default=None, description="LinkedIn profile URL")


EXTRACTION_SYSTEM_PROMPT = """You are an expert technical resume parser.
Your task is to analyze the provided candidate resume text and extract a structured profile JSON.
Ensure:
1. 'skills' contains concrete programming languages, frameworks, tools, and technical competencies.
2. 'experience_years' is a numeric estimate of total relevant professional experience.
3. 'target_titles' contains 2-4 appropriate job titles based on their seniority and expertise.
4. 'summary' is a clear 2-3 sentence executive summary of candidate strengths.
5. Conforms strictly to the required JSON schema without any markdown wrapping.
"""

BIO_GENERATION_SYSTEM_PROMPT = """You are an expert executive resume writer and talent specialist.
Your task is to craft a compelling, highly professional 2-3 sentence Executive Summary / Professional Bio for a job candidate based on their background data.

Guidelines:
1. Highlight candidate's primary domain expertise, key technical skills, experience level, and core strengths.
2. Ensure the tone is confident, executive-ready, and polished for hiring managers.
3. Length: Exactly 2 to 3 well-structured sentences.
4. Output strictly plain text without quotes, markdown block ticks, or extra preamble.
"""


async def generate_candidate_bio(
    profile_data: dict[str, Any],
    ai_client: Optional[Any] = None,
) -> str:
    """Generate a professional executive summary / bio using AI based on candidate details."""
    from app.ai.client import get_ai_client

    client = ai_client or get_ai_client()

    full_name = profile_data.get("full_name") or ""
    headline = profile_data.get("headline") or ""
    exp_years = profile_data.get("experience_years") or 0.0
    titles = profile_data.get("target_titles") or []
    skills = profile_data.get("skills") or []
    work_pref = profile_data.get("work_preference") or "remote_first"
    cv_text = profile_data.get("cv_raw_text") or profile_data.get("bio") or ""

    if isinstance(titles, str):
        titles = [t.strip() for t in titles.split(",") if t.strip()]
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]

    user_prompt = f"""Candidate Details:
Name: {full_name}
Professional Headline: {headline}
Experience Level: {exp_years} years
Target Roles: {', '.join(titles) if titles else 'Software Engineering'}
Key Skills: {', '.join(skills) if skills else 'Technical Problem Solving'}
Work Model Preference: {work_pref}
Background Excerpt / Resume: {str(cv_text)[:2500]}

Write a concise 2-3 sentence Executive Summary / Professional Bio."""

    try:
        raw_bio = await client.generate(
            prompt=user_prompt,
            system_prompt=BIO_GENERATION_SYSTEM_PROMPT,
            json_mode=False,
        )
        clean_bio = raw_bio.strip().strip('"\'')
        if clean_bio.startswith("```"):
            clean_bio = re.sub(r"^```\w*\n?|\n?```$", "", clean_bio).strip()
        if clean_bio:
            return clean_bio
    except Exception as err:
        logger.warning("AI bio generation failed (%s), constructing dynamic fallback bio", err)

    titles_str = f" specializing in {', '.join(titles[:2])}" if titles else ""
    skills_str = f" Core competencies include {', '.join(skills[:5])}." if skills else ""
    return f"{full_name} is a results-driven professional with {exp_years} years of industry experience{titles_str}.{skills_str} Proven track record in delivering scalable solutions and driving technical innovation."


def extract_dynamic_skills_from_text(raw_text: str) -> list[str]:
    """Dynamically extract candidate skills from text without static hardcoded lists."""
    skills: list[str] = []
    # 1. Match explicit Skills / Competencies / Kenntnisse section
    section_match = re.search(r"(?:skills|competencies|technologies|tools|kenntnisse|fertigkeiten)\s*:\s*([^\n]+)", raw_text, re.IGNORECASE)
    if section_match:
        extracted = [s.strip() for s in re.split(r"[,;|•]", section_match.group(1)) if s.strip()]
        for s in extracted:
            if s and len(s) > 1 and s not in skills:
                skills.append(s)

    # 2. Extract technical terms / capitalized tokens from text, ignoring UI boilerplate
    tech_patterns = re.findall(r"\b[A-Z][a-zA-Z0-9+#.-]{1,19}\b", raw_text)
    ignored = {
        "summary", "experience", "education", "resume", "curriculum", "vitae", "contact",
        "email", "phone", "profile", "project", "projects", "work", "history", "candidate",
        "about", "benachrichtigungen", "weiter", "hauptinhalt", "start", "ihr", "netzwerk",
        "jobs", "nachrichten", "mitteilungen", "sie", "produkte", "linkedin", "learning",
        "profil", "abschnitt", "offen", "notifications", "next", "main", "home", "network",
        "messaging", "me", "products", "settings", "search", "privacy", "terms", "help",
        "signout", "signin", "skipping", "skip", "agree", "cookie", "language", "languages",
        "german", "english", "location", "locations", "present", "month", "months", "year",
        "years", "he", "she", "his", "her", "von", "bis", "der", "die", "das", "und", "mit",
        "für", "fürs", "aus", "auf", "ein", "eine", "einer", "eines", "dem", "den"
    }
    for token in tech_patterns:
        if len(token) > 1 and token not in skills and token.lower() not in ignored:
            skills.append(token)

    return skills[:25]


def _fallback_heuristic_extraction(raw_text: str) -> ExtractedProfile:
    """Heuristic regex fallback parser when LLM is offline or unavailable."""
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    first_line = lines[0] if lines else ""
    
    found_skills = extract_dynamic_skills_from_text(raw_text)

    # Heuristic experience years
    years_match = re.findall(r"(\d+)\+?\s*(?:years|yrs)", raw_text, re.IGNORECASE)
    exp_years = float(max([int(y) for y in years_match])) if years_match else 0.0

    return ExtractedProfile(
        full_name=first_line[:50] if first_line else "",
        summary=f"Profile parsed from resume text." if found_skills else "",
        skills=found_skills,
        active_search_skills=found_skills[:5],
        experience_years=exp_years,
        target_titles=[],
        target_locations=[],
        target_salary_min=None,
        education=[],
    )


async def extract_profile_from_text(
    raw_text: str,
    ai_client: Optional[Any] = None,
) -> ExtractedProfile:
    """Extract structured candidate profile from raw CV text using LLM or fallback."""
    if not raw_text.strip():
        return ExtractedProfile()

    extracted: Optional[ExtractedProfile] = None
    if ai_client is not None:
        try:
            prompt = f"Extract structured candidate profile from the following resume text:\n\n{raw_text[:8000]}"
            response = await ai_client.generate(
                prompt=prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                json_mode=True,
            )
            # Clean possible markdown wrapping
            clean_json = response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            data = json.loads(clean_json)
            extracted = ExtractedProfile.model_validate(data)
        except Exception as err:
            logger.warning("LLM profile extraction failed (%s), using heuristic fallback", err)

    if extracted is None:
        extracted = _fallback_heuristic_extraction(raw_text)

    # Automatically generate professional executive summary using AI if empty or generic
    if not extracted.summary or len(extracted.summary.strip()) < 25 or "Profile parsed" in extracted.summary:
        try:
            extracted.summary = await generate_candidate_bio(
                profile_data={
                    "full_name": extracted.full_name,
                    "headline": extracted.headline,
                    "experience_years": extracted.experience_years,
                    "target_titles": extracted.target_titles,
                    "skills": extracted.skills,
                    "work_preference": extracted.work_preference,
                    "cv_raw_text": raw_text,
                },
                ai_client=ai_client,
            )
        except Exception as b_err:
            logger.warning("Failed auto-generating bio during profile extraction: %s", b_err)

    return extracted


def save_profile_to_db(
    profile: ExtractedProfile,
    raw_text: str,
    session: Session,
    source_type: str = "cv",
) -> UserProfile:
    """Persist or update primary UserProfile in SQLite database, joining CV and LinkedIn data."""
    user_profile = session.exec(select(UserProfile)).first()
    
    new_skills = list(dict.fromkeys(profile.skills))
    new_active_skills = profile.active_search_skills if profile.active_search_skills else new_skills
    
    if not user_profile:
        user_profile = UserProfile(
            full_name=profile.full_name,
            headline=profile.headline or (profile.target_titles[0] if profile.target_titles else None),
            bio=profile.summary,
            experience_years=profile.experience_years,
            target_titles_json=json.dumps(profile.target_titles),
            target_locations_json=json.dumps(profile.target_locations),
            target_salary_min=profile.target_salary_min,
            work_preference=profile.work_preference,
            skills_json=json.dumps(new_skills),
            active_search_skills_json=json.dumps(new_active_skills),
            experience_history_json=json.dumps(profile.experience_history),
            education_json=json.dumps(profile.education),
            cv_raw_text=raw_text if source_type == "cv" else None,
            linkedin_raw_text=raw_text if source_type == "linkedin" else None,
            linkedin_url=profile.linkedin_url,
            updated_at=utc_now(),
        )
        session.add(user_profile)
    else:
        # 1. Full name & headline
        if profile.full_name and (not user_profile.full_name or user_profile.full_name == "Candidate"):
            user_profile.full_name = profile.full_name
        elif profile.full_name:
            user_profile.full_name = profile.full_name

        if profile.headline:
            user_profile.headline = profile.headline

        # 2. Executive Bio / Summary
        if profile.summary and profile.summary.strip():
            if not user_profile.bio or len(profile.summary) > len(user_profile.bio):
                user_profile.bio = profile.summary

        # 3. Experience Years (Take maximum or non-zero)
        if profile.experience_years and profile.experience_years > user_profile.experience_years:
            user_profile.experience_years = profile.experience_years

        # 4. Target Titles - Merged & Deduplicated
        existing_titles = []
        if user_profile.target_titles_json:
            try:
                existing_titles = json.loads(user_profile.target_titles_json)
            except Exception:
                pass
        merged_titles = list(dict.fromkeys(existing_titles + [t for t in profile.target_titles if t]))
        user_profile.target_titles_json = json.dumps(merged_titles)

        # 5. Target Locations - Merged & Deduplicated
        existing_locs = []
        if user_profile.target_locations_json:
            try:
                existing_locs = json.loads(user_profile.target_locations_json)
            except Exception:
                pass
        merged_locs = list(dict.fromkeys(existing_locs + [l for l in profile.target_locations if l]))
        user_profile.target_locations_json = json.dumps(merged_locs)

        # 6. Target Salary & Work Preference
        if profile.target_salary_min:
            user_profile.target_salary_min = profile.target_salary_min
        if profile.work_preference and profile.work_preference != "remote_first":
            user_profile.work_preference = profile.work_preference

        # 7. Skills & Active Scraper Search Skills - Joined & Deduplicated Matrix
        existing_skills = []
        if user_profile.skills_json:
            try:
                existing_skills = json.loads(user_profile.skills_json)
            except Exception:
                pass

        existing_active = []
        if user_profile.active_search_skills_json:
            try:
                existing_active = json.loads(user_profile.active_search_skills_json)
            except Exception:
                pass

        joined_skills = list(dict.fromkeys(existing_skills + new_skills))
        # Dynamically update Scraper Search Matrix with all newly joined skills!
        joined_active = list(dict.fromkeys(existing_active + new_active_skills + new_skills))

        user_profile.skills_json = json.dumps(joined_skills)
        user_profile.active_search_skills_json = json.dumps(joined_active)

        # 8. Experience History - Joined & Deduplicated by title+company
        existing_history = []
        if user_profile.experience_history_json:
            try:
                existing_history = json.loads(user_profile.experience_history_json)
            except Exception:
                pass

        merged_history = existing_history.copy()
        seen_keys = {(h.get("title", "").lower(), h.get("company", "").lower()) for h in existing_history if isinstance(h, dict)}

        for new_exp in profile.experience_history:
            if isinstance(new_exp, dict):
                key = (new_exp.get("title", "").lower(), new_exp.get("company", "").lower())
                if key not in seen_keys and (key[0] or key[1]):
                    seen_keys.add(key)
                    merged_history.append(new_exp)

        user_profile.experience_history_json = json.dumps(merged_history)

        # 9. Education - Joined & Deduplicated by school+degree
        existing_edu = []
        if user_profile.education_json:
            try:
                existing_edu = json.loads(user_profile.education_json)
            except Exception:
                pass

        merged_edu = existing_edu.copy()
        seen_edu = {(e.get("school", "").lower(), e.get("degree", "").lower()) for e in existing_edu if isinstance(e, dict)}

        for new_edu in profile.education:
            if isinstance(new_edu, dict):
                key = (new_edu.get("school", "").lower(), new_edu.get("degree", "").lower())
                if key not in seen_edu and (key[0] or key[1]):
                    seen_edu.add(key)
                    merged_edu.append(new_edu)

        user_profile.education_json = json.dumps(merged_edu)

        # 10. Store separate raw texts without overriding
        if source_type == "cv" and raw_text:
            user_profile.cv_raw_text = raw_text
        elif source_type == "linkedin" and raw_text:
            user_profile.linkedin_raw_text = raw_text

        if profile.linkedin_url:
            user_profile.linkedin_url = profile.linkedin_url

        user_profile.updated_at = utc_now()
        session.add(user_profile)

    session.commit()
    session.refresh(user_profile)
    logger.info("Updated & Joined UserProfile id=%d for '%s' (Source: %s)", user_profile.id, user_profile.full_name, source_type)
    return user_profile
