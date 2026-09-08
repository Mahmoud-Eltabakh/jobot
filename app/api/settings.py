"""REST API router for application settings, AI provider testing, blacklist rules, and CV upload."""

import asyncio
import html
import json
import logging
import re
import shutil
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.ai.client import OllamaAIClient, OpenAICompatibleClient, get_ai_client
from app.ai.cv_parser import CVParser
from app.ai.embeddings import ProfileEmbedder
from app.ai.profile_extractor import extract_profile_from_text, save_profile_to_db
from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.db.database import get_app_setting, get_session, get_user_setting, set_user_setting
from app.db.models import FilterRule, User, utc_now
from app.db.ownership import get_user_profile, owned_by_id
from app.db.vector import get_vector_store

logger = logging.getLogger("jobot.api.settings")

router = APIRouter(
    prefix="/api/settings",
    tags=["Settings"],
    dependencies=[Depends(get_current_user)],
)

REMOTE_HOST_PATTERN = re.compile(r"^[A-Za-z0-9._:-]*$")
SSH_USER_PATTERN = re.compile(r"^[A-Za-z0-9._-]*$")


async def get_tailscale_status() -> dict[str, Any]:
    """Return local Tailscale status without blocking the web request indefinitely."""
    executable = shutil.which("tailscale")
    if not executable:
        return {"installed": False, "online": False, "hostname": "", "addresses": []}

    try:
        process = await asyncio.create_subprocess_exec(
            executable,
            "status",
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as error:
        return {
            "installed": True,
            "online": False,
            "hostname": "",
            "addresses": [],
            "error": str(error),
        }
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=2.5)
    except TimeoutError:
        process.kill()
        await process.communicate()
        return {
            "installed": True,
            "online": False,
            "hostname": "",
            "addresses": [],
            "error": "Status check timed out",
        }

    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace").strip()
        return {
            "installed": True,
            "online": False,
            "hostname": "",
            "addresses": [],
            "error": message or "Tailscale is offline",
        }

    try:
        payload = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {
            "installed": True,
            "online": False,
            "hostname": "",
            "addresses": [],
            "error": "Invalid Tailscale status response",
        }

    local_device = payload.get("Self") or {}
    hostname = str(local_device.get("DNSName") or local_device.get("HostName") or "").rstrip(".")
    addresses = [str(address) for address in local_device.get("TailscaleIPs") or []]
    return {
        "installed": True,
        "online": bool(local_device.get("Online", payload.get("BackendState") == "Running")),
        "hostname": hostname,
        "addresses": addresses,
    }


def render_ollama_model_options_html(models: list[str], current_model: str) -> str:
    """Generate HTML select dropdown and datalist for Ollama models.

    All model names are HTML-escaped before injection to prevent XSS via
    malicious Ollama server responses.
    """
    safe_current = html.escape(current_model or "")
    if not models:
        return (
            f'<div class="relative">'
            f'<input type="text" name="ollama_model" value="{safe_current}" '
            f'class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-200 font-mono focus:border-emerald-500" '
            f'placeholder="e.g. llama3.1:8b, qwen2.5:7b">'
            f'<div class="text-[10px] text-amber-400 mt-1">No models detected on Ollama host. Pull a model (e.g. <code>ollama run llama3.1:8b</code>).</div>'
            f'</div>'
        )

    options_html = "".join(
        f'<option value="{html.escape(m)}" {"selected" if m == current_model else ""}>{html.escape(m)}</option>'
        for m in models
    )
    if current_model and current_model not in models:
        options_html = f'<option value="{safe_current}" selected>{safe_current} (Custom)</option>' + options_html

    return (
        f'<div class="space-y-1">'
        f'<select name="ollama_model" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-200 font-mono focus:border-emerald-500 text-xs">'
        f'{options_html}'
        f'</select>'
        f'<div class="text-[10px] text-emerald-400 flex items-center justify-between">'
        f'<span>{len(models)} model{"s" if len(models) != 1 else ""} discovered on Ollama host.</span>'
        f'</div>'
        f'</div>'
    )


@router.get("/ollama/models")
async def get_ollama_models(
    ollama_base_url: str | None = None,
    current_model: str | None = None,
) -> Any:
    """Fetch discovered models from local or host Ollama instance."""
    base_url = (ollama_base_url or get_app_setting("ollama_base_url", "http://localhost:11434")).strip()
    active_model = (current_model or get_app_setting("ollama_model", "llama3.1:8b")).strip()
    models = await OllamaAIClient.fetch_available_models(base_url)
    return HTMLResponse(render_ollama_model_options_html(models, active_model))


