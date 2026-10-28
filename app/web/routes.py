"""Web UI endpoints serving Jinja2 templates and HTMX partial views."""

import json
from datetime import timezone
from html import escape
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, asc, desc, select

from app.ai.application_generator import ApplicationGenerator
from app.ai.client import AIProviderError, get_ai_client, get_embedding_client
from app.ai.embeddings import ProfileEmbedder
from app.ai.evaluator import JobEvaluator
from app.ai.profile_extractor import ExtractedProfile, generate_candidate_bio
from app.auth.dependencies import COOKIE_NAME, get_current_user, get_optional_current_user
from app.auth.security import create_user_session, hash_password, revoke_session, verify_password
from app.core.config import get_settings
from app.db.database import get_app_setting, get_session, get_user_setting
from app.db.models import (
    ApplicationMaterial,
    FeedbackNote,
    FilterRule,
    Job,
    JobStatus,
    JobStatusHistory,
    ScrapeTask,
    SearchConfig,
    User,
    UserProfile,
    utc_now,
)
from app.db.ownership import (
    encrypt_profile,
    get_user_profile,
    migrate_legacy_user_data,
    owned_by_id,
)
from app.db.vector import get_vector_store

logger = logging.getLogger("jobot.web.routes")

router = APIRouter(tags=["Web UI"])
templates = Jinja2Templates(directory="templates")


def provider_failure(error: AIProviderError, retry_url: str = "", retry_target: str = "this", *, retry_include: str = "") -> HTMLResponse:
    """Keep remote bodies out of HTML and routing changes separate from retries."""
    guidance = {"authentication": "Check the saved API key.", "quota": "Check provider billing or switch to local.",
                "rate_limit": "Wait before retrying or switch to local.", "timeout": "Check connectivity before retrying."}
    diagnostic = f"{error.provider[:32]} / {error.model[:200]} / {error.category[:32]} / {error.status_code or ''}: {error.message}"
    include = f' hx-include="{escape(retry_include, quote=True)}"' if retry_include else ""
    retry = (f'<button type="button" hx-post="{escape(retry_url, quote=True)}" hx-target="{escape(retry_target, quote=True)}"{include} class="min-h-[36px] px-3 border rounded">Retry</button>' if retry_url else "")
    content = (f'<div role="alert" class="min-w-0 p-3 border border-rose-700 rounded text-sm text-rose-300 space-y-2" style="overflow-wrap:anywhere">'
               f'<p>{escape(diagnostic)}</p><p>{guidance.get(error.category, "Check provider settings before retrying.")}</p>'
               '<div class="flex flex-wrap gap-2"><button type="button" hx-post="/api/settings/ai/preset" hx-vals=\'{"preset":"local"}\' hx-target="next .local-routing-feedback" class="min-h-[36px] px-3 border rounded">Switch to Local Ollama</button>'
               f'<span class="local-routing-feedback" aria-live="polite"></span>{retry}</div></div>')
    return HTMLResponse(content, status_code=503 if error.provider == "ollama" else 502,
                        headers={"HX-Reswap": "innerHTML"})


async def _record_feedback(
    session: Session,
    job: Job,
    status: str,
    note_text: str | None,
    user_id: int,
    sentiment_override: str | None = None,
) -> str | None:
    """Record an owner-scoped feedback vector; return a user-visible warning on failure."""
    from app.ai.feedback import FeedbackManager

    # Skip unsignalled actions so ordinary moves do not call the embedding model.
    signal = status in FeedbackManager.POSITIVE_STATUSES | FeedbackManager.NEGATIVE_STATUSES \
        or sentiment_override in ("positive", "negative")
    if not signal:
        return None
    try:
        await FeedbackManager.record_job_feedback(
            job_id=job.id, status=status, note_text=note_text, session=session,
            vector_store=get_vector_store(), user_id=user_id, sentiment_override=sentiment_override,
        )
    except AIProviderError as err:
        logger.warning("Feedback vector not recorded for job %s: %s", job.id, err.category)
        return f"Saved, but learning feedback was not recorded ({err.category}). Check the local embedding model."
    except Exception as err:
        logger.warning("Feedback vector not recorded for job %s: %s", job.id, type(err).__name__)
        return "Saved, but learning feedback was not recorded (vector store error)."
    return None


def apply_job_filters(
    statement: Any,
    q: str | None = None,
    min_score: int | None = None,
    work_model: str | None = None,
    min_salary: float | None = None,
    source: str | None = None,
    hide_rejected: bool = False,
    hide_not_fit: bool = False,
    sort_by: str = "fit_score",
    sort_order: str = "desc",
) -> Any:
    """Apply dynamic filtering and sorting to Job query."""
    if q and q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(
            (Job.title.ilike(term)) | (Job.company.ilike(term)) | (Job.description.ilike(term))
        )

    statement = statement.where(Job.fit_score.is_not(None))

    if min_score is not None and min_score > 0:
        statement = statement.where(Job.fit_score >= min_score)

    if work_model == "remote":
        statement = statement.where(Job.is_remote.is_(True))
    elif work_model == "onsite":
        statement = statement.where(Job.is_remote.is_(False))

    if min_salary is not None and min_salary > 0:
        statement = statement.where(
            (Job.salary_min >= min_salary) | (Job.salary_max >= min_salary)
        )

    if source and source.strip() and source != "all":
        statement = statement.where(Job.source == source.strip())

    if hide_rejected:
        statement = statement.where(Job.status != JobStatus.REJECTED.value)
    if hide_not_fit:
        statement = statement.where(Job.status != JobStatus.NOT_A_FIT.value)

    # Sorting
    sort_col = getattr(Job, sort_by, Job.fit_score)
    if sort_order.lower() == "asc":
        statement = statement.order_by(asc(sort_col))
    else:
        statement = statement.order_by(desc(sort_col))

    return statement


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Serve login page."""
    settings = get_settings()
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"app_name": settings.app_name, "error": error},
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Handle web form login submit."""
    settings = get_settings()
    user = session.exec(select(User).where(User.email == email.strip().lower())).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"app_name": settings.app_name, "error": "Invalid email or password"},
            status_code=400,
        )

    session_obj = create_user_session(session, user.id)
    cookie_expires = session_obj.expires_at.replace(tzinfo=timezone.utc) if session_obj.expires_at.tzinfo is None else session_obj.expires_at
    response = HTMLResponse(content="", status_code=303, headers={"Location": "/"})
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_obj.session_token,
        httponly=True,
        secure=settings.env.lower() in {"production", "prod"},
        samesite="lax",
        path="/",
        max_age=7 * 24 * 3600,
        expires=cookie_expires,
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    """Serve register page."""
    settings = get_settings()
    error = request.query_params.get("error")
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"app_name": settings.app_name, "error": error},
    )


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(""),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Handle web form registration submit."""
    settings = get_settings()
    email_clean = email.strip().lower()
    if not email_clean or "@" not in email_clean:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"app_name": settings.app_name, "error": "Invalid email address"},
            status_code=400,
        )
    if len(password) < 10:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"app_name": settings.app_name, "error": "Password must be at least 10 characters"},
            status_code=400,
        )

    existing = session.exec(select(User).where(User.email == email_clean)).first()
    if existing:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"app_name": settings.app_name, "error": "User with this email already exists"},
            status_code=400,
        )

    user = User(
        email=email_clean,
        password_hash=hash_password(password),
        full_name=full_name or "",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    migrate_legacy_user_data(session)
    profile = get_user_profile(session, user.id)
    if not profile:
        profile = UserProfile(user_id=user.id, full_name=user.full_name or "Candidate")
        session.add(profile)
        session.commit()

    session_obj = create_user_session(session, user.id)
    cookie_expires = session_obj.expires_at.replace(tzinfo=timezone.utc) if session_obj.expires_at.tzinfo is None else session_obj.expires_at
    response = HTMLResponse(content="", status_code=303, headers={"Location": "/"})
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_obj.session_token,
        httponly=True,
        secure=settings.env.lower() in {"production", "prod"},
        samesite="lax",
        path="/",
        max_age=7 * 24 * 3600,
        expires=cookie_expires,
    )
    return response


@router.get("/logout", response_class=HTMLResponse)
async def logout_web(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Handle logout and clear authentication cookie."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        revoke_session(session, token)
    response = HTMLResponse(content="", status_code=303, headers={"Location": "/login"})
    response.delete_cookie(key=COOKIE_NAME)
    return response


@router.get("/", response_class=HTMLResponse)
async def index_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User | None = Depends(get_optional_current_user),
) -> HTMLResponse:
    """Serve main application shell or redirect unauthenticated user to auth flow."""
    settings = get_settings()

    if not current_user:
        # Check if any user is registered in the system
        has_any_user = session.exec(select(User)).first() is not None
        if not has_any_user:
            return HTMLResponse(content="", status_code=303, headers={"Location": "/register"})
        return HTMLResponse(content="", status_code=303, headers={"Location": "/login"})

    return HTMLResponse(content="", status_code=303, headers={"Location": "/dashboard"})


def page_context(session: Session, current_user: User, active_page: str) -> dict[str, Any]:
    """Build the shared context required by complete authenticated page shells."""
    return {
        "app_name": get_settings().app_name,
        "user_profile": get_user_profile(session, current_user.id),
        "current_user": current_user,
        "active_page": active_page,
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the refresh-safe dashboard page composed from existing fragments."""
    return templates.TemplateResponse(
        request=request,
        name="pages/dashboard.html",
        context=page_context(session, current_user, "dashboard"),
    )


