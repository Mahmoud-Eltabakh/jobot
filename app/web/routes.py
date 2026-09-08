"""Web UI endpoints serving Jinja2 templates and HTMX partial views."""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, asc, desc, select

from app.ai.application_generator import ApplicationGenerator
from app.ai.client import get_ai_client
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
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"app_name": settings.app_name, "error": None},
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
    response = HTMLResponse(content="", status_code=303, headers={"Location": "/"})
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_obj.session_token,
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    """Serve register page."""
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"app_name": settings.app_name, "error": None},
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
    response = HTMLResponse(content="", status_code=303, headers={"Location": "/"})
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_obj.session_token,
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
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

    user_profile = get_user_profile(session, current_user.id)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "user_profile": user_profile,
            "current_user": current_user,
        },
    )


@router.get("/web/components/filter-bar", response_class=HTMLResponse)
async def get_filter_bar(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the filter toolbar partial."""
    return templates.TemplateResponse(request=request, name="components/filter_bar.html", context={})


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
    TaskQueue.toggle_pause(session)
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

    # Fetch available models if Ollama is accessible
    from app.ai.client import OllamaAIClient
    available_ollama_models = await OllamaAIClient.fetch_available_models(ollama_base_url)

    return templates.TemplateResponse(
        request=request,
        name="components/settings.html",
        context={
            "user_profile": user_profile,
            "rules": rules,
            "search_configs": search_configs,
            "ai_provider": ai_provider,
            "ollama_base_url": ollama_base_url,
            "ollama_model": ollama_model,
            "ollama_embed_model": ollama_embed_model,
            "available_ollama_models": available_ollama_models,
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
    content = await ApplicationGenerator.generate_cover_letter(
        job=job,
        user_profile=user_profile,
        tone=tone,
        custom_instructions=custom_instructions,
    )

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
        f'class="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-xs text-slate-200 font-mono leading-relaxed focus:outline-none focus:border-emerald-500 custom-scrollbar">{content}</textarea>'
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
    content = await ApplicationGenerator.generate_tailored_resume_points(
        job=job,
        user_profile=user_profile,
    )

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
        f'class="w-full bg-slate-950 border border-slate-800 rounded-xl p-4 text-xs text-slate-200 font-mono leading-relaxed focus:outline-none focus:border-indigo-500 custom-scrollbar">{content}</textarea>'
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

    # Return HTMX response with trigger to refresh views
    return HTMLResponse(
        f'<div id="card-{job.id}" hx-swap-oob="delete"></div>',
        headers={"HX-Trigger": "refreshView"},
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
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Update user profile from web form and return refreshed profile view."""
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

    if experience_history_text is not None:
        try:
            txt = experience_history_text.strip()
            exp_data = json.loads(txt) if txt.startswith("[") else ([{"description": line.strip()} for line in txt.split("\n") if line.strip()] if txt else [])
            user_profile.experience_history_json = json.dumps(exp_data)
        except Exception:
            pass

    if education_text is not None:
        try:
            txt = education_text.strip()
            edu_data = json.loads(txt) if txt.startswith("[") else ([{"description": line.strip()} for line in txt.split("\n") if line.strip()] if txt else [])
            user_profile.education_json = json.dumps(edu_data)
        except Exception:
            pass

    if projects_text is not None:
        try:
            txt = projects_text.strip()
            project_data = json.loads(txt) if txt.startswith("[") else ([{"name": line.strip()} for line in txt.split("\n") if line.strip()] if txt else [])
            user_profile.projects_json = json.dumps(project_data)
        except Exception:
            pass

    if cv_raw_text is not None and cv_raw_text.strip():
        user_profile.cv_raw_text = cv_raw_text.strip()

    user_profile.updated_at = utc_now()

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
        )
        vector_store = get_vector_store()
        ai_client = get_ai_client(session, current_user.id)
        await ProfileEmbedder.embed_and_store_profile(extracted, vector_store, ai_client)
    except Exception as err:
        logger.warning("Failed refreshing vector embeddings on profile save: %s", err)

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
    ai_client = get_ai_client(session, current_user.id)
    count = await JobEvaluator.rescore_all_jobs(
        session=session, ai_client=ai_client, user_id=current_user.id
    )
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
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render popup modal asking whether to start fresh or search more."""
    return templates.TemplateResponse(
        request=request,
        name="components/scrape_modal.html",
        context={},
    )


@router.post("/web/scrape/run", response_class=HTMLResponse)
async def run_scrape_modal_action(
    request: Request,
    mode: str = Query("incremental"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Execute scrape discovery with option to clear new matches or search more."""
    from app.queue.task_queue import TaskQueue

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

    TaskQueue.enqueue(
        session=session,
        task_type="full_discovery",
        payload={"max_queries": 5, "mode": mode},
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

    ai_client = get_ai_client(session, current_user.id)
    generated_bio = await generate_candidate_bio(cand_data, ai_client)

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
                  class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition">{generated_bio}</textarea>
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
    session_cookie: str = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Analyze and sync LinkedIn profile using li_at session cookie."""
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
        except Exception as err:
            logger.error("LinkedIn sync failed: %s", err)
            error_msg = str(err)
    else:
        error_msg = "Please enter a valid LinkedIn profile URL (e.g. https://www.linkedin.com/in/username)."

    return await get_profile_view(
        request=request, session=session, error_message=error_msg, current_user=current_user
    )


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
    return HTMLResponse(items)