@router.get("")
def get_all_settings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve all current system settings, AI configuration, and filter rules."""
    settings = get_settings()
    rules = session.exec(select(FilterRule).where(FilterRule.user_id == current_user.id)).all()
    user_profile = get_user_profile(session, current_user.id)

    return {
        "ai_provider": get_user_setting(session, current_user.id, "ai_provider", get_app_setting("ai_provider", settings.ai_provider)),
        "ollama_base_url": get_user_setting(session, current_user.id, "ollama_base_url", get_app_setting("ollama_base_url", settings.ollama_base_url)),
        "ollama_model": get_user_setting(session, current_user.id, "ollama_model", get_app_setting("ollama_model", settings.ollama_model)),
        "openai_model": get_user_setting(session, current_user.id, "openai_model", get_app_setting("openai_model", settings.openai_model)),
        "has_openai_key": bool(get_user_setting(session, current_user.id, "openai_api_key", settings.openai_api_key)),
        "rules_count": len(rules),
        "has_profile": user_profile is not None,
        "remote_access": {
            "enabled": get_user_setting(session, current_user.id, "tailscale_enabled", settings.tailscale_enabled),
            "hostname": get_user_setting(session, current_user.id, "tailscale_hostname", settings.tailscale_hostname),
            "ssh_user": get_user_setting(session, current_user.id, "tailscale_ssh_user", settings.tailscale_ssh_user),
            "ssh_port": get_user_setting(session, current_user.id, "tailscale_ssh_port", settings.tailscale_ssh_port),
            "app_port": get_user_setting(session, current_user.id, "tailscale_app_port", settings.tailscale_app_port),
            "magic_dns": get_user_setting(session, current_user.id, "tailscale_magic_dns", settings.tailscale_magic_dns),
        },
    }


@router.post("/ai")
def update_ai_settings(
    ai_provider: str = Form(...),
    ollama_base_url: str | None = Form(None),
    ollama_model: str | None = Form(None),
    openai_base_url: str | None = Form(None),
    openai_model: str | None = Form(None),
    openai_api_key: str | None = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Update active AI provider and model parameters."""
    set_user_setting(session, current_user.id, "ai_provider", ai_provider.strip().lower())
    if ollama_base_url:
        set_user_setting(session, current_user.id, "ollama_base_url", ollama_base_url.strip())
    if ollama_model:
        set_user_setting(session, current_user.id, "ollama_model", ollama_model.strip())
    if openai_base_url:
        set_user_setting(session, current_user.id, "openai_base_url", openai_base_url.strip())
    if openai_model:
        set_user_setting(session, current_user.id, "openai_model", openai_model.strip())
    # Blank secret fields mean "keep the stored key" so decrypted credentials
    # never need to be round-tripped through rendered HTML.
    if openai_api_key and openai_api_key.strip():
        set_user_setting(session, current_user.id, "openai_api_key", openai_api_key.strip(), sensitive=True)

    logger.info("Updated AI configuration: provider=%s", ai_provider)
    return HTMLResponse(
        '<span class="text-xs text-emerald-400 font-semibold flex items-center space-x-1 animate-fade-in">'
        '<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        '<span>AI Settings Saved!</span></span>'
    )