@router.get("/jobs/board", response_class=HTMLResponse)
async def jobs_board_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the refresh-safe Kanban jobs page from protected fragments."""
    return templates.TemplateResponse(
        request=request,
        name="pages/jobs_board.html",
        context=page_context(session, current_user, "jobs-board"),
    )


@router.get("/jobs/table", response_class=HTMLResponse)
async def jobs_table_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the refresh-safe sortable jobs table from protected fragments."""
    return templates.TemplateResponse(
        request=request,
        name="pages/jobs_table.html",
        context=page_context(session, current_user, "jobs-table"),
    )


@router.get("/queue", response_class=HTMLResponse)
async def queue_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the refresh-safe queue page from its existing protected fragment."""
    return templates.TemplateResponse(
        request=request,
        name="pages/queue.html",
        context=page_context(session, current_user, "queue"),
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the refresh-safe profile page from its existing protected fragment."""
    return templates.TemplateResponse(
        request=request,
        name="pages/profile.html",
        context=page_context(session, current_user, "profile"),
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the refresh-safe settings page from its existing protected fragment."""
    return templates.TemplateResponse(
        request=request,
        name="pages/settings.html",
        context=page_context(session, current_user, "settings"),
    )


@router.get("/web/components/filter-bar", response_class=HTMLResponse)
async def get_filter_bar(
    request: Request,
    view: str = "kanban",
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the filter toolbar partial."""
    view_endpoint = {
        "kanban": "/web/views/kanban",
        "table": "/web/views/table",
    }.get(view, "/web/views/kanban")
    return templates.TemplateResponse(
        request=request,
        name="components/filter_bar.html",
        context={"view_endpoint": view_endpoint},
    )


@router.get("/web/components/queue-status", response_class=HTMLResponse)
async def get_queue_status_component(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the live queue activity widget."""
    from app.queue.task_queue import TaskQueue
    stats = TaskQueue.get_stats(session, current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="components/queue_status.html",
        context={"stats": stats},
    )


@router.get("/web/components/system-alerts", response_class=HTMLResponse)
async def get_system_alerts_component(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render actionable provider/queue alerts for the polled banner."""
    from app.api.diagnostics import collect_system_alerts
    return templates.TemplateResponse(
        request=request,
        name="components/system_alerts.html",
        context={"alerts": collect_system_alerts(session, current_user.id)},
    )


@router.get("/web/views/queue", response_class=HTMLResponse)
async def get_queue_view(
    request: Request,
    session: Session = Depends(get_session),
    status_filter: str | None = "all",
    q: str | None = None,
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render Active AI Task Queue & Control Center partial."""
    from app.queue.task_queue import TaskQueue

    stats = TaskQueue.get_stats(session, current_user.id)

    stmt = select(ScrapeTask).where(ScrapeTask.user_id == current_user.id)
    if status_filter and status_filter != "all":
        stmt = stmt.where(ScrapeTask.status == status_filter.strip().lower())

    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            (ScrapeTask.task_type.ilike(term))
            | (ScrapeTask.payload_json.ilike(term))
            | (ScrapeTask.error_message.ilike(term))
        )

    stmt = stmt.order_by(desc(ScrapeTask.created_at)).limit(100)
    raw_tasks = session.exec(stmt).all()

    # Resolve job details for evaluate_job tasks
    job_ids = []
    for t in raw_tasks:
        try:
            p = json.loads(t.payload_json or "{}")
            if p.get("job_id"):
                job_ids.append(p["job_id"])
        except Exception:
            pass

    job_map = {}
    if job_ids:
        jobs = session.exec(
            select(Job).where(Job.id.in_(job_ids), Job.user_id == current_user.id)
        ).all()
        job_map = {j.id: j for j in jobs}

    enriched_tasks = []
    for t in raw_tasks:
        payload_dict = {}
        job_info = None
        try:
            payload_dict = json.loads(t.payload_json or "{}")
            if "job_id" in payload_dict and payload_dict["job_id"] in job_map:
                job_info = job_map[payload_dict["job_id"]]
        except Exception:
            pass

        enriched_tasks.append({
            "task": t,
            "payload": payload_dict,
            "job": job_info,
        })

    return templates.TemplateResponse(
        request=request,
        name="components/queue_view.html",
        context={
            "stats": stats,
            "tasks": enriched_tasks,
            "status_filter": status_filter or "all",
            "q": q or "",
        },
    )


@router.post("/web/queue/pause-toggle", response_class=HTMLResponse)
async def toggle_queue_pause_web(
    request: Request,
    session: Session = Depends(get_session),
    status_filter: str | None = Form("all"),
    q: str | None = Form(""),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Toggle queue worker pause state and return refreshed queue view."""
    from app.queue.task_queue import TaskQueue
    TaskQueue.toggle_pause(session, current_user.id)
    return await get_queue_view(request=request, session=session, status_filter=status_filter, q=q, current_user=current_user)


@router.post("/web/queue/retry-failed", response_class=HTMLResponse)
async def retry_failed_tasks_web(
    request: Request,
    session: Session = Depends(get_session),
    status_filter: str | None = Form("all"),
    q: str | None = Form(""),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Retry all failed queue tasks and return refreshed queue view."""
    from app.queue.task_queue import TaskQueue
    TaskQueue.retry_all_failed(session, current_user.id)
    return await get_queue_view(request=request, session=session, status_filter=status_filter, q=q, current_user=current_user)


@router.post("/web/queue/clear-completed", response_class=HTMLResponse)
async def clear_completed_tasks_web(
    request: Request,
    session: Session = Depends(get_session),
    status_filter: str | None = Form("all"),
    q: str | None = Form(""),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Clear completed tasks and return refreshed queue view."""
    from app.queue.task_queue import TaskQueue
    TaskQueue.clear_completed(session, current_user.id)
    return await get_queue_view(request=request, session=session, status_filter=status_filter, q=q, current_user=current_user)


@router.post("/web/queue/clear-all", response_class=HTMLResponse)
async def clear_all_tasks_web(
    request: Request,
    session: Session = Depends(get_session),
    status_filter: str | None = Form("all"),
    q: str | None = Form(""),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Clear all non-running tasks and return refreshed queue view."""
    from app.queue.task_queue import TaskQueue
    TaskQueue.clear_all(session, include_in_progress=False, user_id=current_user.id)
    return await get_queue_view(request=request, session=session, status_filter=status_filter, q=q, current_user=current_user)


@router.post("/web/queue/tasks/{task_id}/retry", response_class=HTMLResponse)
async def retry_individual_task_web(
    task_id: int,
    request: Request,
    session: Session = Depends(get_session),
    status_filter: str | None = Form("all"),
    q: str | None = Form(""),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Retry individual task and return refreshed queue view."""
    from app.queue.task_queue import TaskQueue
    if not owned_by_id(session, ScrapeTask, task_id, current_user.id):
        raise HTTPException(status_code=404, detail="Task not found")
    TaskQueue.retry_task(session, task_id, current_user.id)
    return await get_queue_view(request=request, session=session, status_filter=status_filter, q=q, current_user=current_user)


@router.delete("/web/queue/tasks/{task_id}", response_class=HTMLResponse)
async def delete_queue_task_web(
    task_id: int,
    request: Request,
    session: Session = Depends(get_session),
    status_filter: str | None = Form("all"),
    q: str | None = Form(""),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Delete individual task and return refreshed queue view."""
    from app.queue.task_queue import TaskQueue
    TaskQueue.delete_task(session, task_id, current_user.id)
    return await get_queue_view(request=request, session=session, status_filter=status_filter, q=q, current_user=current_user)


@router.get("/web/views/kanban", response_class=HTMLResponse)
async def get_kanban_view(
    request: Request,
    session: Session = Depends(get_session),
    q: str | None = None,
    min_score: int | None = None,
    work_model: str | None = None,
    min_salary: float | None = None,
    source: str | None = None,
    hide_rejected: bool = False,
    hide_not_fit: bool = False,
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render 8-stage Kanban board partial."""
    stmt = select(Job).where(Job.user_id == current_user.id)
    stmt = apply_job_filters(
        stmt,
        q=q,
        min_score=min_score,
        work_model=work_model,
        min_salary=min_salary,
        source=source,
        hide_rejected=hide_rejected,
        hide_not_fit=hide_not_fit,
    )
    jobs = session.exec(stmt).all()

    stages = [
        ("new", "NEW", "border-indigo-500/40 text-indigo-400 bg-indigo-500/10"),
        ("seen", "Seen", "border-indigo-500/40 text-indigo-400 bg-indigo-500/10"),
        ("applied", "Applied", "border-blue-500/40 text-blue-400 bg-blue-500/10"),
        ("waiting for respond", "Waiting", "border-cyan-500/40 text-cyan-400 bg-cyan-500/10"),
        ("1. interview", "1st Interview", "border-amber-500/40 text-amber-400 bg-amber-500/10"),
        ("2. interview", "2nd Interview", "border-orange-500/40 text-orange-400 bg-orange-500/10"),
        ("3. interview", "Final Round", "border-purple-500/40 text-purple-400 bg-purple-500/10"),
        ("not a good fit", "Not a Fit", "border-slate-700 text-slate-400 bg-slate-800/20"),
        ("rejected", "Rejected", "border-rose-500/40 text-rose-400 bg-rose-500/10"),
    ]

    columns = []
    for status_key, label, badge_style in stages:
        col_jobs = [j for j in jobs if j.status == status_key]
        columns.append({
            "status": status_key,
            "label": label,
            "badge_style": badge_style,
            "jobs": col_jobs,
            "count": len(col_jobs),
        })

    return templates.TemplateResponse(
        request=request,
        name="components/kanban.html",
        context={
            "columns": columns,
            "total_jobs": len(jobs),
        },
    )


@router.get("/web/views/table", response_class=HTMLResponse)
async def get_table_view(
    request: Request,
    session: Session = Depends(get_session),
    q: str | None = None,
    min_score: int | None = None,
    work_model: str | None = None,
    min_salary: float | None = None,
    source: str | None = None,
    hide_rejected: bool = False,
    hide_not_fit: bool = False,
    sort_by: str = "fit_score",
    sort_order: str = "desc",
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render sortable Data Table partial."""
    stmt = select(Job).where(Job.user_id == current_user.id)
    stmt = apply_job_filters(
        stmt,
        q=q,
        min_score=min_score,
        work_model=work_model,
        min_salary=min_salary,
        source=source,
        hide_rejected=hide_rejected,
        hide_not_fit=hide_not_fit,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    jobs = session.exec(stmt).all()

    return templates.TemplateResponse(
        request=request,
        name="components/table.html",
        context={
            "jobs": jobs,
            "total_jobs": len(jobs),
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


@router.get("/web/views/settings", response_class=HTMLResponse)
async def get_settings_view(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render Settings and AI Configurator partial."""
    settings = get_settings()
    user_profile = get_user_profile(session, current_user.id)
    rules = session.exec(select(FilterRule).where(FilterRule.user_id == current_user.id)).all()
    search_configs = session.exec(select(SearchConfig).where(SearchConfig.user_id == current_user.id)).all()

    ai_provider = get_user_setting(session, current_user.id, "ai_provider", get_app_setting("ai_provider", "ollama"))
    ollama_base_url = get_user_setting(session, current_user.id, "ollama_base_url", get_app_setting("ollama_base_url", "http://localhost:11434"))
    ollama_model = get_user_setting(session, current_user.id, "ollama_model", get_app_setting("ollama_model", "llama3.1:8b"))
    ollama_embed_model = get_app_setting("ollama_embed_model", "nomic-embed-text")
    openai_base_url = get_user_setting(session, current_user.id, "openai_base_url", get_app_setting("openai_base_url", "https://api.openai.com/v1"))
    openai_model = get_user_setting(session, current_user.id, "openai_model", get_app_setting("openai_model", "gpt-4o-mini"))
    has_openai_api_key = bool(get_user_setting(session, current_user.id, "openai_api_key", ""))
    interval_hours = get_app_setting("scraper_default_interval_hours", 12)

    # Scoring weights
    weight_skills = get_user_setting(session, current_user.id, "weight_skills", get_app_setting("weight_skills", 70))
    weight_title = get_user_setting(session, current_user.id, "weight_title", get_app_setting("weight_title", 15))
    weight_location = get_user_setting(session, current_user.id, "weight_location", get_app_setting("weight_location", 10))
    weight_experience = get_user_setting(session, current_user.id, "weight_experience", get_app_setting("weight_experience", 5))
    weight_vector = get_user_setting(session, current_user.id, "weight_vector", get_app_setting("weight_vector", 20))
    weight_history_skills = get_user_setting(session, current_user.id, "weight_history_skills", get_app_setting("weight_history_skills", 10))
    weight_education = get_user_setting(session, current_user.id, "weight_education", get_app_setting("weight_education", 5))
    weight_projects = get_user_setting(session, current_user.id, "weight_projects", get_app_setting("weight_projects", 10))

    tailscale_enabled = get_user_setting(session, current_user.id, "tailscale_enabled", settings.tailscale_enabled)
    tailscale_hostname = get_user_setting(session, current_user.id, "tailscale_hostname", settings.tailscale_hostname)
    tailscale_ssh_user = get_user_setting(session, current_user.id, "tailscale_ssh_user", settings.tailscale_ssh_user)
    tailscale_ssh_port = get_user_setting(session, current_user.id, "tailscale_ssh_port", settings.tailscale_ssh_port)
    tailscale_app_port = get_user_setting(session, current_user.id, "tailscale_app_port", settings.tailscale_app_port)
    tailscale_magic_dns = get_user_setting(session, current_user.id, "tailscale_magic_dns", settings.tailscale_magic_dns)

    # Concurrency limits
    concurrency_max_scrapers = int(get_user_setting(session, current_user.id, "concurrency_max_scrapers", get_app_setting("concurrency_max_scrapers", settings.concurrency_max_scrapers)))
    concurrency_max_evaluators = int(get_user_setting(session, current_user.id, "concurrency_max_evaluators", get_app_setting("concurrency_max_evaluators", settings.concurrency_max_evaluators)))

    from app.api.settings import get_all_settings
    safe_ai = get_all_settings(session, current_user)
    available_ollama_models = []
    
    scraper_results_wanted = int(get_user_setting(session, current_user.id, "scraper_results_wanted", 50))
    use_ai_scraping = bool(get_user_setting(session, current_user.id, "use_ai_scraping", False))

    return templates.TemplateResponse(
        request=request,
        name="components/settings.html",
        context={
            "user_profile": user_profile,
            "rules": rules,
            "search_configs": search_configs,
            "provider_configs": safe_ai["providers"],
            "task_assignments": safe_ai,
            "ai_provider": ai_provider,
            "ollama_base_url": ollama_base_url,
            "ollama_model": ollama_model,
            "ollama_embed_model": ollama_embed_model,
            "available_ollama_models": available_ollama_models,
            "scraper_results_wanted": scraper_results_wanted,
            "use_ai_scraping": use_ai_scraping,
            "openai_base_url": openai_base_url,
            "openai_model": openai_model,
            "has_openai_api_key": has_openai_api_key,
            "interval_hours": interval_hours,
            "weight_skills": weight_skills,
            "weight_title": weight_title,
            "weight_location": weight_location,
            "weight_experience": weight_experience,
            "weight_vector": weight_vector,
            "weight_history_skills": weight_history_skills,
            "weight_education": weight_education,
            "weight_projects": weight_projects,
            "concurrency_max_scrapers": concurrency_max_scrapers,
            "concurrency_max_evaluators": concurrency_max_evaluators,
            "tailscale_enabled": tailscale_enabled,
            "tailscale_hostname": tailscale_hostname,
            "tailscale_ssh_user": tailscale_ssh_user,
            "tailscale_ssh_port": tailscale_ssh_port,
            "tailscale_app_port": tailscale_app_port,
            "tailscale_magic_dns": tailscale_magic_dns,
        },
    )


@router.get("/web/job/{job_id}/inspect", response_class=HTMLResponse)
async def get_job_inspector(
    job_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render Job Inspector slide-over drawer."""
    job = owned_by_id(session, Job, job_id, current_user.id)
    if not job:
        return HTMLResponse("<div class='p-4 text-rose-400'>Job not found</div>", status_code=404)

    # Parse JSON lists safely
    pros = json.loads(job.pros_json) if job.pros_json else []
    cons = json.loads(job.cons_json) if job.cons_json else []
    missing_skills = json.loads(job.missing_skills_json) if job.missing_skills_json else []

    # Get status history and notes
    history = session.exec(
        select(JobStatusHistory).where(JobStatusHistory.job_id == job_id).order_by(desc(JobStatusHistory.changed_at))
    ).all()
    notes = session.exec(
        select(FeedbackNote).where(
            FeedbackNote.job_id == job_id,
            FeedbackNote.user_id == current_user.id,
        ).order_by(desc(FeedbackNote.created_at))
    ).all()

    # Get existing application materials
    cover_letter = session.exec(
        select(ApplicationMaterial).where(
            ApplicationMaterial.job_id == job_id,
            ApplicationMaterial.material_type == "cover_letter",
            ApplicationMaterial.user_id == current_user.id,
        )
    ).first()
    tailored_resume = session.exec(
        select(ApplicationMaterial).where(
            ApplicationMaterial.job_id == job_id,
            ApplicationMaterial.material_type == "tailored_resume",
            ApplicationMaterial.user_id == current_user.id,
        )
    ).first()

    statuses = [s.value for s in JobStatus]
    failed_task = None
    for candidate in session.exec(select(ScrapeTask).where(
        ScrapeTask.user_id == current_user.id, ScrapeTask.task_type == "evaluate_job",
        ScrapeTask.status == "failed",
    ).order_by(desc(ScrapeTask.id))).all():
        try:
            if json.loads(candidate.payload_json).get("job_id") == job_id:
                failed_task = candidate
                break
        except (ValueError, AttributeError):
            continue

    return templates.TemplateResponse(
        request=request,
        name="components/job_inspector.html",
        context={
            "job": job,
            "pros": pros,
            "cons": cons,
            "missing_skills": missing_skills,
            "history": history,
            "notes": notes,
            "cover_letter": cover_letter,
            "tailored_resume": tailored_resume,
            "statuses": statuses,
            "failed_task": failed_task,
        },
    )


@router.post("/web/job/{job_id}/cover-letter/generate", response_class=HTMLResponse)
async def generate_cover_letter_view(
    job_id: int,
    request: Request,
    tone: str = Form("professional"),
    custom_instructions: str | None = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Generate cover letter from inspector UI and return updated container HTML."""
    job = owned_by_id(session, Job, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_profile = get_user_profile(session, current_user.id, decrypt=True) or UserProfile(user_id=current_user.id)
    try:
        client = get_ai_client(session=session, user_id=current_user.id, task_type="applying")
        content = await ApplicationGenerator.generate_cover_letter(
            job=job, user_profile=user_profile, tone=tone,
            custom_instructions=custom_instructions, ai_client=client,
        )
    except AIProviderError as error:
        return provider_failure(error, f"/web/job/{job.id}/cover-letter/generate", "#cover-letter-container",
                                retry_include=f"#cover-letter-options-{job.id}")

    ApplicationGenerator.save_material(
        session=session,
        job_id=job.id,
        material_type="cover_letter",
        content_markdown=content,
        tone=tone,
        user_id=current_user.id,
    )

    return HTMLResponse(
        f'<form hx-post="/web/job/{job.id}/materials/save" hx-swap="none" class="space-y-2">'
        f'<input type="hidden" name="material_type" value="cover_letter">'
        f'<textarea id="cover-letter-text" name="content_markdown" rows="14" '
        f'class="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-xs text-slate-200 font-mono leading-relaxed focus:outline-none focus:border-emerald-500 custom-scrollbar">{escape(content)}</textarea>'
        f'<div class="flex items-center justify-between pt-1">'
        f'<button type="button" onclick="copyText(\'cover-letter-text\', this)" '
        f'class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition flex items-center space-x-1.5">'
        f'<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>'
        f'<span>Copy to Clipboard</span></button>'
        f'<button type="submit" class="px-3.5 py-1.5 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-white font-medium text-xs transition">Save Changes</button>'
        f'</div></form>'
    )


@router.post("/web/job/{job_id}/tailor-resume/generate", response_class=HTMLResponse)
async def generate_tailored_resume_view(
    job_id: int,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Generate tailored resume points from inspector UI and return updated container HTML."""
    job = owned_by_id(session, Job, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    user_profile = get_user_profile(session, current_user.id, decrypt=True) or UserProfile(user_id=current_user.id)
    try:
        client = get_ai_client(session=session, user_id=current_user.id, task_type="applying")
        content = await ApplicationGenerator.generate_tailored_resume_points(job=job, user_profile=user_profile, ai_client=client)
    except AIProviderError as error:
        return provider_failure(error, f"/web/job/{job.id}/tailor-resume/generate", "#tailored-resume-container")

    ApplicationGenerator.save_material(
        session=session,
        job_id=job.id,
        material_type="tailored_resume",
        content_markdown=content,
        tone="professional",
        user_id=current_user.id,
    )

    return HTMLResponse(
        f'<form hx-post="/web/job/{job.id}/materials/save" hx-swap="none" class="space-y-2">'
        f'<input type="hidden" name="material_type" value="tailored_resume">'
        f'<textarea id="tailored-resume-text" name="content_markdown" rows="14" '
        f'class="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-xs text-slate-200 font-mono leading-relaxed focus:outline-none focus:border-indigo-500 custom-scrollbar">{escape(content)}</textarea>'
        f'<div class="flex items-center justify-between pt-1">'
        f'<button type="button" onclick="copyText(\'tailored-resume-text\', this)" '
        f'class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs transition flex items-center space-x-1.5">'
        f'<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>'
        f'<span>Copy to Clipboard</span></button>'
        f'<button type="submit" class="px-3.5 py-1.5 rounded-lg bg-indigo-700 hover:bg-indigo-600 text-white font-medium text-xs transition">Save Changes</button>'
        f'</div></form>'
    )


@router.post("/web/job/{job_id}/materials/save", response_class=HTMLResponse)
async def save_material_view(
    job_id: int,
    material_type: str = Form(...),
    content_markdown: str = Form(...),
    tone: str = Form("professional"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Persist modified material content from inspector form."""
    if not owned_by_id(session, Job, job_id, current_user.id):
        raise HTTPException(status_code=404, detail="Job not found")
    ApplicationGenerator.save_material(
        session=session,
        job_id=job_id,
        material_type=material_type,
        content_markdown=content_markdown,
        tone=tone,
        user_id=current_user.id,
    )
    return HTMLResponse('<span class="text-xs text-emerald-400 font-semibold">Saved!</span>')


@router.put("/api/jobs/{job_id}/status")
async def update_job_status(
    job_id: int,
    new_status: str = Form(...),
    notes: str | None = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Update job lifecycle status and return refreshed Kanban card."""
    job = owned_by_id(session, Job, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    old_status = job.status
    job.status = new_status
    job.updated_at = utc_now()

    history = JobStatusHistory(
        job_id=job.id,
        old_status=old_status,
        new_status=new_status,
        notes=notes,
    )
    session.add(job)
    session.add(history)
    session.commit()
    session.refresh(job)

    warning = await _record_feedback(session, job, new_status, notes, current_user.id)
    headers = {"HX-Trigger": "refreshView"}
    if warning:
        headers["HX-Trigger-After-Settle"] = json.dumps({"feedbackWarning": warning})

    # Return HTMX response with trigger to refresh views
    return HTMLResponse(
        f'<div id="card-{job.id}" hx-swap-oob="delete"></div>',
        headers=headers,
    )


@router.get("/web/views/profile", response_class=HTMLResponse)
async def get_profile_view(
    request: Request,
    session: Session = Depends(get_session),
    error_message: str | None = None,
    toast_message: str | None = None,
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the candidate profile editing view with structured, parsed profile data."""
    user_profile = get_user_profile(session, current_user.id, decrypt=True)
    
    target_titles = json.loads(user_profile.target_titles_json or "[]") if user_profile else []
    target_locations = json.loads(user_profile.target_locations_json or "[]") if user_profile else []
    all_skills = json.loads(user_profile.skills_json or "[]") if user_profile else []
    active_skills = json.loads(user_profile.active_search_skills_json or "[]") if user_profile else []
    if not active_skills and all_skills:
        active_skills = all_skills

    exp_history = json.loads(user_profile.experience_history_json or "[]") if user_profile else []
    education = json.loads(user_profile.education_json or "[]") if user_profile else []
    projects = json.loads(user_profile.projects_json or "[]") if user_profile else []

    def sort_profile_entries(entries: list[dict]) -> list[dict]:
        return sorted(
            entries,
            key=lambda item: (
                str(item.get("title") or item.get("company") or item.get("school") or item.get("degree") or item.get("field_of_study") or "").lower(),
                str(item.get("company") or item.get("school") or "").lower(),
                str(item.get("duration") or item.get("start_date") or item.get("period") or "").lower(),
            ),
        )

    sorted_exp_history = sort_profile_entries(exp_history)
    sorted_education = sort_profile_entries(education)
    sorted_projects = sort_profile_entries(projects)
    exp_history_str = json.dumps(sorted_exp_history, indent=2) if sorted_exp_history else ""
    education_str = json.dumps(sorted_education, indent=2) if sorted_education else ""
    projects_str = json.dumps(sorted_projects, indent=2) if sorted_projects else ""
    cv_raw_text = (user_profile.cv_raw_text or "") if user_profile else ""
    linkedin_raw_text = (user_profile.linkedin_raw_text or "") if user_profile else ""
    has_linkedin_session = bool(user_profile and user_profile.linkedin_session_cookie)
    if not toast_message:
        toast_message = request.query_params.get("toast_message")
    if not error_message:
        error_message = request.query_params.get("error_message") or request.query_params.get("error")

    from app.auth.linkedin_client import LinkedInOIDCClient
    is_linkedin_linked = bool(user_profile and (user_profile.linkedin_access_token or user_profile.linkedin_user_id))
    linkedin_client_configured = LinkedInOIDCClient().is_configured

    return templates.TemplateResponse(
        request=request,
        name="components/profile.html",
        context={
            "user_profile": user_profile,
            "target_titles_str": ", ".join(target_titles),
            "target_locations_str": ", ".join(target_locations),
            "skills_str": ", ".join(all_skills),
            "all_skills": all_skills,
            "active_skills": active_skills,
            "experience_history_str": exp_history_str,
            "education_str": education_str,
            "projects_str": projects_str,
            "cv_raw_text": cv_raw_text,
            "linkedin_raw_text": linkedin_raw_text,
            "has_linkedin_session": has_linkedin_session,
            "is_linkedin_linked": is_linkedin_linked,
            "linkedin_client_configured": linkedin_client_configured,
            "error_message": error_message,
            "toast_message": toast_message,
        },
    )


@router.post("/web/profile/update", response_class=HTMLResponse)
async def update_profile_form(
    request: Request,
    full_name: str = Form(...),
    headline: str | None = Form(None),
    bio: str | None = Form(None),
    experience_years: float = Form(0.0),
    target_titles: str = Form(...),
    target_locations: str = Form(""),
    target_salary_min: float | None = Form(None),
    work_preference: str = Form("remote_first"),
    skills: str = Form(""),
    active_skills: list[str] = Form(default=[]),
    experience_history_text: str | None = Form(None),
    education_text: str | None = Form(None),
    projects_text: str | None = Form(None),
    cv_raw_text: str | None = Form(None),
    linkedin_raw_text: str | None = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Update user profile from web form and return refreshed profile view."""
    # Parse history sections first so invalid JSON rejects the whole save
    def _parse_section(text: str | None, label: str, line_key: str) -> list | None:
        if text is None:
            return None
        txt = text.strip()
        if txt.startswith("[") or txt.startswith("{"):
            try:
                data = json.loads(txt)
            except ValueError:
                raise ValueError(label) from None
            if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
                raise ValueError(label)
            return data
        return [{line_key: line.strip()} for line in txt.split("\n") if line.strip()]

    try:
        exp_data = _parse_section(experience_history_text, "Experience history", "description")
        edu_data = _parse_section(education_text, "Education", "description")
        project_data = _parse_section(projects_text, "Projects", "name")
    except ValueError as bad:
        return await get_profile_view(
            request=request, session=session, current_user=current_user,
            error_message=f"{bad} is not valid JSON (expected a list of objects). Nothing was saved.",
        )

    titles_list = [t.strip() for t in target_titles.split(",") if t.strip()]
    locations_list = [l.strip() for l in target_locations.split(",") if l.strip()]
    skills_list = [s.strip() for s in skills.split(",") if s.strip()]
    active_skills_list = active_skills if active_skills else skills_list

    user_profile = get_user_profile(session, current_user.id, decrypt=True)
    if not user_profile:
        user_profile = UserProfile(user_id=current_user.id, full_name=full_name, updated_at=utc_now())
        session.add(user_profile)

    user_profile.full_name = full_name
    user_profile.headline = headline
    user_profile.bio = bio
    user_profile.experience_years = experience_years
    user_profile.target_titles_json = json.dumps(titles_list)
    user_profile.target_locations_json = json.dumps(locations_list)
    user_profile.target_salary_min = target_salary_min
    user_profile.work_preference = work_preference
    user_profile.skills_json = json.dumps(skills_list)
    user_profile.active_search_skills_json = json.dumps(active_skills_list)

    if exp_data is not None:
        user_profile.experience_history_json = json.dumps(exp_data)
    if edu_data is not None:
        user_profile.education_json = json.dumps(edu_data)
    if project_data is not None:
        user_profile.projects_json = json.dumps(project_data)

    if cv_raw_text is not None and cv_raw_text.strip():
        user_profile.cv_raw_text = cv_raw_text.strip()
    if linkedin_raw_text is not None and linkedin_raw_text.strip():
        user_profile.linkedin_raw_text = linkedin_raw_text.strip()

    user_profile.updated_at = utc_now()
    history_for_vectors = json.loads(user_profile.experience_history_json or "[]")

    encrypt_profile(user_profile, current_user.id)
    session.add(user_profile)
    session.commit()
    session.refresh(user_profile)

    # Sync ChromaDB vector store
    try:
        extracted = ExtractedProfile(
            full_name=user_profile.full_name,
            headline=user_profile.headline,
            summary=user_profile.bio or "",
            skills=skills_list,
            active_search_skills=active_skills_list,
            experience_years=user_profile.experience_years,
            target_titles=titles_list,
            target_locations=locations_list,
            target_salary_min=user_profile.target_salary_min,
            work_preference=user_profile.work_preference,
            linkedin_url=user_profile.linkedin_url,
            experience_history=history_for_vectors,
            education=[{k: str(v) for k, v in e.items()} for e in (edu_data or [])],
            projects=project_data or [],
        )
        vector_store = get_vector_store()
        local = get_embedding_client(session=session, user_id=current_user.id)
        await ProfileEmbedder.embed_and_store_profile(extracted, vector_store, embedding_client=local, session=session, user_id=current_user.id)
    except Exception as err:
        return await get_profile_view(request=request, session=session, current_user=current_user,
                                      error_message="Profile saved; local embeddings were not synchronized.")

    # Purge any jobs that do not match the updated candidate profile skills
    try:
        purged = JobEvaluator.purge_non_matching_jobs(session, user_id=current_user.id)
        logger.info("Purged %d non-matching jobs from databank after profile update", purged)
    except Exception as purge_err:
        logger.warning("Failed purging non-matching jobs on profile save: %s", purge_err)

    return await get_profile_view(request=request, session=session, current_user=current_user)


@router.post("/web/profile/rescore-filter", response_class=HTMLResponse)
async def rescore_and_filter_view(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Re-evaluate and rescore all stored jobs against candidate profile and purge non-matches."""
    try:
        ai_client = get_ai_client(session=session, user_id=current_user.id, task_type="scoring")
        count = await JobEvaluator.rescore_all_jobs(session=session, ai_client=ai_client, user_id=current_user.id)
    except AIProviderError as error:
        return provider_failure(error)
    logger.info("Rescored and filtered %d jobs from UI action", count)

    return await get_profile_view(
        request=request,
        session=session,
        toast_message=f"Rescored and Filtered {count} stored jobs successfully!",
        current_user=current_user,
    )


@router.get("/web/components/scrape-modal", response_class=HTMLResponse)
async def get_scrape_modal_view(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render popup modal asking whether to start fresh or search more, prefilled with location and work type from UI profile."""
    profile = get_user_profile(session, current_user.id, decrypt=True)
    target_locations = json.loads(profile.target_locations_json or "[]") if profile else []
    target_locations_str = ", ".join(target_locations) if target_locations else ""
    work_preference = profile.work_preference if profile else "remote_first"

    return templates.TemplateResponse(
        request=request,
        name="components/scrape_modal.html",
        context={
            "user_profile": profile,
            "target_locations_str": target_locations_str,
            "work_preference": work_preference,
        },
    )


@router.post("/web/scrape/run", response_class=HTMLResponse)
async def run_scrape_modal_action(
    request: Request,
    mode: str = Query("incremental"),
    target_locations: str | None = Form(None),
    work_preference: str | None = Form(None),
    platforms: list[str] = Form(default=[]),
    custom_platforms: str | None = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Execute scrape discovery with option to clear new matches or search more, reading and persisting location, work type, and target platforms from UI."""
    from app.queue.task_queue import TaskQueue

    profile = get_user_profile(session, current_user.id, decrypt=True)
    if profile:
        # Update target locations and work preference if modified in UI modal
        if target_locations is not None:
            locs_list = [l.strip() for l in target_locations.split(",") if l.strip()]
            profile.target_locations_json = json.dumps(locs_list)
        if work_preference is not None and work_preference.strip():
            profile.work_preference = work_preference.strip()
        profile.updated_at = utc_now()
        from app.db.ownership import encrypt_profile
        encrypt_profile(profile, current_user.id)
        session.add(profile)
        session.commit()

    cleared_count = 0
    if mode == "fresh":
        new_jobs = session.exec(
            select(Job).where(
                (Job.status == JobStatus.NEW.value) | (Job.status == JobStatus.SEEN.value)
            ).where(Job.user_id == current_user.id)
        ).all()
        for j in new_jobs:
            session.delete(j)
        cleared_count = len(new_jobs)
        session.commit()
        logger.info("Cleared %d existing new/seen jobs for fresh discovery", cleared_count)

    loc_val = target_locations.strip() if target_locations and target_locations.strip() else None
    work_val = work_preference.strip() if work_preference and work_preference.strip() else None

    # Collect selected and custom platforms
    selected_platforms = list(platforms)
    if custom_platforms and custom_platforms.strip():
        for p in custom_platforms.split(","):
            p_clean = p.strip().lower()
            if p_clean and p_clean not in selected_platforms:
                selected_platforms.append(p_clean)

    if not selected_platforms:
        selected_platforms = ["all"]

    TaskQueue.enqueue(
        session=session,
        task_type="full_discovery",
        payload={
            "max_queries": 5,
            "mode": mode,
            "location": loc_val,
            "work_preference": work_val,
            "platforms": selected_platforms,
        },
        user_id=current_user.id,
    )

    msg = f"Fresh discovery queued! Cleared {cleared_count} old matches." if mode == "fresh" else "Incremental search discovery queued!"

    html = f"""
    <div id="toast-notification" class="fixed bottom-5 right-5 z-50 bg-slate-900 border border-emerald-500 text-emerald-300 px-4 py-3 rounded-xl shadow-2xl font-semibold text-xs flex items-center space-x-2 animate-bounce cursor-pointer" onclick="this.remove()">
        <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
        <span>{msg}</span>
    </div>
    <script>
        setTimeout(() => {{
            let toast = document.getElementById('toast-notification');
            if (toast) toast.remove();
        }}, 4000);
    </script>
    """
    return HTMLResponse(content=html, headers={"HX-Trigger": "refreshView"})


@router.post("/web/profile/generate-bio", response_class=HTMLResponse)
async def generate_profile_bio_web(
    request: Request,
    full_name: str | None = Form(None),
    headline: str | None = Form(None),
    experience_years: float | None = Form(None),
    target_titles: str | None = Form(None),
    skills: str | None = Form(None),
    work_preference: str | None = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Generate executive summary / bio using AI and return swapped textarea component HTML."""
    profile = get_user_profile(session, current_user.id, decrypt=True)

    titles_list = [t.strip() for t in target_titles.split(",") if t.strip()] if target_titles else (json.loads(profile.target_titles_json or "[]") if profile else [])
    skills_list = [s.strip() for s in skills.split(",") if s.strip()] if skills else (json.loads(profile.skills_json or "[]") if profile else [])

    cand_data = {
        "full_name": full_name or (profile.full_name if profile else ""),
        "headline": headline or (profile.headline if profile else ""),
        "experience_years": experience_years if experience_years is not None else (profile.experience_years if profile else 0.0),
        "target_titles": titles_list,
        "skills": skills_list,
        "work_preference": work_preference or (profile.work_preference if profile else "remote_first"),
        "cv_raw_text": profile.cv_raw_text if profile else "",
        "bio": profile.bio if profile else "",
    }

    try:
        ai_client = get_ai_client(session=session, user_id=current_user.id, task_type="scraping")
        generated_bio = await generate_candidate_bio(cand_data, ai_client)
    except AIProviderError as error:
        return provider_failure(error, "/web/profile/generate-bio", "#bio-textarea-container")

    if profile:
        profile.bio = generated_bio
        profile.updated_at = utc_now()
        encrypt_profile(profile, current_user.id)
        session.add(profile)
        session.commit()

    html = f"""
    <div id="bio-textarea-container" class="space-y-1.5">
        <div class="flex items-center justify-between">
            <label class="block text-slate-400 font-medium">Professional Bio / Executive Summary</label>
            <button type="button" 
                    hx-post="/web/profile/generate-bio" 
                    hx-target="#bio-textarea-container" 
                    hx-swap="outerHTML"
                    hx-include="[name='full_name'], [name='headline'], [name='experience_years'], [name='target_titles'], [name='skills'], [name='work_preference']"
                    class="px-2.5 py-1 rounded bg-indigo-950 hover:bg-indigo-900 border border-indigo-700/60 text-indigo-300 font-semibold text-[11px] transition flex items-center space-x-1 shadow-sm active:scale-95">
                <svg class="w-3.5 h-3.5 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                <span>Generate Bio with AI</span>
            </button>
        </div>
        <textarea name="bio" rows="3" placeholder="2-3 sentence executive summary of your expertise and background..."
                  class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition">{escape(generated_bio)}</textarea>
        <p class="text-[10px] text-emerald-400 flex items-center space-x-1">
            <svg class="w-3 h-3 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
            <span>Executive summary generated automatically with AI! Click "Save Profile" below to sync vectors.</span>
        </p>
    </div>
    """
    return HTMLResponse(content=html)


@router.post("/web/profile/linkedin/sync", response_class=HTMLResponse)
async def sync_linkedin_form(
    request: Request,
    linkedin_url: str = Form(...),
    session_cookie: str | None = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Analyze and sync LinkedIn profile using a pasted or stored encrypted li_at cookie."""
    from app.ai.linkedin_analyzer import LinkedInProfileAnalyzer

    error_msg = None
    if linkedin_url and "linkedin.com" in linkedin_url:
        try:
            await LinkedInProfileAnalyzer.sync_linkedin_to_profile(
                session=session,
                linkedin_url=linkedin_url.strip(),
                session_cookie=session_cookie.strip() if session_cookie else None,
                user_id=current_user.id,
            )
        except AIProviderError as err:
            return provider_failure(err)
        except ValueError as err:
            # Analyzer ValueErrors are static guidance (missing/expired cookie), never secrets
            error_msg = str(err)
        except Exception:
            error_msg = "LinkedIn synchronization failed. Check the URL and session cookie."
    else:
        error_msg = "Please enter a valid LinkedIn profile URL (e.g. https://www.linkedin.com/in/username)."

    return await get_profile_view(
        request=request, session=session, error_message=error_msg, current_user=current_user
    )


@router.post("/web/profile/linkedin/pdf", response_class=HTMLResponse)
async def import_linkedin_pdf(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Store text from a user-exported LinkedIn PDF without contacting LinkedIn or auto-analyzing it."""
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        return await get_profile_view(request=request, session=session, current_user=current_user,
                                      error_message="Upload a LinkedIn profile PDF file.")
    try:
        from app.ai.cv_parser import CVParser

        raw_text = CVParser().extract_text_from_bytes(await file.read(), filename)
        if not raw_text:
            raise ValueError("The PDF did not contain readable text")
    except ValueError as error:
        return await get_profile_view(request=request, session=session, current_user=current_user,
                                      error_message=f"LinkedIn PDF import failed: {error}")

    profile = get_user_profile(session, current_user.id, decrypt=True)
    if not profile:
        profile = UserProfile(user_id=current_user.id, full_name=current_user.full_name or "Candidate", updated_at=utc_now())
        session.add(profile)
    profile.linkedin_raw_text = raw_text
    profile.linkedin_session_cookie = None
    profile.updated_at = utc_now()
    encrypt_profile(profile, current_user.id)
    session.add(profile)
    session.commit()
    return await get_profile_view(request=request, session=session, current_user=current_user,
                                  toast_message="LinkedIn PDF imported. Review the extracted text before saving profile details.")


def _linkedin_badge(label: str, tone: str) -> HTMLResponse:
    colors = {
        "ok": "bg-emerald-950 border-emerald-800 text-emerald-400",
        "bad": "bg-rose-950 border-rose-800 text-rose-300",
        "idle": "bg-slate-900 border-slate-700 text-slate-400",
    }[tone]
    return HTMLResponse(
        f'<span id="linkedin-session-badge" class="text-xs px-2.5 py-1 rounded border font-mono {colors}">{escape(label)}</span>'
    )


@router.post("/web/profile/linkedin/login", response_class=HTMLResponse)
async def linkedin_login_form(
    request: Request,
    linkedin_email: str = Form(""),
    linkedin_password: str = Form(""),
    linkedin_code: str = Form(""),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Log in with credentials via Playwright; only the encrypted li_at cookie is persisted."""
    from app.scrapers.linkedin_auth import LinkedInAuthManager

    result = await LinkedInAuthManager.login_and_capture_session(
        email=linkedin_email, password=linkedin_password, session=session, user_id=current_user.id,
        verification_code=linkedin_code,
    )
    if result.get("success"):
        return await get_profile_view(
            request=request, session=session, current_user=current_user,
            toast_message="Logged in to LinkedIn. Session cookie stored encrypted; credentials were not saved.",
        )
    return await get_profile_view(
        request=request, session=session, current_user=current_user,
        error_message=result.get("error") or "LinkedIn login failed.",
    )


@router.get("/web/profile/linkedin/status", response_class=HTMLResponse)
async def linkedin_session_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Validate the stored li_at cookie and return a status badge."""
    from app.scrapers.linkedin_auth import LinkedInAuthManager

    profile = get_user_profile(session, current_user.id, decrypt=True)
    cookie = profile.linkedin_session_cookie if profile else None
    if not cookie:
        return _linkedin_badge("Needs login", "idle")
    if await LinkedInAuthManager.validate_session_cookie(cookie):
        return _linkedin_badge("Logged In (Active)", "ok")
    return _linkedin_badge("Expired - log in again", "bad")


@router.post("/api/jobs/{job_id}/notes")
async def add_job_note(
    job_id: int,
    request: Request,
    note_text: str = Form(...),
    sentiment: str = Form("neutral"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Add a feedback note to a job and return updated notes timeline."""
    job = owned_by_id(session, Job, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    note = FeedbackNote(
        user_id=current_user.id,
        job_id=job.id,
        note_text=note_text.strip(),
        sentiment=sentiment,
        created_at=utc_now(),
    )
    session.add(note)
    session.commit()

    warning = await _record_feedback(
        session, job, job.status, note.note_text, current_user.id, sentiment_override=sentiment,
    )

    notes = session.exec(
        select(FeedbackNote).where(
            FeedbackNote.job_id == job_id,
            FeedbackNote.user_id == current_user.id,
        ).order_by(desc(FeedbackNote.created_at))
    ).all()

    items = "".join([
        f'<div class="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-200">'
        f'<div class="flex justify-between text-slate-400 text-[10px] mb-1">'
        f'<span class="font-medium text-emerald-400 uppercase">{n.sentiment}</span>'
        f'<span>{n.created_at.strftime("%Y-%m-%d %H:%M")}</span>'
        f'</div>{n.note_text}</div>'
        for n in notes
    ])
    if warning:
        items += f'<div role="alert" class="p-2.5 text-xs text-amber-300">{escape(warning)}</div>'
    return HTMLResponse(items)
