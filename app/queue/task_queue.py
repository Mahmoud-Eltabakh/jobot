"""Persistent SQLite-backed task queue manager for Jobot."""

import json
import logging
import time
from typing import Any

from sqlalchemy import update
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, func, select

from app.db.database import get_app_setting, set_app_setting
from app.db.models import ScrapeTask, utc_now

logger = logging.getLogger("jobot.queue.task_queue")

# Maximum allowed serialized payload size (64 KiB) to prevent resource exhaustion
MAX_PAYLOAD_BYTES = 65_536

# Whitelist of valid task types accepted by the background worker
ALLOWED_TASK_TYPES = frozenset({"scrape_query", "evaluate_job", "full_discovery", "feedback_tune"})


class TaskQueue:
    """Manages enqueueing, state transitions, claiming, stats, and controls for ScrapeTask items."""

    @classmethod
    def is_paused(cls, session: Session) -> bool:
        """Check if background worker queue processing is paused."""
        val = get_app_setting("is_queue_paused", False)
        return bool(val)

    @classmethod
    def toggle_pause(cls, session: Session) -> bool:
        """Toggle queue worker pause state."""
        current = cls.is_paused(session)
        new_state = not current
        set_app_setting("is_queue_paused", new_state)
        logger.info("TaskQueue worker pause state changed to: %s", new_state)
        return new_state

    @classmethod
    def enqueue(
        cls,
        session: Session,
        task_type: str,
        payload: dict[str, Any],
        max_retries: int = 3,
        user_id: int | None = None,
    ) -> ScrapeTask:
        """Enqueue a task carrying the account boundary into background work.

        Raises:
            ValueError: If task_type is not in ALLOWED_TASK_TYPES or payload exceeds MAX_PAYLOAD_BYTES.
        """
        if task_type not in ALLOWED_TASK_TYPES:
            raise ValueError(
                f"Unknown task type '{task_type}'. Allowed types: {sorted(ALLOWED_TASK_TYPES)}"
            )
        payload_json = json.dumps(payload)
        if len(payload_json.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"Task payload exceeds maximum allowed size of {MAX_PAYLOAD_BYTES} bytes"
            )
        task = ScrapeTask(
            user_id=user_id,
            task_type=task_type,
            payload_json=payload_json,
            status="pending",
            retries=0,
            max_retries=max_retries,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        logger.info("Enqueued task id=%d type='%s'", task.id, task.task_type)
        return task

    @classmethod
    def claim_next_task(cls, session: Session) -> ScrapeTask | None:
        """Claim the next available pending task atomically if queue is not paused.

        Implements retry logic with exponential backoff to handle SQLite write contention (database is locked).
        """
        if cls.is_paused(session):
            return None

        max_retries = 5
        base_delay = 0.1

        for attempt in range(max_retries):
            try:
                candidate = session.exec(
                    select(ScrapeTask)
                    .where(ScrapeTask.status == "pending")
                    .order_by(ScrapeTask.created_at)
                ).first()

                if candidate:
                    claimed_at = utc_now()
                    result = session.exec(
                        update(ScrapeTask)
                        .where(ScrapeTask.id == candidate.id, ScrapeTask.status == "pending")
                        .values(status="in_progress", updated_at=claimed_at)
                    )
                    session.commit()
                    if result.rowcount:
                        task = session.get(ScrapeTask, candidate.id)
                        if task:
                            return task
                return None
            except OperationalError as err:
                if "database is locked" in str(err).lower():
                    session.rollback()
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning("Database locked during claim_next_task, retrying in %.2fs (attempt %d/%d)", delay, attempt + 1, max_retries)
                        time.sleep(delay)
                    else:
                        logger.error("Failed to claim task due to persistent database lock after %d attempts", max_retries)
                        return None
                else:
                    raise

    @classmethod
    def mark_completed(
        cls,
        session: Session,
        task_id: int,
    ) -> ScrapeTask | None:
        """Mark a task as completed."""
        task = session.get(ScrapeTask, task_id)
        if task:
            task.status = "completed"
            task.updated_at = utc_now()
            task.completed_at = utc_now()
            session.add(task)
            session.commit()
            session.refresh(task)
            logger.info("Task id=%d marked as completed", task_id)
        return task

    @classmethod
    def mark_failed(
        cls,
        session: Session,
        task_id: int,
        error_message: str,
    ) -> ScrapeTask | None:
        """Mark a task as failed or requeue if retries remain."""
        task = session.get(ScrapeTask, task_id)
        if task:
            task.retries += 1
            task.error_message = error_message[:1000]
            task.updated_at = utc_now()

            if task.retries < task.max_retries:
                task.status = "pending"
                logger.warning("Task id=%d failed (retry %d/%d): %s", task_id, task.retries, task.max_retries, error_message)
            else:
                task.status = "failed"
                logger.error("Task id=%d permanently failed after %d retries: %s", task_id, task.retries, error_message)

            session.add(task)
            session.commit()
            session.refresh(task)
        return task

    @classmethod
    def retry_task(cls, session: Session, task_id: int, user_id: int | None = None) -> ScrapeTask | None:
        """Reset an individual task back to pending status for retry."""
        stmt = select(ScrapeTask).where(ScrapeTask.id == task_id)
        if user_id is not None:
            stmt = stmt.where(ScrapeTask.user_id == user_id)
        task = session.exec(stmt).first()
        if task:
            task.status = "pending"
            task.retries = 0
            task.error_message = None
            task.updated_at = utc_now()
            session.add(task)
            session.commit()
            session.refresh(task)
            logger.info("Reset task id=%d back to pending for retry", task_id)
        return task

    @classmethod
    def delete_task(cls, session: Session, task_id: int, user_id: int | None = None) -> bool:
        """Delete an individual task from SQLite queue."""
        stmt = select(ScrapeTask).where(ScrapeTask.id == task_id)
        if user_id is not None:
            stmt = stmt.where(ScrapeTask.user_id == user_id)
        task = session.exec(stmt).first()
        if task:
            session.delete(task)
            session.commit()
            logger.info("Deleted task id=%d from queue", task_id)
            return True
        return False

    @classmethod
    def clear_completed(cls, session: Session, user_id: int | None = None) -> int:
        """Delete all completed tasks from SQLite queue."""
        stmt = select(ScrapeTask).where(ScrapeTask.status == "completed")
        if user_id is not None:
            stmt = stmt.where(ScrapeTask.user_id == user_id)
        completed_tasks = session.exec(stmt).all()
        count = 0
        for t in completed_tasks:
            session.delete(t)
            count += 1
        session.commit()
        logger.info("Cleared %d completed tasks from queue", count)
        return count

    @classmethod
    def clear_all(
        cls,
        session: Session,
        include_in_progress: bool = False,
        user_id: int | None = None,
    ) -> int:
        """Delete all queue tasks (optionally including in-progress tasks)."""
        stmt = select(ScrapeTask)
        if not include_in_progress:
            stmt = stmt.where(ScrapeTask.status != "in_progress")
        if user_id is not None:
            stmt = stmt.where(ScrapeTask.user_id == user_id)
        tasks = session.exec(stmt).all()
        count = 0
        for t in tasks:
            session.delete(t)
            count += 1
        session.commit()
        logger.info("Cleared %d tasks from queue", count)
        return count

    @classmethod
    def retry_all_failed(cls, session: Session, user_id: int | None = None) -> int:
        """Reset all failed tasks back to pending status."""
        stmt = select(ScrapeTask).where(ScrapeTask.status == "failed")
        if user_id is not None:
            stmt = stmt.where(ScrapeTask.user_id == user_id)
        failed_tasks = session.exec(stmt).all()
        count = 0
        for t in failed_tasks:
            t.status = "pending"
            t.retries = 0
            t.error_message = None
            t.updated_at = utc_now()
            session.add(t)
            count += 1
        session.commit()
        logger.info("Reset %d failed tasks back to pending", count)
        return count

    @classmethod
    def get_stats(cls, session: Session, user_id: int | None = None) -> dict[str, Any]:
        """Return total counts of tasks grouped by status and worker state."""
        def count_status(status: str) -> int:
            stmt = select(func.count(ScrapeTask.id)).where(ScrapeTask.status == status)
            if user_id is not None:
                stmt = stmt.where(ScrapeTask.user_id == user_id)
            return session.exec(stmt).one() or 0

        pending = count_status("pending")
        in_progress = count_status("in_progress")
        completed = count_status("completed")
        failed = count_status("failed")
        paused = cls.is_paused(session)
        return {
            "pending": pending or 0,
            "in_progress": in_progress or 0,
            "completed": completed or 0,
            "failed": failed or 0,
            "total": (pending or 0) + (in_progress or 0) + (completed or 0) + (failed or 0),
            "is_paused": paused,
        }
