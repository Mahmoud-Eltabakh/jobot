"""Process owned discovery and scoring tasks through their selected AI stages.

Task records carry the owner into each handler and its existing session.
Discovery and evaluation resolve separate clients rather than a global cache.
Explicit worker client injection remains available for deterministic tests.
The established dual loops, claim logic and per-task session lifetime remain.
Provider failures are terminal until the existing owner-checked retry action.
Other task failures retain the queue's established retry-budget behavior.
Only bounded public provider diagnostics are persisted or logged here.
Raw exception messages, causes and provider payloads are not task diagnostics.
Concurrent website results are inspected before any jobs are persisted.
Provider errors cannot be mistaken for an empty successful website scrape.
Cancellation bypasses ordinary Exception handlers and stops loops normally.
This module does not change model assignments or implement automatic failover.
"""

import asyncio
import json
import logging
from typing import Any

from sqlmodel import Session, select

from app.ai.client import AIProviderError, BaseAIClient, get_ai_client
from app.ai.evaluator import JobEvaluator
from app.db.database import engine, get_app_setting, get_user_setting
from app.db.models import Job, ScrapeTask, UserProfile
from app.db.ownership import get_user_profile
from app.queue.task_queue import TaskQueue
from app.scrapers.base import ScrapedJob
from app.scrapers.dedup import save_scraped_jobs
from app.scrapers.filter_pipeline import JobFilterPipeline
from app.scrapers.jobspy_scraper import JobSpyScraper
from app.scrapers.query_strategist import AIQueryStrategist
from app.scrapers.stepstone import StepStoneScraper

logger = logging.getLogger("jobot.queue.worker")