@router.post("/remote-access")
def update_remote_access_settings(
    tailscale_enabled: bool = Form(False),
    tailscale_hostname: str = Form(""),
    tailscale_ssh_user: str = Form(""),
    tailscale_ssh_port: int = Form(22),
    tailscale_app_port: int = Form(8000),
    tailscale_magic_dns: bool = Form(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Persist validated Tailscale SSH connection preferences."""
    hostname = tailscale_hostname.strip()
    ssh_user = tailscale_ssh_user.strip()
    if not REMOTE_HOST_PATTERN.fullmatch(hostname):
        raise HTTPException(status_code=422, detail="Tailscale hostname contains unsupported characters")
    if not SSH_USER_PATTERN.fullmatch(ssh_user):
        raise HTTPException(status_code=422, detail="SSH user contains unsupported characters")
    if not 1 <= tailscale_ssh_port <= 65535 or not 1 <= tailscale_app_port <= 65535:
        raise HTTPException(status_code=422, detail="Ports must be between 1 and 65535")

    set_user_setting(session, current_user.id, "tailscale_enabled", tailscale_enabled)
    set_user_setting(session, current_user.id, "tailscale_hostname", hostname)
    set_user_setting(session, current_user.id, "tailscale_ssh_user", ssh_user)
    set_user_setting(session, current_user.id, "tailscale_ssh_port", tailscale_ssh_port)
    set_user_setting(session, current_user.id, "tailscale_app_port", tailscale_app_port)
    set_user_setting(session, current_user.id, "tailscale_magic_dns", tailscale_magic_dns)

    return HTMLResponse(
        '<span class="text-xs text-emerald-400 font-semibold">Tailscale SSH settings saved.</span>'
    )


@router.get("/tailscale/status")
async def tailscale_status() -> HTMLResponse:
    """Render a compact status badge for the local Tailscale client."""
    status_details = await get_tailscale_status()
    if not status_details["installed"]:
        return HTMLResponse(
            '<span class="text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-400 font-mono">Not installed</span>'
        )

    if not status_details["online"]:
        error = html.escape(str(status_details.get("error") or "Offline"))
        return HTMLResponse(
            f'<span class="text-xs px-2.5 py-1 rounded-full bg-amber-950 border border-amber-800 text-amber-300 font-mono" title="{error}">Offline</span>'
        )

    hostname = html.escape(str(status_details.get("hostname") or "Connected"))
    addresses = ", ".join(html.escape(address) for address in status_details.get("addresses") or [])
    detail = f"{hostname} | {addresses}" if addresses else hostname
    return HTMLResponse(
        '<div class="text-right">'
        '<span class="text-xs px-2.5 py-1 rounded-full bg-emerald-950 border border-emerald-800 text-emerald-300 font-mono">Connected</span>'
        f'<div class="text-[10px] text-slate-500 mt-1 font-mono">{detail}</div>'
        '</div>'
    )


@router.post("/test-ai")
async def test_ai_connection(
    ai_provider: str | None = Form(None),
    ollama_base_url: str | None = Form(None),
    ollama_model: str | None = Form(None),
    openai_base_url: str | None = Form(None),
    openai_model: str | None = Form(None),
    openai_api_key: str | None = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Test connectivity of the specified or configured AI provider."""
    model = ""
    provider = (ai_provider or get_user_setting(session, current_user.id, "ai_provider", "ollama")).strip().lower()

    if provider == "ollama":
        base_url = (ollama_base_url or get_app_setting("ollama_base_url", "http://localhost:11434")).strip()
        model = (ollama_model or get_app_setting("ollama_model", "llama3.1:8b")).strip()
        client = OllamaAIClient(base_url=base_url, model=model)
    elif provider in ("openai", "custom"):
        api_key = (
            openai_api_key.strip()
            if openai_api_key and openai_api_key.strip()
            else get_user_setting(session, current_user.id, "openai_api_key", "")
        )
        base_url = (openai_base_url or get_app_setting("openai_base_url", "https://api.openai.com/v1")).strip()
        model = (openai_model or get_app_setting("openai_model", "gpt-4o-mini")).strip()
        client = OpenAICompatibleClient(api_key=api_key, base_url=base_url, model=model)
    else:
        client = get_ai_client(session, current_user.id)

    details = await client.check_health_details()

    if details.get("healthy"):
        models_list = details.get("available_models", [])
        models_html = ""
        oob_models_swap = ""
        if provider == "ollama" and models_list:
            models_html = f'<div class="text-[11px] text-emerald-300 font-mono mt-1">Discovered {len(models_list)} model(s): {", ".join(models_list)}</div>'
            dropdown_inner = render_ollama_model_options_html(models_list, model)
            oob_models_swap = f'<div id="ollama-model-selector-container" hx-swap-oob="innerHTML">{dropdown_inner}</div>'

        return HTMLResponse(
            '<div class="space-y-1">'
            '<span class="text-xs px-2.5 py-1 rounded-full bg-emerald-950/80 border border-emerald-800 text-emerald-400 font-mono flex items-center space-x-1.5 w-fit shadow-sm">'
            '<span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>'
            f'<span>Connected & Ready</span></span>'
            f'{models_html}'
            '</div>'
            f'{oob_models_swap}'
        )

    error_msg = details.get("message") or details.get("error") or "Connection failed"
    return HTMLResponse(
        '<div class="space-y-1.5">'
        '<span class="text-xs px-2.5 py-1 rounded-full bg-rose-950/80 border border-rose-800 text-rose-400 font-mono flex items-center space-x-1.5 w-fit">'
        '<svg class="w-3.5 h-3.5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>'
        '<span>Connection Failed</span></span>'
        f'<div class="text-[11px] text-rose-300/90 leading-relaxed bg-rose-950/40 p-2.5 rounded-lg border border-rose-900/40 max-w-lg">{error_msg}</div>'
        '</div>'
    )


@router.post("/rules")
async def create_filter_rule(
    rule_type: str = Form(...),
    pattern: str = Form(...),
    is_regex: bool = Form(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Add a new blacklist FilterRule and re-render the settings view."""
    rule = FilterRule(
        user_id=current_user.id,
        rule_type=rule_type.strip().lower(),
        pattern=pattern.strip(),
        is_regex=is_regex,
        is_active=True,
        created_at=utc_now(),
    )
    session.add(rule)
    session.commit()
    logger.info("Created FilterRule: type=%s, pattern='%s'", rule.rule_type, rule.pattern)

    return HTMLResponse(
        headers={"HX-Redirect": "/"}
    )


@router.delete("/rules/{rule_id}")
async def delete_filter_rule(
    rule_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Delete a blacklist FilterRule."""
    rule = owned_by_id(session, FilterRule, rule_id, current_user.id)
    if rule:
        session.delete(rule)
        session.commit()
        logger.info("Deleted FilterRule id=%d", rule_id)
    return HTMLResponse(headers={"HX-Redirect": "/"})


@router.post("/upload-cv")
async def upload_cv_document(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Upload resume, extract text & structured profile, and store embeddings."""
    content = await file.read()
    parser = CVParser()
    try:
        raw_text = parser.extract_text_from_bytes(content, file.filename or "resume.pdf")
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    ai_client = get_ai_client(session, current_user.id)
    extracted_profile = await extract_profile_from_text(raw_text, ai_client)
    user_profile = save_profile_to_db(
        extracted_profile, raw_text, session, source_type="cv", user_id=current_user.id
    )

    # Embed and sync into ChromaDB
    vector_store = get_vector_store()
    await ProfileEmbedder.embed_and_store_profile(extracted_profile, vector_store, ai_client)

    logger.info("Uploaded and embedded CV for candidate '%s'", user_profile.full_name)
    return HTMLResponse(headers={"HX-Redirect": "/"})


@router.post("/scoring-weights")
def update_scoring_weights(
    weight_skills: float = Form(70.0),
    weight_title: float = Form(15.0),
    weight_location: float = Form(10.0),
    weight_experience: float = Form(5.0),
    weight_vector: float = Form(20.0),
    weight_history_skills: float = Form(10.0),
    weight_education: float = Form(5.0),
    weight_projects: float = Form(10.0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Update fine-tuned scoring weights for job match evaluation."""
    weights = {
        "weight_skills": weight_skills,
        "weight_title": weight_title,
        "weight_location": weight_location,
        "weight_experience": weight_experience,
        "weight_vector": weight_vector,
        "weight_history_skills": weight_history_skills,
        "weight_education": weight_education,
        "weight_projects": weight_projects,
    }
    for key, value in weights.items():
        set_user_setting(session, current_user.id, key, max(0.0, value))

    logger.info(
        "Updated scoring weights: skills=%s, title=%s, location=%s, exp=%s, vec=%s, history_skills=%s, education=%s, projects=%s",
        weight_skills, weight_title, weight_location, weight_experience, weight_vector, weight_history_skills, weight_education, weight_projects
    )

    return HTMLResponse(
        '<span class="text-xs text-emerald-400 font-semibold flex items-center space-x-1 animate-fade-in">'
        '<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        '<span>Scoring Weights Saved!</span></span>'
    )


@router.post("/rescore-all")
async def rescore_all_jobs_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Rescore all stored jobs in database using updated scoring weights."""
    from app.ai.evaluator import JobEvaluator
    ai_client = get_ai_client(session, current_user.id)
    count = await JobEvaluator.rescore_all_jobs(
        session=session, ai_client=ai_client, user_id=current_user.id
    )
    return HTMLResponse(
        f'<span class="text-xs text-emerald-400 font-semibold flex items-center space-x-1 animate-fade-in">'
        f'<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        f'<span>Rescored {count} Jobs Successfully!</span></span>'
    )
