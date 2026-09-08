"""Asynchronous background worker continuously processing tasks from SQLite task queue."""

import asyncio
import json
import logging
from typing import Any

from sqlmodel import Session, select

from app.ai.client import BaseAIClient, get_ai_client
from app.ai.evaluator import JobEvaluator
from app.db.database import engine
from app.db.models import Job, ScrapeTask
from app.queue.task_queue import TaskQueue
from app.scrapers.base import ScrapedJob
from app.scrapers.dedup import save_scraped_jobs
from app.scrapers.filter_pipeline import JobFilterPipeline
from app.scrapers.jobspy_scraper import JobSpyScraper
from app.scrapers.query_strategist import AIQueryStrategist
from app.scrapers.stepstone import StepStoneScraper

logger = logging.getLogger("jobot.queue.worker")


class QueueWorker:
    """Continuous background worker consuming tasks from SQLite queue."""

    def __init__(
        self,
        poll_interval_seconds: float = 2.0,
        ai_client: BaseAIClient | None = None,
    ) -> None:
        self.poll_interval = poll_interval_seconds
        self.ai_client = ai_client
        self._running: bool = False
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Start background worker task."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._worker_loop())
            logger.info("Started QueueWorker background loop")

    def stop(self) -> None:
        """Stop background worker gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            logger.info("Stopped QueueWorker background loop")

    async def _worker_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                processed_any = False
                with Session(engine) as session:
                    task = TaskQueue.claim_next_task(session)
                    if task:
                        processed_any = True
                        await self._process_task(task, session)

                if not processed_any:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as err:
                logger.error("Error in QueueWorker loop: %s", err, exc_info=True)
                await asyncio.sleep(self.poll_interval)

    async def _process_task(self, task: ScrapeTask, session: Session) -> None:
        """Dispatch task to appropriate handler based on task_type."""
        logger.info("QueueWorker processing task id=%d type='%s'", task.id, task.task_type)
        payload = json.loads(task.payload_json or "{}")

        try:
            if task.task_type == "scrape_query":
                await self._handle_scrape_query(payload, session, task.user_id)
            elif task.task_type == "evaluate_job":
                await self._handle_evaluate_job(payload, session, task.user_id)
            elif task.task_type == "full_discovery":
                await self._handle_full_discovery(payload, session, task.user_id)
            else:
                logger.warning("Unknown task type '%s' for task id=%d", task.task_type, task.id)

            TaskQueue.mark_completed(session, task.id)
        except Exception as err:
            logger.error("Failed processing task id=%d: %s", task.id, err)
            TaskQueue.mark_failed(session, task.id, str(err))

    async def _handle_scrape_query(self, payload: dict[str, Any], session: Session, user_id: int | None) -> None:
        """Execute single search query across scrapers and queue new jobs for evaluation."""
        platform = payload.get("platform", "all")
        keywords = payload.get("keywords", "")
        location = payload.get("location", "")
        results_wanted = payload.get("results_wanted", None)
        if results_wanted is not None:
            results_wanted = int(results_wanted)

        scraped_jobs: list[ScrapedJob] = []

        # 1. JobSpy (LinkedIn & Google)
        if platform in ("all", "linkedin", "google"):
            try:
                sites = ["linkedin", "google"] if platform == "all" else [platform]
                jobspy = JobSpyScraper(default_sites=sites)
                res = await jobspy.scrape(
                    search_term=keywords,
                    location=location,
                    results_wanted=results_wanted,
                    site_name=sites,
                )
                scraped_jobs.extend(res)
            except Exception as err:
                logger.warning("JobSpy scrape failed in queue: %s", err)

        # 2. StepStone
        if platform in ("all", "stepstone"):
            try:
                stepstone = StepStoneScraper()
                res = await stepstone.scrape(
                    search_term=keywords,
                    location=location,
                    results_wanted=results_wanted,
                )
                scraped_jobs.extend(res)
            except Exception as err:
                logger.warning("StepStone scrape failed in queue: %s", err)

        # 3. Save & pre-filter
        inserted, _ = save_scraped_jobs(scraped_jobs, session, user_id=user_id)
        if inserted:
            filter_pipeline = JobFilterPipeline()
            approved, _ = filter_pipeline.apply_filters_and_save(inserted, session, user_id=user_id)
            
            # Queue evaluation tasks for approved jobs
            for job in approved:
                TaskQueue.enqueue(
                    session=session,
                    task_type="evaluate_job",
                    payload={"job_id": job.id},
                    user_id=user_id,
                )
            logger.info("Enqueued %d jobs for AI fit evaluation", len(approved))

    async def _handle_evaluate_job(self, payload: dict[str, Any], session: Session, user_id: int | None) -> None:
        """Evaluate a single job with AI matching engine using per-user AI configuration."""
        job_id = payload.get("job_id")
        if not job_id:
            return
        job = session.exec(select(Job).where(Job.id == job_id, Job.user_id == user_id)).first()
        if not job:
            return

        # Resolve AI client with per-user configuration (honours user-specific Ollama URL / model)
        client = self.ai_client or get_ai_client(session=session, user_id=user_id)
        updated_job = await JobEvaluator.evaluate_and_update_job(
            job_id=job_id,
            session=session,
            ai_client=client,
            user_id=user_id,
        )
        if updated_job:
            logger.info("Evaluated job id=%d '%s' fit_score=%s", updated_job.id, updated_job.title, updated_job.fit_score)

    async def _handle_full_discovery(self, payload: dict[str, Any], session: Session, user_id: int | None) -> None:
        """Generate intelligent search queries and enqueue them as scrape_query tasks.

        Uses per-user AI configuration for query generation.
        """
        client = self.ai_client or get_ai_client(session=session, user_id=user_id)
        queries = await AIQueryStrategist.generate_search_queries(
            session=session,
            max_queries=None,
            ai_client=client,
            user_id=user_id,
        )
        for platform, kw, loc in queries:
            TaskQueue.enqueue(
                session=session,
                task_type="scrape_query",
                payload={"platform": platform, "keywords": kw, "location": loc, "results_wanted": None},
                user_id=user_id,
            )
        logger.info("Enqueued %d search query tasks for full discovery", len(queries))


# Global worker instance
_queue_worker: QueueWorker | None = None


def get_queue_worker() -> QueueWorker:
    """Return singleton QueueWorker instance."""
    global _queue_worker
    if _queue_worker is None:
        _queue_worker = QueueWorker()
    return _queue_worker
