"""REST API endpoints for generating and managing tailored application materials."""

import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.ai.application_generator import ApplicationGenerator
from app.ai.client import get_ai_client
from app.db.database import get_session
from app.db.models import ApplicationMaterial, Job, UserProfile, utc_now

logger = logging.getLogger("jobot.api.applications")

router = APIRouter(prefix="/api/jobs", tags=["Applications"])


class GenerateCoverLetterRequest(BaseModel):
    """Payload for generating tailored cover letter."""

    tone: str = "professional"  # professional, enthusiastic, direct, conversational
    custom_instructions: Optional[str] = None


class SaveMaterialRequest(BaseModel):
    """Payload for updating or saving application material content."""

    content_markdown: str
    tone: Optional[str] = "professional"


@router.get("/{job_id}/materials", response_model=dict[str, Any])
async def get_job_materials(
    job_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Fetch all saved application materials for a job."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    materials = session.exec(
        select(ApplicationMaterial).where(ApplicationMaterial.job_id == job_id)
    ).all()

    return {
        "status": "ok",
        "job_id": job_id,
        "materials": [
            {
                "id": m.id,
                "material_type": m.material_type,
                "tone": m.tone,
                "content_markdown": m.content_markdown,
                "created_at": m.created_at.isoformat(),
                "updated_at": m.updated_at.isoformat(),
            }
            for m in materials
        ],
    }


@router.post("/{job_id}/cover-letter/generate", response_model=dict[str, Any])
async def generate_cover_letter(
    job_id: int,
    payload: GenerateCoverLetterRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Generate and persist an AI tailored cover letter for the given job."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_profile = session.exec(select(UserProfile)).first()
    if not user_profile:
        user_profile = UserProfile()

    content = await ApplicationGenerator.generate_cover_letter(
        job=job,
        user_profile=user_profile,
        tone=payload.tone,
        custom_instructions=payload.custom_instructions,
    )

    material = ApplicationGenerator.save_material(
        session=session,
        job_id=job.id,
        material_type="cover_letter",
        content_markdown=content,
        tone=payload.tone,
    )

    return {
        "status": "ok",
        "material_id": material.id,
        "job_id": job.id,
        "material_type": "cover_letter",
        "tone": material.tone,
        "content_markdown": material.content_markdown,
    }


@router.post("/{job_id}/tailor-resume/generate", response_model=dict[str, Any])
async def generate_tailored_resume(
    job_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Generate and persist tailored resume bullet points for the given job."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_profile = session.exec(select(UserProfile)).first()
    if not user_profile:
        user_profile = UserProfile()

    content = await ApplicationGenerator.generate_tailored_resume_points(
        job=job,
        user_profile=user_profile,
    )

    material = ApplicationGenerator.save_material(
        session=session,
        job_id=job.id,
        material_type="tailored_resume",
        content_markdown=content,
        tone="professional",
    )

    return {
        "status": "ok",
        "material_id": material.id,
        "job_id": job.id,
        "material_type": "tailored_resume",
        "content_markdown": material.content_markdown,
    }


@router.put("/materials/{material_id}", response_model=dict[str, Any])
async def update_material(
    material_id: int,
    payload: SaveMaterialRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update existing application material content."""
    material = session.get(ApplicationMaterial, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    material.content_markdown = payload.content_markdown
    if payload.tone:
        material.tone = payload.tone
    material.updated_at = utc_now()

    session.add(material)
    session.commit()
    session.refresh(material)

    return {
        "status": "ok",
        "material_id": material.id,
        "content_markdown": material.content_markdown,
        "updated_at": material.updated_at.isoformat(),
    }
