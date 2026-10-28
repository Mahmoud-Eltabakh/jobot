"""Expose owned application generation with safe upstream failure responses.

Authentication and owned job lookup precede every generation request.
The current account selects the applying assignment and its own credentials.
That client is passed explicitly into the existing domain generator.
An absent saved profile does not remove the authenticated owner boundary.
Resolution and generation share the typed provider-error handling block.
Safe errors expose selected configuration metadata, never raw provider bodies.
Local unavailability/timeouts use 503; other upstream failures use 502.
Neither status represents a successful generation or triggers another model.
Material creation/update occurs strictly after generation has returned content.
Previously saved letters and resume bullets survive failed regeneration.
Success response fields and manual material-edit endpoints remain unchanged.
No automatic employer submission or cross-provider retry is implemented here.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.ai.application_generator import ApplicationGenerator
from app.ai.client import AIProviderError, get_ai_client
from app.auth.dependencies import get_current_user
from app.db.database import get_session
from app.db.models import ApplicationMaterial, Job, User, UserProfile, utc_now
from app.db.ownership import get_user_profile, owned_by_id

logger = logging.getLogger("jobot.api.applications")

router = APIRouter(prefix="/api/jobs", tags=["Applications"])


def _generation_failure(error: AIProviderError) -> HTTPException:
    """Expose bounded adapter diagnostics, never exception chains or payloads.

    A local outage is temporarily unavailable; other selected-provider
    failures are upstream errors. Neither response retries nor saves content.
    """
    status = 503 if error.provider == "ollama" and error.category in ("unavailable", "timeout") else 502
    return HTTPException(status_code=status, detail={
        "provider": error.provider[:40], "model": error.model[:120],
        "category": error.category, "status_code": error.status_code,
        "message": error.message,
    })


class GenerateCoverLetterRequest(BaseModel):
    """Payload for generating tailored cover letter."""

    tone: str = "professional"  # professional, enthusiastic, direct, conversational
    custom_instructions: str | None = None


class SaveMaterialRequest(BaseModel):
    """Payload for updating or saving application material content."""

    content_markdown: str
    tone: str | None = "professional"


@router.get("/{job_id}/materials", response_model=dict[str, Any])
async def get_job_materials(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Fetch all saved application materials for a job."""
    job = owned_by_id(session, Job, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    materials = session.exec(
        select(ApplicationMaterial).where(
            ApplicationMaterial.job_id == job_id,
            ApplicationMaterial.user_id == current_user.id,
        )
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
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate a letter for the authenticated owner and persist on success.

    Verify job ownership before resolving any account provider configuration.
    Keep tone and custom instructions intact while injecting the applying
    client explicitly. Typed resolution/generation failures return bounded
    diagnostics without changing a previous letter's content or timestamps.
    """
    job = owned_by_id(session, Job, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_profile = get_user_profile(session, current_user.id, decrypt=True)
    if not user_profile:
        user_profile = UserProfile(user_id=current_user.id)

    try:
        ai_client = get_ai_client(session, current_user.id, task_type="applying")
        content = await ApplicationGenerator.generate_cover_letter(
            job=job,
            user_profile=user_profile,
            tone=payload.tone,
            custom_instructions=payload.custom_instructions,
            ai_client=ai_client,
        )
    except AIProviderError as error:
        raise _generation_failure(error) from None

    material = ApplicationGenerator.save_material(
        session=session,
        job_id=job.id,
        material_type="cover_letter",
        content_markdown=content,
        tone=payload.tone,
        user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate owned resume bullets without saving provider-failure output.

    The same applying stage and safe failure mapping as cover letters apply.
    No material is created or overwritten until real generation succeeds.
    A missing profile retains the job owner's authenticated account context.
    """
    job = owned_by_id(session, Job, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_profile = get_user_profile(session, current_user.id, decrypt=True)
    if not user_profile:
        user_profile = UserProfile(user_id=current_user.id)

    try:
        ai_client = get_ai_client(session, current_user.id, task_type="applying")
        content = await ApplicationGenerator.generate_tailored_resume_points(
            job=job,
            user_profile=user_profile,
            ai_client=ai_client,
        )
    except AIProviderError as error:
        raise _generation_failure(error) from None

    material = ApplicationGenerator.save_material(
        session=session,
        job_id=job.id,
        material_type="tailored_resume",
        content_markdown=content,
        tone="professional",
        user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Update existing application material content."""
    material = owned_by_id(session, ApplicationMaterial, material_id, current_user.id)
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
