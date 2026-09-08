"""REST API endpoints for monitoring and controlling the background task queue."""

import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select, desc

from app.db.database import get_session
from app.db.models import ScrapeTask
from app.queue.task_queue import TaskQueue

logger = logging.getLogger("jobot.api.queue")

router = APIRouter(prefix="/api/queue", tags=["Queue"])


class EnqueueTaskRequest(BaseModel):
    """Payload for enqueuing an ad-hoc scraping or evaluation task."""

    task_type: str  # "scrape_query", "evaluate_job", "full_discovery"
    payload: dict[str, Any] = Field(default_factory=dict)
    max_retries: int = 3


@router.get("/status", response_model=dict[str, Any])
async def get_queue_status(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Fetch task queue counts and recent task logs."""
    stats = TaskQueue.get_stats(session)
    recent_tasks = session.exec(
        select(ScrapeTask).order_by(desc(ScrapeTask.created_at)).limit(10)
    ).all()

    return {
        "status": "ok",
        "stats": stats,
        "recent_tasks": [
            {
                "id": t.id,
                "task_type": t.task_type,
                "status": t.status,
                "retries": t.retries,
                "error_message": t.error_message,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in recent_tasks
        ],
    }


@router.post("/enqueue", response_model=dict[str, Any])
async def enqueue_task(
    payload: EnqueueTaskRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Enqueue a new task into the background queue."""
    task = TaskQueue.enqueue(
        session=session,
        task_type=payload.task_type,
        payload=payload.payload,
        max_retries=payload.max_retries,
    )
    return {
        "status": "ok",
        "task_id": task.id,
        "task_type": task.task_type,
        "task_status": task.status,
    }


@router.post("/run-discovery", response_model=dict[str, Any])
async def trigger_full_discovery_task(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Enqueue a full discovery job that formulates queries and extracts opportunities in the background."""
    task = TaskQueue.enqueue(
        session=session,
        task_type="full_discovery",
        payload={"max_queries": 5},
    )
    return {
        "status": "ok",
        "message": "Full discovery job successfully queued for background execution.",
        "task_id": task.id,
    }


@router.post("/retry-failed", response_model=dict[str, Any])
async def retry_failed_tasks(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Reset all failed tasks back to pending for worker retry."""
    count = TaskQueue.retry_all_failed(session)
    return {
        "status": "ok",
        "message": f"Successfully reset {count} failed tasks to pending.",
        "retried_count": count,
    }


@router.post("/pause-toggle", response_model=dict[str, Any])
async def toggle_queue_pause(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Toggle background worker pause/resume state."""
    new_state = TaskQueue.toggle_pause(session)
    return {
        "status": "ok",
        "is_paused": new_state,
        "message": "Queue worker paused" if new_state else "Queue worker resumed",
    }


@router.post("/retry/{task_id}", response_model=dict[str, Any])
async def retry_individual_task(
    task_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Reset an individual task to pending for worker retry."""
    task = TaskQueue.retry_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": "ok",
        "message": f"Task #{task_id} reset to pending for retry.",
        "task_id": task_id,
    }


@router.delete("/tasks/{task_id}", response_model=dict[str, Any])
async def delete_queue_task(
    task_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Delete an individual task from the queue."""
    deleted = TaskQueue.delete_task(session, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "status": "ok",
        "message": f"Task #{task_id} deleted successfully.",
        "task_id": task_id,
    }


@router.post("/clear-completed", response_model=dict[str, Any])
async def clear_completed_tasks(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Clear all completed tasks from the queue."""
    count = TaskQueue.clear_completed(session)
    return {
        "status": "ok",
        "message": f"Cleared {count} completed tasks from queue.",
        "cleared_count": count,
    }


@router.post("/clear-all", response_model=dict[str, Any])
async def clear_all_tasks(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Clear all non-running tasks from the queue."""
    count = TaskQueue.clear_all(session, include_in_progress=False)
    return {
        "status": "ok",
        "message": f"Cleared {count} tasks from queue.",
        "cleared_count": count,
    }
