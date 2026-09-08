"""REST API router for application settings, AI provider testing, blacklist rules, and CV upload."""

import json
import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.database import get_session, get_app_setting, set_app_setting
from app.db.models import AppSettings, FilterRule, UserProfile, utc_now
from app.ai.client import get_ai_client, OllamaAIClient, OpenAICompatibleClient
from app.ai.cv_parser import CVParser
from app.ai.profile_extractor import extract_profile_from_text, save_profile_to_db
from app.ai.embeddings import ProfileEmbedder
from app.db.vector import get_vector_store

logger = logging.getLogger("jobot.api.settings")

router = APIRouter(prefix="/api/settings", tags=["Settings"])


def render_ollama_model_options_html(models: list[str], current_model: str) -> str:
    """Generate HTML select dropdown and datalist for Ollama models."""
    if not models:
        return (
            f'<div class="relative">'
            f'<input type="text" name="ollama_model" value="{current_model}" '
            f'class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-slate-200 font-mono focus:border-emerald-500" '
            f'placeholder="e.g. llama3.1:8b, qwen2.5:7b">'
            f'<div class="text-[10px] text-amber-400 mt-1">No models detected on Ollama host. Pull a model (e.g. <code>ollama run llama3.1:8b</code>).</div>'
            f'</div>'
        )

    options_html = "".join(
        f'<option value="{m}" {"selected" if m == current_model else ""}>{m}</option>'
        for m in models
    )
    if current_model and current_model not in models:
        options_html = f'<option value="{current_model}" selected>{current_model} (Custom)</option>' + options_html

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
    ollama_base_url: Optional[str] = None,
    current_model: Optional[str] = None,
) -> Any:
    """Fetch discovered models from local or host Ollama instance."""
    base_url = (ollama_base_url or get_app_setting("ollama_base_url", "http://localhost:11434")).strip()
    active_model = (current_model or get_app_setting("ollama_model", "llama3.1:8b")).strip()
    models = await OllamaAIClient.fetch_available_models(base_url)
    return HTMLResponse(render_ollama_model_options_html(models, active_model))


@router.get("")
def get_all_settings(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Retrieve all current system settings, AI configuration, and filter rules."""
    settings = get_settings()
    rules = session.exec(select(FilterRule)).all()
    user_profile = session.exec(select(UserProfile)).first()

    return {
        "ai_provider": get_app_setting("ai_provider", settings.ai_provider),
        "ollama_base_url": get_app_setting("ollama_base_url", settings.ollama_base_url),
        "ollama_model": get_app_setting("ollama_model", settings.ollama_model),
        "openai_model": get_app_setting("openai_model", settings.openai_model),
        "has_openai_key": bool(get_app_setting("openai_api_key", settings.openai_api_key)),
        "rules_count": len(rules),
        "has_profile": user_profile is not None,
    }


@router.post("/ai")
def update_ai_settings(
    ai_provider: str = Form(...),
    ollama_base_url: Optional[str] = Form(None),
    ollama_model: Optional[str] = Form(None),
    openai_base_url: Optional[str] = Form(None),
    openai_model: Optional[str] = Form(None),
    openai_api_key: Optional[str] = Form(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Update active AI provider and model parameters."""
    set_app_setting("ai_provider", ai_provider.strip().lower())
    if ollama_base_url:
        set_app_setting("ollama_base_url", ollama_base_url.strip())
    if ollama_model:
        set_app_setting("ollama_model", ollama_model.strip())
    if openai_base_url:
        set_app_setting("openai_base_url", openai_base_url.strip())
    if openai_model:
        set_app_setting("openai_model", openai_model.strip())
    if openai_api_key is not None:
        set_app_setting("openai_api_key", openai_api_key.strip())

    logger.info("Updated AI configuration: provider=%s", ai_provider)
    return HTMLResponse(
        '<span class="text-xs text-emerald-400 font-semibold flex items-center space-x-1 animate-fade-in">'
        '<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        '<span>AI Settings Saved!</span></span>'
    )


@router.post("/test-ai")
async def test_ai_connection(
    ai_provider: Optional[str] = Form(None),
    ollama_base_url: Optional[str] = Form(None),
    ollama_model: Optional[str] = Form(None),
    openai_base_url: Optional[str] = Form(None),
    openai_model: Optional[str] = Form(None),
    openai_api_key: Optional[str] = Form(None),
) -> HTMLResponse:
    """Test connectivity of the specified or configured AI provider."""
    provider = (ai_provider or get_app_setting("ai_provider", "ollama")).strip().lower()

    if provider == "ollama":
        base_url = (ollama_base_url or get_app_setting("ollama_base_url", "http://localhost:11434")).strip()
        model = (ollama_model or get_app_setting("ollama_model", "llama3.1:8b")).strip()
        client = OllamaAIClient(base_url=base_url, model=model)
    elif provider in ("openai", "custom"):
        api_key = (openai_api_key if openai_api_key is not None else get_app_setting("openai_api_key", "")).strip()
        base_url = (openai_base_url or get_app_setting("openai_base_url", "https://api.openai.com/v1")).strip()
        model = (openai_model or get_app_setting("openai_model", "gpt-4o-mini")).strip()
        client = OpenAICompatibleClient(api_key=api_key, base_url=base_url, model=model)
    else:
        client = get_ai_client()

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
) -> HTMLResponse:
    """Add a new blacklist FilterRule and re-render the settings view."""
    rule = FilterRule(
        rule_type=rule_type.strip().lower(),
        pattern=pattern.strip(),
        is_regex=is_regex,
        is_active=True,
        created_at=utc_now(),
    )
    session.add(rule)
    session.commit()
    logger.info("Created FilterRule: type=%s, pattern='%s'", rule.rule_type, rule.pattern)

    # Return refreshed settings view
    from app.web.routes import get_settings_view
    from starlette.requests import Request
    # HTMX swap response
    return HTMLResponse(
        headers={"HX-Redirect": "/"}
    )


