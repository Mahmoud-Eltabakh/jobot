"""Authenticated, secret-free diagnostics and actionable system alerts.

Everything here is derived from the caller's own rows and local state; no
provider, scraper or LinkedIn request is made, so polling stays cheap and
offline-safe. Alerts report only what the queue actually recorded.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, desc, select

from app.auth.dependencies import get_current_user
from app.db.database import get_app_setting, get_session, get_user_setting
from app.db.models import ScrapeTask, User
from app.db.vector import VectorStore, get_vector_store
from app.queue.task_queue import TaskQueue

router = APIRouter(prefix="/api/diagnostics", tags=["Diagnostics"])

# (needles in the stored error, alert code, level, title, advice, target view)
_ERROR_CLASSES: tuple[tuple[tuple[str, ...], str, str, str, str, str], ...] = (
    (("linkedin", "li_at", "authwall", "session cookie"), "linkedin_login", "error",
     "LinkedIn session needs attention",
     "Log in to LinkedIn again and save a fresh session cookie, then retry the task.", "/web/views/profile"),
    (("rate limit", "rate_limit", "429"), "rate_limit", "warning",
     "Provider or site rate limit reached",
     "Wait before retrying, or switch to a different provider in Settings.", "/web/views/settings"),
    (("authentication", "quota", "configuration"), "provider_credentials", "error",
     "AI provider credentials or billing problem",
     "Check the saved API key, quota and endpoint in Settings.", "/web/views/settings"),
    (("unavailable", "timed out", "timeout", "ollama"), "provider_unavailable", "error",
     "AI provider is unreachable",
     "Start Ollama or check connectivity, or switch to another provider in Settings.", "/web/views/settings"),
)


def collect_system_alerts(session: Session, user_id: int) -> list[dict[str, str]]:
    """Return actionable alerts for one account, one entry per distinct cause."""
    alerts: dict[str, dict[str, str]] = {}

    failed = session.exec(
        select(ScrapeTask)
        .where(ScrapeTask.user_id == user_id, ScrapeTask.status == "failed")
        .order_by(desc(ScrapeTask.updated_at))
        .limit(20)
    ).all()
    for task in failed:
        message = (task.error_message or "").strip()
        lowered = message.lower()
        for needles, code, level, title, advice, target in _ERROR_CLASSES:
            if any(n in lowered for n in needles):
                break
        else:
            code, level, title, advice, target = (
                f"task_failed_{task.task_type}", "error", f"Queue task failed: {task.task_type}",
                "Review the error in the AI Queue and retry.", "/web/views/queue",
            )
        # Keep the newest evidence per cause; tasks are ordered newest first.
        alerts.setdefault(code, {
            "code": code, "level": level, "title": title,
            "message": f"{advice} Last error: {message[:160] or 'no message recorded'}",
            "action_target": target,
        })

    if TaskQueue.is_paused(session, user_id):
        alerts["queue_paused"] = {
            "code": "queue_paused", "level": "info", "title": "Queue is paused",
            "message": "Pending tasks will not run until the queue is resumed.",
            "action_target": "/web/views/queue",
        }
    return list(alerts.values())


@router.get("/health")
async def diagnostics_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Report component health for the caller; never includes keys, URLs or cookies."""
    checks: dict[str, Any] = {}

    try:
        session.connection().exec_driver_sql("SELECT 1")
        checks["database"] = {"ok": True}
    except Exception:
        checks["database"] = {"ok": False}

    try:
        # The store is shared across accounts, so no counts are exposed.
        get_vector_store().count(VectorStore.COLLECTION_USER_FEEDBACK)
        checks["vector_store"] = {"ok": True}
    except Exception:
        checks["vector_store"] = {"ok": False}

    stats = TaskQueue.get_stats(session, current_user.id)
    checks["queue"] = {k: stats[k] for k in ("pending", "in_progress", "failed", "is_paused")}

    # Configuration only: reachability is probed by explicit provider tests in Settings.
    provider = get_user_setting(session, current_user.id, "ai_provider", get_app_setting("ai_provider", "ollama"))
    checks["ai"] = {"provider": str(provider)[:32], "reachability": "not_probed"}

    alerts = collect_system_alerts(session, current_user.id)
    degraded = not all(c.get("ok", True) for c in checks.values()) or any(a["level"] == "error" for a in alerts)
    return {"status": "degraded" if degraded else "ok", "checks": checks, "alerts": alerts}
