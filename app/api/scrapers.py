"""REST API endpoints for triggering and monitoring scrapers."""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth.dependencies import get_current_user
from app.db.database import get_app_setting, get_session
from app.db.models import SearchConfig, User
from app.scrapers.scheduler import ScraperPipeline

router = APIRouter(prefix="/api/scrapers", tags=["Scrapers"])


class ScrapeTriggerRequest(BaseModel):
    """Optional parameters for on-demand scrape trigger."""

    keywords: str | None = None
    location: str | None = None
    results_wanted: int | None = None


@router.post("/run")
async def trigger_scrape_now(
    params: ScrapeTriggerRequest | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger an immediate scraping, filtering, and AI evaluation cycle."""
    if ScraperPipeline.is_running():
        return {
            "status": "already_running",
            "message": "A scrape cycle is already in progress.",
        }

    # Execute async pipeline in background task
    async def _run_job() -> None:
        # Create fresh session for background worker
        from app.db.database import engine
        with Session(engine) as worker_session:
            kw = params.keywords if params else None
            loc = params.location if params else None
            rw = params.results_wanted if params else None
            await ScraperPipeline.run_full_pipeline(
                session=worker_session,
                override_keywords=kw,
                override_location=loc,
                results_wanted_per_source=rw,
                user_id=current_user.id,
            )

    background_tasks.add_task(_run_job)
    return {
        "status": "triggered",
        "message": "Job scraping and AI evaluation started in background.",
    }


@router.get("/status")
def get_scraper_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Get active scraper status, last run statistics, and configured searches."""
    configs = session.exec(
        select(SearchConfig).where(SearchConfig.user_id == current_user.id)
    ).all()
    last_stats = get_app_setting("last_scrape_stats", default={})

    return {
        "is_running": ScraperPipeline.is_running(),
        "last_stats": last_stats,
        "active_configs": [
            {
                "id": c.id,
                "source": c.source,
                "keywords": c.keywords,
                "location": c.location,
                "is_active": c.is_active,
                "last_run_at": c.last_run_at.isoformat() if c.last_run_at else None,
            }
            for c in configs
        ],
    }