class QueueWorker:
    """Continuous dual-loop background worker processing scraping and AI scoring concurrently in parallel."""

    def __init__(
        self,
        poll_interval_seconds: float = 2.0,
        ai_client: BaseAIClient | None = None,
        maintenance_interval_seconds: float = 60.0,
    ) -> None:
        self.poll_interval = poll_interval_seconds
        self.ai_client = ai_client
        self.maintenance_interval = maintenance_interval_seconds
        self.heartbeat_interval: float | None = None  # None: a third of the lease
        self._running: bool = False
        # kind -> {loop index: task}; a loop exits when idle and its index >= desired size
        self._pools: dict[str, dict[int, asyncio.Task]] = {"scraper": {}, "evaluator": {}}
        self._desired: dict[str, int] = {"scraper": 0, "evaluator": 0}
        self._maintenance_task: asyncio.Task | None = None

    @property
    def _loop_tasks(self) -> list[asyncio.Task]:
        return [t for pool in self._pools.values() for t in pool.values() if not t.done()]

    @staticmethod
    def _pool_size(key: str, default: int) -> int:
        try:
            return max(1, int(get_app_setting(key, default=default)))
        except (TypeError, ValueError):
            return default

    def start(self) -> None:
        """Recover stranded tasks, then start scraper/evaluator loops sized by concurrency settings."""
        if not self._running:
            self._running = True
            # A fresh process has nothing in flight, so any in_progress row is stranded
            with Session(engine) as session:
                TaskQueue.recover_stale_tasks(session)
            self._sync_pools()
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())
            logger.info(
                "Started QueueWorker loops (%d scraper, %d evaluator)",
                self._desired["scraper"], self._desired["evaluator"],
            )

    def _sync_pools(self) -> None:
        """Grow pools to the configured sizes; surplus loops exit by themselves when idle."""
        self._desired["scraper"] = self._pool_size("concurrency_max_scrapers", 2)
        self._desired["evaluator"] = self._pool_size("concurrency_max_evaluators", 3)
        loops = {"scraper": self._scraper_worker_loop, "evaluator": self._evaluator_worker_loop}
        for kind, pool in self._pools.items():
            for index in [i for i, t in pool.items() if t.done()]:
                del pool[index]
            for index in range(self._desired[kind]):
                if index not in pool:
                    pool[index] = asyncio.create_task(loops[kind](index))

    def reclaim_expired_leases(self) -> int:
        """Return in_progress tasks older than the lease to pending (worker died or hung)."""
        with Session(engine) as session:
            return TaskQueue.recover_stale_tasks(session, older_than_seconds=self._lease_seconds())

    async def _maintenance_loop(self) -> None:
        """Periodically reclaim expired leases and apply changed concurrency settings."""
        while self._running:
            try:
                await asyncio.sleep(self.maintenance_interval)
                self.reclaim_expired_leases()
                self._sync_pools()
            except asyncio.CancelledError:
                break
            except Exception as err:
                logger.error("QueueWorker maintenance failed: %s", err, exc_info=True)

    def stop(self) -> None:
        """Stop background worker loops gracefully."""
        self._running = False
        for t in self._loop_tasks:
            t.cancel()
        if self._maintenance_task:
            self._maintenance_task.cancel()
            self._maintenance_task = None
        self._pools = {"scraper": {}, "evaluator": {}}
        logger.info("Stopped QueueWorker background loops")

    async def _scraper_worker_loop(self, index: int = 0) -> None:
        """Dedicated worker loop continuously claiming and executing scraping tasks in parallel."""
        while self._running and index < self._desired["scraper"]:
            try:
                processed_any = False
                with Session(engine) as session:
                    # Claim next scraping task ('scrape_query' or 'full_discovery')
                    task = TaskQueue.claim_next_task(session, task_types=["scrape_query", "full_discovery"])
                    if task:
                        processed_any = True
                        await self._process_task(task, session)

                if not processed_any:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as err:
                logger.error("Error in QueueWorker scraper loop: %s", err, exc_info=True)
                await asyncio.sleep(self.poll_interval)

    async def _evaluator_worker_loop(self, index: int = 0) -> None:
        """Dedicated worker loop continuously claiming and executing AI job evaluations in parallel."""
        while self._running and index < self._desired["evaluator"]:
            try:
                processed_any = False
                with Session(engine) as session:
                    # Claim next scoring task ('evaluate_job' or 'feedback_tune')
                    task = TaskQueue.claim_next_task(session, task_types=["evaluate_job", "feedback_tune"])
                    if task:
                        processed_any = True
                        await self._process_task(task, session)

                if not processed_any:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as err:
                logger.error("Error in QueueWorker evaluator loop: %s", err, exc_info=True)
                await asyncio.sleep(self.poll_interval)

    def _lease_seconds(self) -> float:
        try:
            return max(60.0, float(get_app_setting("task_lease_seconds", default=900)))
        except (TypeError, ValueError):
            return 900.0

    async def _heartbeat(self, task_id: int) -> None:
        """Refresh the claim timestamp so a long-running task is not reclaimed as expired."""
        interval = self.heartbeat_interval or self._lease_seconds() / 3
        while True:
            await asyncio.sleep(interval)
            try:
                # Own session: the task's session is mid-use by the handler.
                with Session(engine) as beat_session:
                    TaskQueue.touch_task(beat_session, task_id)
            except Exception as err:
                logger.warning("Heartbeat failed for task id=%d: %s", task_id, type(err).__name__)

    async def _process_task(self, task: ScrapeTask, session: Session) -> None:
        """Run a task while a heartbeat keeps its lease fresh."""
        beat = asyncio.create_task(self._heartbeat(task.id))
        try:
            await self._dispatch_task(task, session)
        finally:
            beat.cancel()

    async def _dispatch_task(self, task: ScrapeTask, session: Session) -> None:
        """Dispatch a task and persist only safe failure information.

        A typed provider error retains its selected provider, model, category
        and status without stringifying its underlying exception chain.
        mark_failed records bookkeeping and terminal status in one commit,
        never exposing a pending task to another database consumer.
        max_retries is preserved for the explicit retry action to reset.
        No different account, model or provider is attempted as recovery.
        Ordinary failures keep established queue retry behavior but no longer
        expose arbitrary exception messages in persisted diagnostics.
        Failed handlers never reach the completion transition below.
        """
        logger.info("QueueWorker processing task id=%d type='%s'", task.id, task.task_type)
        try:
            payload = json.loads(task.payload_json or "{}")
            if task.task_type == "scrape_query":
                await self._handle_scrape_query(payload, session, task.user_id)
            elif task.task_type == "evaluate_job":
                await self._handle_evaluate_job(payload, session, task.user_id)
            elif task.task_type == "full_discovery":
                await self._handle_full_discovery(payload, session, task.user_id)
            else:
                # No handler exists (e.g. feedback_tune): fail terminally instead of faking completion
                logger.warning("Unsupported task type '%s' for task id=%d", task.task_type, task.id)
                TaskQueue.mark_failed(session, task.id, f"Unsupported task type: {task.task_type[:40]}", terminal=True)
                return

            TaskQueue.mark_completed(session, task.id)
        except asyncio.CancelledError:
            # Shutdown mid-task: hand the claim back so it is not stranded in_progress
            TaskQueue.release_task(session, task.id)
            raise
        except AIProviderError as err:
            diagnostic = json.dumps({
                "provider": err.provider[:40], "model": err.model[:120], "category": err.category,
                "status_code": err.status_code, "message": err.message,
            })
            logger.warning("Provider failure task id=%d: %s", task.id, diagnostic)
            TaskQueue.mark_failed(session, task.id, diagnostic, terminal=True)
        except Exception as err:
            logger.error("Task execution failed id=%d", task.id)
            TaskQueue.mark_failed(session, task.id, "Task execution failed.")

    async def _handle_scrape_query(self, payload: dict[str, Any], session: Session, user_id: int | None) -> None:
        """Execute search query across all target websites in parallel and queue new jobs for evaluation."""
        raw_platforms = payload.get("platforms") or payload.get("platform", "all")
        if isinstance(raw_platforms, str):
            if "," in raw_platforms:
                platforms = [p.strip().lower() for p in raw_platforms.split(",") if p.strip()]
            else:
                platforms = [raw_platforms.strip().lower()]
        elif isinstance(raw_platforms, list):
            platforms = [str(p).strip().lower() for p in raw_platforms if str(p).strip()]
        else:
            platforms = ["all"]

        keywords = payload.get("keywords", "")
        location = payload.get("location", "")
        results_wanted = payload.get("results_wanted", None)
        is_remote = payload.get("is_remote", None)
        if results_wanted is not None:
            results_wanted = int(results_wanted)

        # Read location and work type from UI user profile if not explicit in payload
        profile = get_user_profile(session, user_id, decrypt=True) if user_id else session.exec(select(UserProfile)).first()
        if not location and profile and profile.target_locations_json:
            try:
                target_locs = json.loads(profile.target_locations_json)
                if target_locs and isinstance(target_locs, list) and len(target_locs) > 0:
                    location = target_locs[0]
            except Exception:
                pass
        if not location:
            location = ""

        if is_remote is None:
            work_pref = profile.work_preference if profile else "remote_first"
            is_remote = work_pref in ("remote_first", "remote_only", "any", "remote")

        stagger_delay = float(get_app_setting("scraping_stagger_delay_seconds", default=0.5))

        # Define individual scraper coroutines for parallel execution
        async def run_jobspy_site(site: str) -> list[ScrapedJob]:
            try:
                scraper = JobSpyScraper(default_sites=[site])
                return await scraper.scrape(
                    search_term=keywords,
                    location=location,
                    results_wanted=results_wanted,
                    site_name=[site],
                    is_remote=is_remote,
                )
            except AIProviderError:
                raise
            except Exception as js_err:
                logger.warning("JobSpy scrape failed for site '%s': %s", site, js_err)
                return []

        async def run_stepstone_scraper() -> list[ScrapedJob]:
            try:
                if stagger_delay > 0:
                    await asyncio.sleep(stagger_delay)
                stepstone = StepStoneScraper()
                extra = {}
                if user_id and get_user_setting(session, user_id, "use_ai_scraping", False):
                    extra["ai_client"] = self.ai_client or get_ai_client(session=session, user_id=user_id, task_type="scraping")
                return await stepstone.scrape(
                    search_term=keywords,
                    location=location,
                    results_wanted=results_wanted,
                    is_remote=is_remote,
                    **extra,
                )
            except AIProviderError:
                raise
            except Exception as ss_err:
                logger.warning("StepStone scrape failed in queue: %s", ss_err)
                return []

        # Build parallel scraping tasks based on selected platforms
        scrape_tasks: list[asyncio.Task | Any] = []

        if "all" in platforms:
            scrape_tasks.append(run_jobspy_site("linkedin"))
            scrape_tasks.append(run_jobspy_site("google"))
            scrape_tasks.append(run_stepstone_scraper())
        else:
            for p in platforms:
                if p == "stepstone":
                    scrape_tasks.append(run_stepstone_scraper())
                else:
                    scrape_tasks.append(run_jobspy_site(p))

        # Execute all website scrapers concurrently in parallel
        results = await asyncio.gather(*scrape_tasks, return_exceptions=True)

        scraped_jobs: list[ScrapedJob] = []
        for res in results:
            if isinstance(res, AIProviderError):
                raise res
            if isinstance(res, list):
                scraped_jobs.extend(res)
            elif isinstance(res, Exception):
                logger.warning("Scraping task raised exception: %s", res)

        logger.info(
            "Parallel scrape completed for '%s' in '%s' across platforms %s (is_remote=%s): extracted %d total jobs",
            keywords, location, platforms, is_remote, len(scraped_jobs),
        )

        # Save and deduplicate newly scraped records
        inserted, _ = save_scraped_jobs(scraped_jobs, session, user_id=user_id)
        if inserted:
            filter_pipeline = JobFilterPipeline()
            approved, _ = filter_pipeline.apply_filters_and_save(inserted, session, user_id=user_id)

            # Queue parallel evaluation tasks for approved jobs
            for job in approved:
                TaskQueue.enqueue(
                    session=session,
                    task_type="evaluate_job",
                    payload={"job_id": job.id},
                    user_id=user_id,
                )
            logger.info("Enqueued %d jobs for AI fit evaluation", len(approved))

    async def _handle_evaluate_job(self, payload: dict[str, Any], session: Session, user_id: int | None) -> None:
        """Evaluate a job only after matching its owner to the task owner.

        Resolve scoring after the owned lookup, not before authorization.
        Explicit generation injection does not select an embedding backend.
        The evaluator controls local vectors and commits only on success.
        """
        job_id = payload.get("job_id")
        if not job_id:
            return
        job = session.exec(select(Job).where(Job.id == job_id, Job.user_id == user_id)).first()
        if not job:
            return

        # Resolve AI client with per-user configuration (honours user-specific Ollama URL / model)
        client = self.ai_client or get_ai_client(session=session, user_id=user_id, task_type="scoring")
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

        Uses location and work type preferences read from the UI / candidate profile.
        Resolve scraping for this task owner without retaining a client on
        the singleton worker. Query failures propagate before enqueueing any
        replacement searches. Successful child tasks inherit the same owner
        and the existing explicit location/platform override behavior.
        """
        client = self.ai_client or get_ai_client(session=session, user_id=user_id, task_type="scraping")

        # Read user profile to determine target location and work type
        profile = get_user_profile(session, user_id, decrypt=True) if user_id else session.exec(select(UserProfile)).first()

        # Payload overrides from scrape modal if provided
        override_loc = payload.get("location")
        override_work_pref = payload.get("work_preference")
        override_platforms = payload.get("platforms")

        work_pref = override_work_pref or (profile.work_preference if profile else "remote_first")
        is_remote = work_pref in ("remote_first", "remote_only", "any", "remote")

        queries = await AIQueryStrategist.generate_search_queries(
            session=session,
            max_queries=None,
            ai_client=client,
            user_id=user_id,
            override_location=override_loc,
            override_work_preference=work_pref,
        )

        # Add the deterministic title x skill matrix (capped) alongside AI queries, deduplicated
        from app.scrapers.scheduler import ScraperPipeline
        seen = {(kw.strip().lower(), (loc or "").strip().lower()) for _, kw, loc in queries}
        for platform, kw, loc in ScraperPipeline.build_profile_search_queries(
            session, override_location=override_loc, max_queries=3, user_id=user_id,
        ):
            key = (kw.strip().lower(), (loc or "").strip().lower())
            if key not in seen:
                seen.add(key)
                queries.append((platform, kw, loc))

        # Read scraper settings
        results_wanted = get_user_setting(session, user_id, "scraper_results_wanted", 50) if user_id else 50

        for platform, kw, loc in queries:
            target_loc = loc or override_loc or ""
            if not target_loc and profile and profile.target_locations_json:
                try:
                    locs = json.loads(profile.target_locations_json)
                    if locs and isinstance(locs, list) and len(locs) > 0:
                        target_loc = locs[0]
                except Exception:
                    pass

            target_platforms = override_platforms or ([platform] if platform != "all" else ["all"])

            TaskQueue.enqueue(
                session=session,
                task_type="scrape_query",
                payload={
                    "platform": platform,
                    "platforms": target_platforms,
                    "keywords": kw,
                    "location": target_loc,
                    "results_wanted": results_wanted,
                    "is_remote": is_remote,
                },
                user_id=user_id,
            )
        logger.info(
            "Enqueued %d search query tasks for full discovery (work_pref='%s', is_remote=%s, platforms=%s)",
            len(queries), work_pref, is_remote, override_platforms,
        )


# Global worker instance
_queue_worker: QueueWorker | None = None


def get_queue_worker() -> QueueWorker:
    """Return singleton QueueWorker instance."""
    global _queue_worker
    if _queue_worker is None:
        _queue_worker = QueueWorker()
    return _queue_worker