@router.delete("/rules/{rule_id}")
async def delete_filter_rule(
    rule_id: int,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Delete a blacklist FilterRule."""
    rule = session.get(FilterRule, rule_id)
    if rule:
        session.delete(rule)
        session.commit()
        logger.info("Deleted FilterRule id=%d", rule_id)
    return HTMLResponse(headers={"HX-Redirect": "/"})


@router.post("/upload-cv")
async def upload_cv_document(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Upload resume, extract text & structured profile, and store embeddings."""
    content = await file.read()
    parser = CVParser()
    try:
        raw_text = parser.extract_text_from_bytes(content, file.filename or "resume.pdf")
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    ai_client = get_ai_client()
    extracted_profile = await extract_profile_from_text(raw_text, ai_client)
    user_profile = save_profile_to_db(extracted_profile, raw_text, session)

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
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Update fine-tuned scoring weights for job match evaluation."""
    set_app_setting("weight_skills", max(0.0, weight_skills))
    set_app_setting("weight_title", max(0.0, weight_title))
    set_app_setting("weight_location", max(0.0, weight_location))
    set_app_setting("weight_experience", max(0.0, weight_experience))
    set_app_setting("weight_vector", max(0.0, weight_vector))

    logger.info(
        "Updated scoring weights: skills=%s, title=%s, location=%s, exp=%s, vec=%s",
        weight_skills, weight_title, weight_location, weight_experience, weight_vector
    )

    return HTMLResponse(
        '<span class="text-xs text-emerald-400 font-semibold flex items-center space-x-1 animate-fade-in">'
        '<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        '<span>Scoring Weights Saved!</span></span>'
    )


@router.post("/rescore-all")
async def rescore_all_jobs_endpoint(
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Rescore all stored jobs in database using updated scoring weights."""
    from app.ai.evaluator import JobEvaluator
    ai_client = get_ai_client()
    count = await JobEvaluator.rescore_all_jobs(session=session, ai_client=ai_client)
    return HTMLResponse(
        f'<span class="text-xs text-emerald-400 font-semibold flex items-center space-x-1 animate-fade-in">'
        f'<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        f'<span>Rescored {count} Jobs Successfully!</span></span>'
    )
