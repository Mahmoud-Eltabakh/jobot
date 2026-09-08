"""Persistent SQLite-backed task queue manager for Jobot."""

import json
import logging
from datetime import datetime
from typing import Any, Optional
from sqlmodel import Session, select, func
from sqlalchemy import update

from app.db.database import engine, get_app_setting, set_app_setting
from app.db.models import ScrapeTask, utc_now

logger = logging.getLogger("jobot.queue.task_queue")


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
    ) -> ScrapeTask:
        """Enqueue a new task into SQLite."""
        task = ScrapeTask(
            task_type=task_type,
            payload_json=json.dumps(payload),
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
    def claim_next_task(cls, session: Session) -> Optional[ScrapeTask]:
        """Claim the next available pending task atomically if queue is not paused."""
        if cls.is_paused(session):
            return None

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

    @classmethod
    def mark_completed(
        cls,
        session: Session,
        task_id: int,
    ) -> Optional[ScrapeTask]:
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
    ) -> Optional[ScrapeTask]:
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
    def retry_task(cls, session: Session, task_id: int) -> Optional[ScrapeTask]:
        """Reset an individual task back to pending status for retry."""
        task = session.get(ScrapeTask, task_id)
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
    def delete_task(cls, session: Session, task_id: int) -> bool:
        """Delete an individual task from SQLite queue."""
        task = session.get(ScrapeTask, task_id)
        if task:
            session.delete(task)
            session.commit()
            logger.info("Deleted task id=%d from queue", task_id)
            return True
        return False

    @classmethod
    def clear_completed(cls, session: Session) -> int:
        """Delete all completed tasks from SQLite queue."""
        completed_tasks = session.exec(
            select(ScrapeTask).where(ScrapeTask.status == "completed")
        ).all()
        count = 0
        for t in completed_tasks:
            session.delete(t)
            count += 1
        session.commit()
        logger.info("Cleared %d completed tasks from queue", count)
        return count

    @classmethod
    def clear_all(cls, session: Session, include_in_progress: bool = False) -> int:
        """Delete all queue tasks (optionally including in-progress tasks)."""
        stmt = select(ScrapeTask)
        if not include_in_progress:
            stmt = stmt.where(ScrapeTask.status != "in_progress")
        tasks = session.exec(stmt).all()
        count = 0
        for t in tasks:
            session.delete(t)
            count += 1
        session.commit()
        logger.info("Cleared %d tasks from queue", count)
        return count

    @classmethod
    def retry_all_failed(cls, session: Session) -> int:
        """Reset all failed tasks back to pending status."""
        failed_tasks = session.exec(
            select(ScrapeTask).where(ScrapeTask.status == "failed")
        ).all()
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
    def get_stats(cls, session: Session) -> dict[str, Any]:
        """Return total counts of tasks grouped by status and worker state."""
        pending = session.exec(select(func.count(ScrapeTask.id)).where(ScrapeTask.status == "pending")).one()
        in_progress = session.exec(select(func.count(ScrapeTask.id)).where(ScrapeTask.status == "in_progress")).one()
        completed = session.exec(select(func.count(ScrapeTask.id)).where(ScrapeTask.status == "completed")).one()
        failed = session.exec(select(func.count(ScrapeTask.id)).where(ScrapeTask.status == "failed")).one()
        paused = cls.is_paused(session)
        return {
            "pending": pending or 0,
            "in_progress": in_progress or 0,
            "completed": completed or 0,
            "failed": failed or 0,
            "total": (pending or 0) + (in_progress or 0) + (completed or 0) + (failed or 0),
            "is_paused": paused,
        }
