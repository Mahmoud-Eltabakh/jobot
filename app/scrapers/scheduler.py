"""Background scheduler and end-to-end scraping pipeline orchestrator."""

import asyncio
import json
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlmodel import Session, select

from app.ai.client import BaseAIClient, get_ai_client
from app.ai.evaluator import JobEvaluator, extract_keywords_from_profile
from app.core.config import get_settings
from app.db.database import engine, get_app_setting, set_app_setting
from app.db.models import SearchConfig, UserProfile, utc_now
from app.db.ownership import get_user_profile
from app.scrapers.base import ScrapedJob
from app.scrapers.dedup import save_scraped_jobs
from app.scrapers.filter_pipeline import JobFilterPipeline
from app.scrapers.jobspy_scraper import JobSpyScraper
from app.scrapers.query_strategist import AIQueryStrategist
from app.scrapers.stepstone import StepStoneScraper

logger = logging.getLogger("jobot.scrapers.scheduler")


class ScraperPipeline:
    """Orchestrates multi-source scraping, deduplication, pre-filtering, and AI fit scoring."""

    _is_running: bool = False
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def is_running(cls) -> bool:
        """Check if pipeline is currently executing."""
        return cls._is_running

    @classmethod
    def build_profile_search_queries(
        cls,
        session: Session,
        override_keywords: str | None = None,
        override_location: str | None = None,
        max_queries: int | None = None,
        user_id: int | None = None,
    ) -> list[tuple[str, str, str]]:
        """
        Build an intelligent matrix of search queries combining primary target titles with active profile skills.
        No artificial limit is placed on active skills.
        Returns: list of (source_platform, keywords, location) tuples.
        """
        if override_keywords and override_keywords.strip():
            return [("all", override_keywords.strip(), override_location or "")]

        config_stmt = select(SearchConfig).where(SearchConfig.is_active.is_(True))
        if user_id is not None:
            config_stmt = config_stmt.where(SearchConfig.user_id == user_id)
        search_configs = session.exec(config_stmt).all()

        if search_configs:
            return [(sc.source, sc.keywords, sc.location) for sc in search_configs]

        # Dynamic query generation from candidate UserProfile
        profile = get_user_profile(session, user_id, decrypt=True) if user_id is not None else session.exec(select(UserProfile)).first()
        queries: list[tuple[str, str, str]] = []

        if profile:
            try:
                titles = json.loads(profile.target_titles_json) if profile.target_titles_json else []
                active_skills = extract_keywords_from_profile(profile)
                locations = json.loads(profile.target_locations_json) if profile.target_locations_json else []

                loc = locations[0] if locations else ""
                primary_title = titles[0] if titles else (profile.headline or (active_skills[0] if active_skills else ""))

                # 1. Primary target title query
                if primary_title and primary_title.strip():
                    queries.append(("all", primary_title.strip(), loc))

                    # 2. Target title + active skills combinations (without restriction)
                    for skill in active_skills:
                        if skill and skill.strip():
                            combo_kw = f"{primary_title.strip()} {skill.strip()}".strip()
                            if combo_kw not in [q[1] for q in queries]:
                                queries.append(("all", combo_kw, loc))

                # 3. Secondary target titles combined with active skills
                for sec_title in titles[1:]:
                    if sec_title and sec_title.strip():
                        if sec_title.strip() not in [q[1] for q in queries]:
                            queries.append(("all", sec_title.strip(), loc))
                        for skill in active_skills:
                            combo_sec = f"{sec_title.strip()} {skill.strip()}".strip()
                            if combo_sec not in [q[1] for q in queries]:
                                queries.append(("all", combo_sec, loc))
            except Exception as err:
                logger.warning("Failed building profile search queries: %s", err)

        return queries[:max_queries] if max_queries is not None else queries

    @classmethod
    async def run_full_pipeline(
        cls,
        session: Session,
        ai_client: BaseAIClient | None = None,
        override_keywords: str | None = None,
        override_location: str | None = None,
        results_wanted_per_source: int | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Execute full end-to-end job discovery pipeline.
        
        Steps:
          1. Determine search targets (SearchConfig or UserProfile skills/titles).
          2. Execute JobSpy and StepStone scrapers without arbitrary limits.
          3. Deduplicate and insert into SQLite.
          4. Run Pre-Filter pipeline to auto-reject blacklisted positions.
          5. Evaluate approved jobs with LLM (Fit Score & Breakdown).
        """
        async with cls._lock:
            cls._is_running = True
            start_time = utc_now()
            logger.info("Starting ScraperPipeline execution at %s", start_time.isoformat())

            client = ai_client or get_ai_client()
            scraped_jobs: list[ScrapedJob] = []

            # 1. Resolve search queries using AI Query Strategist
            if override_keywords:
                search_queries = [("all", override_keywords.strip(), override_location or "Germany")]
            else:
                search_queries = await AIQueryStrategist.generate_search_queries(
                    session=session,
                    max_queries=None,
                    ai_client=client,
                    user_id=user_id,
                )
            logger.info("Generated %d search query batches from AI Strategist & candidate profile", len(search_queries))

            # ==========================================
            # STAGE 1: SCRAPE
            # ==========================================
            jobspy = JobSpyScraper()
            stepstone = StepStoneScraper()

            for source_target, kw, loc in search_queries:
                try:
                    if source_target in ("all", "linkedin", "google"):
                        sites = ["linkedin", "google"] if source_target == "all" else [source_target]
                        res_js = await jobspy.scrape(
                            search_term=kw,
                            location=loc,
                            results_wanted=results_wanted_per_source,
                            site_name=sites,
                        )
                        scraped_jobs.extend(res_js)
                except Exception as err:
                    logger.warning("JobSpy scrape failed for '%s': %s", kw, err)

                try:
                    if source_target in ("all", "stepstone"):
                        res_ss = await stepstone.scrape(
                            search_term=kw,
                            location=loc,
                            results_wanted=results_wanted_per_source,
                        )
                        scraped_jobs.extend(res_ss)
                except Exception as err:
                    logger.warning("StepStone scrape failed for '%s': %s", kw, err)

            # Deduplicate & persist raw ingested records
            inserted_jobs, skipped_dups = save_scraped_jobs(scraped_jobs, session, user_id=user_id)
            logger.info("Stage 1 (SCRAPE) complete: %d fetched, %d new inserted, %d duplicates skipped", len(scraped_jobs), len(inserted_jobs), skipped_dups)

            # ==========================================
            # STAGE 2: FILTER
            # ==========================================
            approved_for_ai, filtered_out = JobFilterPipeline.apply_filters_and_save(
                inserted_jobs, session, user_id=user_id
            )
            logger.info("Stage 2 (FILTER) complete: %d approved for scoring, %d blacklisted/filtered out", len(approved_for_ai), len(filtered_out))

            # ==========================================
            # STAGE 3: SCORE
            # ==========================================
            evaluated_count = 0
            for job in approved_for_ai:
                if job.id is None:
                    continue
                try:
                    await JobEvaluator.evaluate_and_update_job(
                        job_id=job.id,
                        session=session,
                        ai_client=client,
                        user_id=user_id,
                    )
                    evaluated_count += 1
                except Exception as err:
                    logger.warning("Failed AI evaluation for Job id=%d: %s", job.id, err)
            logger.info("Stage 3 (SCORE) complete: %d jobs evaluated with actual profile skills", evaluated_count)

            # ==========================================
            # STAGE 4: QUEUE / STATS LOGGING
            # ==========================================

            duration = (utc_now() - start_time).total_seconds()
            cls._is_running = False

            stats = {
                "scraped_total": len(scraped_jobs),
                "new_inserted": len(inserted_jobs),
                "duplicates_skipped": skipped_dups,
                "filtered_out": len(filtered_out),
                "ai_evaluated": evaluated_count,
                "duration_seconds": round(duration, 2),
                "completed_at": utc_now().isoformat(),
            }
            logger.info("ScraperPipeline finished: %s", stats)
            set_app_setting("last_scrape_stats", stats)
            return stats


class JobotScheduler:
    """Manages periodic background job scraping cycles using AsyncIOScheduler."""

    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()
        self._is_started = False

    def start(self) -> None:
        """Start background scheduler."""
        if not self._is_started:
            settings = get_settings()
            interval_hours = int(get_app_setting("scraper_default_interval_hours", default=settings.scraper_default_interval_hours))
            
            self.scheduler.add_job(
                self._periodic_task,
                "interval",
                hours=max(1, interval_hours),
                id="periodic_job_scraper",
                replace_existing=True,
            )
            self.scheduler.start()
            self._is_started = True
            logger.info("JobotScheduler started with %d hour interval", interval_hours)

    def shutdown(self) -> None:
        """Stop background scheduler."""
        if self._is_started:
            self.scheduler.shutdown(wait=False)
            self._is_started = False
            logger.info("JobotScheduler shutdown")

    async def _periodic_task(self) -> None:
        """Internal worker executing periodic scrape cycle."""
        logger.info("Executing scheduled periodic scrape cycle...")
        with Session(engine) as session:
            await ScraperPipeline.run_full_pipeline(session)


# Global scheduler singleton
_scheduler_instance: JobotScheduler | None = None


def get_scheduler() -> JobotScheduler:
    """Return JobotScheduler singleton instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = JobotScheduler()
    return _scheduler_instance
