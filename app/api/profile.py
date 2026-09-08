"""REST API endpoints for Candidate Profile management and LinkedIn synchronization."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.ai.client import get_ai_client
from app.ai.embeddings import ProfileEmbedder
from app.ai.linkedin_analyzer import LinkedInProfileAnalyzer
from app.ai.profile_extractor import ExtractedProfile, generate_candidate_bio
from app.auth.dependencies import get_current_user
from app.db.database import get_session
from app.db.models import User, UserProfile, utc_now
from app.db.ownership import encrypt_profile, get_user_profile
from app.db.vector import get_vector_store

logger = logging.getLogger("jobot.api.profile")

router = APIRouter(prefix="/api/profile", tags=["Profile"])


class ProfileUpdateRequest(BaseModel):
    """Payload for updating candidate profile details."""

    full_name: str
    headline: str | None = None
    bio: str | None = None
    experience_years: float = 0.0
    target_titles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    target_salary_min: float | None = None
    work_preference: str = "remote_first"
    skills: list[str] = Field(default_factory=list)
    active_search_skills: list[str] = Field(default_factory=list)
    linkedin_url: str | None = None


class LinkedInSyncRequest(BaseModel):
    """Payload for synchronizing and analyzing a LinkedIn profile using li_at session cookie."""

    linkedin_url: str
    session_cookie: str | None = None
    raw_text_override: str | None = None


@router.get("", response_model=dict[str, Any])
async def get_profile(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve the primary UserProfile record."""
    profile = get_user_profile(session, current_user.id, decrypt=True)
    if not profile:
        return {
            "status": "empty",
            "profile": None,
        }

    return {
        "status": "ok",
        "profile": {
            "id": profile.id,
            "full_name": profile.full_name,
            "headline": profile.headline,
            "bio": profile.bio,
            "experience_years": profile.experience_years,
            "target_titles": json.loads(profile.target_titles_json or "[]"),
            "target_locations": json.loads(profile.target_locations_json or "[]"),
            "target_salary_min": profile.target_salary_min,
            "work_preference": profile.work_preference,
            "skills": json.loads(profile.skills_json or "[]"),
            "active_search_skills": json.loads(profile.active_search_skills_json or "[]"),
            "experience_history": json.loads(profile.experience_history_json or "[]"),
            "education": json.loads(profile.education_json or "[]"),
            "projects": json.loads(profile.projects_json or "[]"),
            "linkedin_url": profile.linkedin_url,
            "updated_at": profile.updated_at.isoformat(),
        },
    }


@router.post("/update", response_model=dict[str, Any])
async def update_profile(
    payload: ProfileUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Update profile attributes and sync embeddings with ChromaDB."""
    profile = get_user_profile(session, current_user.id, decrypt=True)
    if not profile:
        profile = UserProfile(
            user_id=current_user.id,
            full_name=payload.full_name,
            updated_at=utc_now(),
        )
        session.add(profile)

    profile.full_name = payload.full_name
    profile.headline = payload.headline
    profile.bio = payload.bio
    profile.experience_years = payload.experience_years
    profile.target_titles_json = json.dumps(payload.target_titles)
    profile.target_locations_json = json.dumps(payload.target_locations)
    profile.target_salary_min = payload.target_salary_min
    profile.work_preference = payload.work_preference
    profile.skills_json = json.dumps(payload.skills)
    profile.active_search_skills_json = json.dumps(payload.active_search_skills or payload.skills)
    profile.linkedin_url = payload.linkedin_url
    profile.updated_at = utc_now()

    encrypt_profile(profile, current_user.id)
    session.add(profile)
    session.commit()
    session.refresh(profile)

    # Refresh ChromaDB embeddings
    try:
        extracted = ExtractedProfile(
            full_name=profile.full_name,
            headline=profile.headline,
            summary=profile.bio or "",
            skills=payload.skills,
            active_search_skills=payload.active_search_skills or payload.skills,
            experience_years=payload.experience_years,
            target_titles=payload.target_titles,
            target_locations=payload.target_locations,
            target_salary_min=payload.target_salary_min,
            work_preference=payload.work_preference,
            linkedin_url=payload.linkedin_url,
        )
        vector_store = get_vector_store()
        ai_client = get_ai_client()
        await ProfileEmbedder.embed_and_store_profile(extracted, vector_store, ai_client)
    except Exception as err:
        logger.warning("Failed updating vector embeddings for profile: %s", err)

    return {
        "status": "ok",
        "message": "Profile updated and vector embeddings synchronized successfully.",
        "profile_id": profile.id,
    }


@router.post("/linkedin/sync", response_model=dict[str, Any])
async def sync_linkedin_profile(
    payload: LinkedInSyncRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Ingest, analyze with AI, and synchronize a LinkedIn profile using li_at cookie."""
    if not payload.linkedin_url or "linkedin.com" not in payload.linkedin_url:
        raise HTTPException(status_code=400, detail="A valid LinkedIn profile URL is required.")

    try:
        user_profile = await LinkedInProfileAnalyzer.sync_linkedin_to_profile(
            session=session,
            linkedin_url=payload.linkedin_url,
            session_cookie=payload.session_cookie,
            raw_text_override=payload.raw_text_override,
            user_id=current_user.id,
        )

        return {
            "status": "ok",
            "message": f"LinkedIn profile successfully analyzed and synced for {user_profile.full_name}!",
            "full_name": user_profile.full_name,
            "headline": user_profile.headline,
            "skills": json.loads(user_profile.skills_json or "[]"),
            "target_titles": json.loads(user_profile.target_titles_json or "[]"),
        }
    except Exception as err:
        logger.error("LinkedIn sync failed: %s", err)
        raise HTTPException(status_code=500, detail=f"LinkedIn sync failed: {err!s}")


@router.post("/generate-bio", response_model=dict[str, Any])
async def generate_profile_bio_api(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate professional bio / executive summary for candidate using AI."""
    profile = get_user_profile(session, current_user.id, decrypt=True)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found.")

    cand_data = {
        "full_name": profile.full_name,
        "headline": profile.headline,
        "experience_years": profile.experience_years,
        "target_titles": json.loads(profile.target_titles_json or "[]"),
        "skills": json.loads(profile.skills_json or "[]"),
        "work_preference": profile.work_preference,
        "cv_raw_text": profile.cv_raw_text,
        "bio": profile.bio,
    }
    ai_client = get_ai_client()
    new_bio = await generate_candidate_bio(cand_data, ai_client)

    profile.bio = new_bio
    profile.updated_at = utc_now()
    encrypt_profile(profile, current_user.id)
    session.add(profile)
    session.commit()
    session.refresh(profile)

    return {
        "status": "ok",
        "bio": new_bio,
        "message": "Professional bio generated and updated successfully.",
    }
