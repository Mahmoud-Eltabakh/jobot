"""Settings API with owner-isolated provider credentials and task routing.

Authentication is enforced at the router boundary, including legacy routes.
An owner probe reads only that account's endpoint, model, and credential.
Installation/environment API keys are never credential-presence defaults.
Connection checks are transient: they cannot save submitted credentials or
change task assignments, even when a provider reports a successful health.
Cloud model listing proves reachability, not paid generation entitlement.
Provider error bodies and exception messages are untrusted remote content.
Only normalized diagnostics may cross the HTML boundary; model options are
escaped independently because even a local Ollama host can return HTML.
Credential and task updates validate before writing and commit as one unit.
Presets are intentionally narrower: six assignments only, no migration,
connectivity checks, automatic failover, or replay of a failed queue task.
New routing controls and non-2xx HTMX swapping belong to the UI plan; this
router retains legacy selectors and emits a refresh event after successful saves.
"""

import asyncio
import html
import json
import logging
import re
import shutil
from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from app.ai.client import (
    AIProviderError, MODEL_ID_PATTERN, PROVIDER_DEFAULTS, AnthropicClient, GeminiClient,
    ModelListing, OllamaAIClient, OpenAICompatibleClient, _catalog_identity, _provider_error,
    _validated_url, get_ai_client, get_default_provider, get_embedding_client, get_provider_defaults,
)
from app.ai.model_catalog import (
    RefreshCooldown, get_model_catalog, normalize_model_name, validate_configured_model,
)
from app.ai.cv_parser import CVParser
from app.ai.embeddings import ProfileEmbedder
from app.ai.profile_extractor import extract_profile_from_text, save_profile_to_db
from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.db.database import (
    PROVIDER_SECRET_KEYS, get_app_setting, get_session, get_user_setting,
    migrate_legacy_ai_settings, set_app_setting, set_user_setting, set_user_settings,
)
from app.db.models import FilterRule, User, utc_now
from app.db.ownership import get_user_profile, owned_by_id
from app.db.vector import get_vector_store
from app.security.encryption import EncryptionError

logger = logging.getLogger("jobot.api.settings")

router = APIRouter(
    prefix="/api/settings",
    tags=["Settings"],
    dependencies=[Depends(get_current_user)],
)

REMOTE_HOST_PATTERN = re.compile(r"^[A-Za-z0-9._:-]*$")
SSH_USER_PATTERN = re.compile(r"^[A-Za-z0-9._-]*$")
MODEL_PATTERN = MODEL_ID_PATTERN  # alias: one definition lives in app.ai.client


def _validate_provider(provider: str) -> str:
    """Use a closed provider vocabulary before constructing clients or HTML IDs.

    Provider text is never interpolated into a status target until validated.
    Rejecting unknown IDs also prevents accidental fallback to the active
    stage's provider when testing a different provider's submitted credential.
    """
    provider = provider.strip().lower()
    if provider not in PROVIDER_DEFAULTS:
        raise HTTPException(422, "Unknown AI provider")
    return provider


def _validate_model(model: str) -> str:
    """Bound model identifiers; adapters still encode protocol path segments.

    Slashes and colons support gateway namespaces and local model tags.
    Query delimiters, whitespace and control characters are not identifiers;
    excluding them prevents path/query injection before adapter construction.
    """
    model = model.strip()
    if not MODEL_PATTERN.fullmatch(model):
        raise HTTPException(422, "Invalid AI model")
    return model


def _validate_endpoint(base_url: str, provider: str, model: str = "") -> str:
    """Retain local HTTP support without credential-bearing URL components.

    This is URL hygiene, not a private-network denylist: self-hosted custom
    servers are supported. Transport redirect blocking is a separate control.
    Validation failures never repeat a submitted URL that might contain a key.
    """
    try:
        return _validated_url(base_url.strip(), provider, model)
    except AIProviderError:
        raise HTTPException(422, "Invalid provider endpoint") from None


def _owner_key(session: Session, user_id: int, provider: str) -> str:
    """Read vault or matching owner legacy key, never global/environment keys.

    A legacy custom credential is not an OpenAI credential. Explicit vault
    entries win, including an explicit empty record from an older migration.
    Decryption failure is a configuration error, not permission to search for
    another key. Neither health checks nor settings JSON can repair a keyring.
    Legacy credentials remain readable until the owner's next atomic save.
    They are not copied as a side effect of testing or viewing Settings.
    """
    try:
        key = get_user_setting(session, user_id, f"provider_{provider}_key", None)
        if key is None:
            legacy_provider = get_user_setting(session, user_id, "ai_provider", "ollama")
            key = get_user_setting(session, user_id, "openai_api_key", "") if provider in ("openai", "custom") and legacy_provider == provider else ""
        if not isinstance(key, str):
            raise ValueError
        return key
    except (EncryptionError, ValueError, TypeError):
        raise HTTPException(422, "Stored provider credential is unavailable") from None


def _owner_model(session: Session, user_id: int, provider: str) -> str:
    """Legacy model names are owner-local and belong only to their provider.

    Probe selection is independent of task assignment. Testing one provider
    must not pick the model assigned to a stage using another provider.
    Factory defaults are editable hints, not verified account entitlements.
    """
    return get_provider_defaults(session, user_id, provider)["model"]


def _owner_endpoint(session: Session, user_id: int, provider: str) -> str:
    """Fixed cloud hosts cannot be replaced by legacy installation endpoints.

    Older forms allowed URLs containing credentials. Do not reflect those
    stored strings; an empty endpoint forces explicit correction before I/O.
    Invalid legacy values remain stored for explicit owner correction rather
    than being silently replaced or rewritten by a read-only settings view.
    OpenAI's historical custom endpoint field is used only for custom accounts.
    Fixed provider defaults come from the same table as the client adapters.
    """
    if provider not in ("ollama", "custom"):
        return PROVIDER_DEFAULTS[provider]["base_url"]
    url = get_provider_defaults(session, user_id, provider)["base_url"]
    try:
        return _validate_endpoint(url, provider)
    except HTTPException:
        return ""


def _provider_client(session: Session, user_id: int, provider: str, api_key: str | None = None,
                     base_url: str | None = None, model: str | None = None):
    """Build a transient probe without persisting form values.

    Submitted keys override only for this request. A saved endpoint token
    cannot follow an unsaved URL override; submitting a new key is explicit.
    All fixed cloud URLs are allowlisted before any credential can leave.
    Blank form keys deliberately use the saved owner credential, while a
    nonblank key tests an unsaved replacement without modifying the vault.
    The token-to-endpoint binding includes scheme, port and path, not merely
    hostname: a changed self-hosted path is still an explicit configuration.
    Constructing the adapter performs no generation or health request.
    """
    provider = _validate_provider(provider)
    model = _validate_model(model if model and model.strip() else _owner_model(session, user_id, provider))
    saved_url = _owner_endpoint(session, user_id, provider)
    url = _validate_endpoint(base_url if base_url and base_url.strip() else saved_url, provider, model)
    if provider not in ("ollama", "custom") and url != PROVIDER_DEFAULTS[provider]["base_url"]:
        raise HTTPException(422, "Fixed provider endpoint cannot be overridden")
    submitted_key = api_key.strip() if api_key else ""
    key = submitted_key or _owner_key(session, user_id, provider)
    if key and not submitted_key and url != saved_url.rstrip("/"):
        raise HTTPException(422, "Save the provider endpoint before using its stored credential")
    if provider != "ollama" and not key:
        raise HTTPException(422, "Provider API key required")
    if provider == "ollama":
        return OllamaAIClient(base_url=url, model=model, api_key=key)
    if provider == "anthropic":
        return AnthropicClient(api_key=key, model=model)
    if provider == "gemini":
        return GeminiClient(api_key=key, model=model)
    return OpenAICompatibleClient(api_key=key, base_url=url, model=model, provider=provider)


async def _health_details(client) -> dict[str, Any]:
    """Bound the entire non-generating check, including injected/SDK clients.

    Remote messages and error bodies are never trusted display text. Health
    categories are normalized again at the HTML boundary, even for adapters.
    Cancellation propagates rather than becoming an apparent provider error.
    The outer deadline also covers clients whose own per-read timeout could
    otherwise restart indefinitely while a server trickles response chunks.
    Adapter health dictionaries may contain unsafe legacy message fields;
    returning those dictionaries internally never authorizes rendering them.
    """
    try:
        details = await asyncio.wait_for(client.check_health_details(), timeout=5)
        if not isinstance(details, dict):
            raise AIProviderError(client.provider, client.model, "invalid_response")
        secret = client._headers.get("Authorization", "").removeprefix("Bearer ") if client.provider == "ollama" else getattr(client, "api_key", "")
        models = details.get("available_models")
        if secret and isinstance(models, list):
            details = {**details, "available_models": [model for model in models if not isinstance(model, str) or secret not in model]}
        return details
    except Exception as error:
        safe = _provider_error(client.provider, client.model, error)
        return {"healthy": False, "category": safe.category}


def _health_fragment(provider: str, model: str, details: dict[str, Any], *, legacy: bool = False,
                     models_override: list[str] | None = None, extra_html: str = "") -> HTMLResponse:
    """Only allowlisted diagnostics enter a provider-local escaped fragment.

    Model discovery is reachability evidence, not generation entitlement.
    Retain the old Ollama out-of-band selector target for legacy forms.
    A success badge never announces model availability or billing readiness.
    For failures the selected provider controls HTTP status, not remote text.
    Unknown category values collapse to unavailable and never enter markup.
    Only Ollama discovery contributes model names to the old selector.
    """
    if details.get("healthy") is True:
        models = [value for value in details.get("available_models", []) if isinstance(value, str)] if isinstance(details.get("available_models", []), list) else []
        if models_override is not None:
            models = models_override  # live listing replaces health names so exactly one datalist is emitted
        text = "Connected" if provider == "ollama" else "Reachable; credentials unverified"
        if details.get("credential_validation") == "unverified":
            text = "Reachable; credentials unverified"
        extra = ""
        if not legacy:
            options = "".join(f'<option value="{html.escape(value[:200], quote=True)}"></option>' for value in models[:100])
            extra = f'<datalist id="provider-models-{provider}" hx-swap-oob="outerHTML">{options}</datalist>'
        if legacy and provider == "ollama" and models:
            extra = ('<div id="ollama-model-selector-container" hx-swap-oob="innerHTML">'
                     + render_ollama_model_options_html(models, model) + '</div>')
        return HTMLResponse(f'<div id="provider-status-{provider}" aria-live="polite" class="text-xs text-emerald-400">{text}</div>{extra}{extra_html}')
    category = details.get("category")
    if category not in ("configuration", "authentication", "quota", "rate_limit", "timeout", "unavailable", "invalid_response", "embedding_dimension"):
        category = "unavailable"
    safe = AIProviderError(provider, model, category)
    status = 422 if category == "configuration" else 503 if provider == "ollama" else 502
    return HTMLResponse(f'<div id="provider-status-{provider}" aria-live="polite" role="alert" class="text-sm text-rose-400" style="overflow-wrap:anywhere">{html.escape(str(safe))}</div>', status_code=status)


@router.post("/test-provider")
async def test_provider_connection(
    provider: str = Form(...), api_key: str | None = Form(None),
    base_url: str | None = Form(None), model: str | None = Form(None),
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Test one submitted or owner-saved provider without saving credentials."""
    provider = _validate_provider(provider)
    try:
        client = _provider_client(session, current_user.id, provider, api_key, base_url, model)
    except HTTPException:
        return HTMLResponse(f'<div id="provider-status-{provider}" aria-live="polite" role="alert" class="text-sm text-rose-400 break-words">API key or valid endpoint/model required for {provider}.</div>', status_code=422)
    details = await _health_details(client)
    if details.get("healthy") is not True:
        return _health_fragment(client.provider, client.model, details)
    # Listing failure never fails the connection test; the model is just reported unchecked.
    try:
        listing: ModelListing | None = await _discover(current_user.id, client)
    except Exception:
        listing = None
    extra = _model_state_fragment(client.provider, client.model, listing)
    if client.provider == "ollama":
        extra += _ollama_requirements_fragment(session, current_user.id, client, details, listing)
    override = list(listing.models) if listing is not None and listing.supported else None
    return _health_fragment(client.provider, client.model, details, models_override=override, extra_html=extra)


async def _discover(user_id: int, client, refresh: bool = False) -> ModelListing:
    """Cached listing for an already owner-scoped client; RefreshCooldown propagates to the route."""
    listing, _ = await get_model_catalog().get_or_fetch(user_id, _catalog_identity(client), client.list_models, refresh=refresh)
    return listing


def _model_state_fragment(provider: str, model: str, listing: ModelListing | None) -> str:
    """Advisory model-in-list line: text plus symbol (not colour alone); always emitted so stale warnings clear.

    'listed' only means advertised by the provider, never proven usable (D-01).
    """
    state = validate_configured_model(provider, model, listing)
    safe_model = html.escape(model)
    if state == "listed":
        text, tone = "Model listed (not a guarantee it can generate)", "text-slate-300"
    elif state == "not_listed":
        sample = ", ".join(html.escape(name) for name in (listing.models[:5] if listing else ()))
        text = f"\u26a0 Model not in provider list: {safe_model}. Listed: {sample}"
        tone = "text-amber-400"
    else:
        text, tone = "Model not checked (provider list unavailable)", "text-slate-400"
    return f'<div id="model-warning-{provider}" hx-swap-oob="outerHTML" aria-live="polite" class="text-xs {tone}" style="overflow-wrap:anywhere">{text}</div>'


def required_ollama_models(session: Session, user_id: int, provider_model: str | None = None) -> list[str]:
    """Chat models the owner's configuration expects on the Ollama host (deduplicated, ordered).

    The provider default (or the model being tested) plus every task model
    whose stage is routed to Ollama. nomic-embed-text is checked separately.
    """
    required = [provider_model or _owner_model(session, user_id, "ollama")]
    routing = _routing_settings(session, user_id)
    for stage in ("scraping", "scoring", "applying"):
        if routing[f"task_{stage}_provider"] == "ollama":
            required.append(routing[f"task_{stage}_model"])
    return list(dict.fromkeys(name for name in required if isinstance(name, str) and name.strip()))


def ollama_requirements(present: Iterable[str], required: Iterable[str]) -> list[str]:
    """Required names absent from the host, comparing tag-insensitively (name == name:latest)."""
    have = {normalize_model_name("ollama", name) for name in present}
    return [name for name in required if normalize_model_name("ollama", name) not in have]


def _pull_hint(model: str) -> str:
    """Display-only hint; nothing is executed, linked or proxied, and invalid names yield no hint."""
    if not MODEL_ID_PATTERN.fullmatch(model):
        return ""
    return f"Run on the Ollama host: <code>ollama pull {html.escape(model)}</code>"


def _embedding_present(names: Iterable[str]) -> bool:
    return any(name.split(":")[0] == "nomic-embed-text" for name in names)


def _ollama_requirements_fragment(session: Session, user_id: int, client, details: dict[str, Any],
                                  listing: ModelListing | None) -> str:
    """Report missing chat models and nomic-embed-text on the owner's own Ollama host."""
    present = [name for name in details.get("available_models", []) if isinstance(name, str)] if isinstance(details.get("available_models"), list) else []
    if listing is not None and listing.supported:
        present += list(listing.models) + list(listing.embedding_models)
    missing = ollama_requirements(present, required_ollama_models(session, user_id, client.model))
    lines = [f"<p>\u26a0 Missing on this host: {html.escape(name)}. {_pull_hint(name)}</p>" for name in missing if MODEL_ID_PATTERN.fullmatch(name)]
    if not _embedding_present(present):
        lines.append(f"<p>\u26a0 Missing on this host: nomic-embed-text. {_pull_hint('nomic-embed-text')}</p>")
    body = "".join(lines) or "All required Ollama models are present."
    return f'<div id="ollama-requirements-hint" hx-swap-oob="outerHTML" aria-live="polite" class="text-xs {"text-amber-400" if lines else "text-slate-300"}">{body}</div>'


@router.post("/provider-models")
async def list_provider_models(
    provider: str = Form(...), api_key: str | None = Form(None),
    base_url: str | None = Form(None), model: str | None = Form(None),
    refresh: str | None = Form(None),
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Advisory live model list for one owner-scoped provider.

    POST keeps keys out of URLs. The client comes only from _provider_client, so
    owner key/endpoint binding rules apply; remote text never reaches the page
    except as pattern-filtered, escaped model IDs. Results are cached; refresh
    bypasses the cache but is rate limited per owner and provider.
    """
    provider = _validate_provider(provider)
    try:
        client = _provider_client(session, current_user.id, provider, api_key, base_url, model)
    except HTTPException:
        return HTMLResponse(f'<div id="provider-status-{provider}" aria-live="polite" role="alert" class="text-sm text-rose-400 break-words">API key or valid endpoint/model required for {provider}.</div>', status_code=422)
    try:
        listing = await _discover(current_user.id, client, refresh=(refresh or "").strip().lower() in ("1", "true", "on", "yes"))
    except RefreshCooldown:
        return HTMLResponse(f'<div id="provider-status-{provider}" role="status" aria-live="polite" class="text-xs text-amber-400">Wait a few seconds before refreshing again</div>', status_code=429)
    except AIProviderError as error:
        return _health_fragment(provider, client.model, {"category": error.category})
    if not listing.supported:
        return HTMLResponse(f'<div id="provider-status-{provider}" aria-live="polite" class="text-xs text-slate-400">Model discovery not available for this provider</div>')
    return HTMLResponse(_listing_fragment(provider, listing) + _model_state_fragment(provider, client.model, listing))


def _listing_fragment(provider: str, listing) -> str:
    """Status line plus one out-of-band datalist; wording says listed, never verified (D-01)."""
    count = len(listing.models)
    text = f"{count} model{'s' if count != 1 else ''} listed" + (" (list truncated)" if listing.truncated else "")
    options = "".join(f'<option value="{html.escape(value, quote=True)}"></option>' for value in listing.models)
    return (f'<div id="provider-status-{provider}" aria-live="polite" class="text-xs text-emerald-400">{html.escape(text)}</div>'
            f'<datalist id="provider-models-{provider}" hx-swap-oob="outerHTML">{options}</datalist>')


@router.post("/test-embeddings")
async def test_local_embeddings(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> HTMLResponse:
    """Explicit local model-presence check, never a cloud embedding or generation."""
    hint = ""
    try:
        client = get_embedding_client(session=session, user_id=current_user.id)
        details = await _health_details(client)
        models = details.get("available_models", [])
        ready = details.get("healthy") is True and any(isinstance(model, str) and model.split(":")[0] == "nomic-embed-text" for model in models)
        if details.get("healthy") is True and not ready:
            # Only a reachable host gets a hint; an unreachable one may well have the model.
            hint = f'<p id="embedding-hint" hx-swap-oob="outerHTML" class="text-xs text-amber-400">\u26a0 Missing on this host: nomic-embed-text. {_pull_hint("nomic-embed-text")}</p>'
    except (AIProviderError, ValueError):
        ready = False
    return HTMLResponse(f'<span id="embedding-status" aria-live="polite">{"Connected" if ready else "Unavailable"}</span>{hint}')


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
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Discover models using only the owner's Ollama endpoint and bearer token."""
    client = _provider_client(session, current_user.id, "ollama", base_url=ollama_base_url, model=current_model)
    details = await _health_details(client)
    if details.get("healthy") is not True:
        return _health_fragment("ollama", client.model, details)
    models = details.get("available_models", [])
    if not isinstance(models, list) or not all(isinstance(model, str) for model in models):
        return _health_fragment("ollama", client.model, {"category": "invalid_response"})
    return HTMLResponse(render_ollama_model_options_html(models, client.model))


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
        "ai_provider": get_default_provider(session, current_user.id),
        "ollama_base_url": _owner_endpoint(session, current_user.id, "ollama"),
        "ollama_model": _owner_model(session, current_user.id, "ollama"),
        "openai_model": _owner_model(session, current_user.id, "openai"),
        "has_openai_key": bool(_owner_key(session, current_user.id, "openai")),
        "providers": {provider: {"has_key": bool(_owner_key(session, current_user.id, provider)),
                     "base_url": _owner_endpoint(session, current_user.id, provider),
                     "model": _owner_model(session, current_user.id, provider)}
                  for provider in PROVIDER_DEFAULTS},
        **_routing_settings(session, current_user.id),
        "rules_count": len(rules),
        "has_profile": user_profile is not None,
        "concurrency": {
            "max_scrapers": int(get_user_setting(session, current_user.id, "concurrency_max_scrapers", get_app_setting("concurrency_max_scrapers", settings.concurrency_max_scrapers))),
            "max_evaluators": int(get_user_setting(session, current_user.id, "concurrency_max_evaluators", get_app_setting("concurrency_max_evaluators", settings.concurrency_max_evaluators))),
        },
        "remote_access": {
            "enabled": get_user_setting(session, current_user.id, "tailscale_enabled", settings.tailscale_enabled),
            "hostname": get_user_setting(session, current_user.id, "tailscale_hostname", settings.tailscale_hostname),
            "ssh_user": get_user_setting(session, current_user.id, "tailscale_ssh_user", settings.tailscale_ssh_user),
            "ssh_port": get_user_setting(session, current_user.id, "tailscale_ssh_port", settings.tailscale_ssh_port),
            "app_port": get_user_setting(session, current_user.id, "tailscale_app_port", settings.tailscale_app_port),
            "magic_dns": get_user_setting(session, current_user.id, "tailscale_magic_dns", settings.tailscale_magic_dns),
        },
    }


def _routing_settings(session: Session, user_id: int) -> dict[str, str]:
    """Expose non-secret routing without constructing clients or probing hosts.

    Missing task records remain derived; merely viewing Settings must not
    freeze global defaults into owner task overrides or migrate credentials.
    Only the same provider's legacy model can serve as its model default.
    A stage that explicitly changes provider receives that provider's hint,
    not an unrelated legacy OpenAI or Ollama model selected for another stage.
    Missing custom models remain visibly incomplete until the owner sets one.
    """
    legacy = _validate_provider(get_default_provider(session, user_id))
    values = {}
    for stage in ("scraping", "scoring", "applying"):
        provider = _validate_provider(get_user_setting(session, user_id, f"task_{stage}_provider", legacy))
        default = _owner_model(session, user_id, provider) if provider == legacy or provider == "ollama" else PROVIDER_DEFAULTS[provider]["model"]
        values[f"task_{stage}_provider"] = provider
        values[f"task_{stage}_model"] = get_user_setting(session, user_id, f"task_{stage}_model", default)
    return values


def _validated_ai_values(session: Session, user_id: int, form) -> dict[str, str]:
    """Validate the entire form before any migration, encryption or write.

    New task and credential fields are optional, retaining old /ai forms.
    Duplicate fields and unknown names fail closed rather than partially
    applying a misspelled routing choice. Blank secrets preserve ciphertext.
    Legacy custom fields remain custom, never becoming fixed-cloud endpoints.
    Validation reads settings but does not mutate the session. A late invalid
    task therefore cannot save an earlier credential or trigger migration.
    Provider-only stage changes use the new provider's model hint unless the
    form supplies a model explicitly; stale models are not carried across.
    Required cloud credentials are a preset prerequisite, not a restriction
    on saving partial manual configuration before credentials are available.
    """
    task_keys = {f"task_{stage}_{field}" for stage in ("scraping", "scoring", "applying") for field in ("provider", "model")}
    legacy_keys = {"ai_provider", "ollama_base_url", "ollama_model", "openai_base_url", "openai_model", "openai_api_key"}
    allowed = task_keys | legacy_keys | PROVIDER_SECRET_KEYS | {"provider_custom_url"} | {f"{provider}_model" for provider in PROVIDER_DEFAULTS}
    values = {}
    for key in form:
        if key not in allowed or len(form.getlist(key)) != 1 or not isinstance(form[key], str):
            raise HTTPException(422, "Unknown or duplicate AI setting")
        value = form[key].strip()
        if len(value) > 8192:
            raise HTTPException(422, "AI setting exceeds maximum length")
        if not value and key not in task_keys:
            continue
        if key == "ai_provider" or key.endswith("_provider"):
            value = _validate_provider(value)
        elif key.endswith("_model"):
            value = _validate_model(value)
        values[key] = value
    legacy = values.get("ai_provider", get_default_provider(session, user_id))
    for key in ("ollama_base_url", "openai_base_url", "provider_custom_url"):
        if key not in values:
            continue
        provider = "ollama" if key == "ollama_base_url" else "custom" if key == "provider_custom_url" or legacy == "custom" else "openai"
        values[key] = _validate_endpoint(values[key], provider)
        if provider == "openai" and values[key] != PROVIDER_DEFAULTS["openai"]["base_url"]:
            raise HTTPException(422, "Fixed provider endpoint cannot be overridden")
    if legacy == "custom" and "openai_base_url" in values:
        values.setdefault("provider_custom_url", values["openai_base_url"])
    if legacy in ("openai", "custom") and "openai_api_key" in values:
        values.setdefault(f"provider_{legacy}_key", values["openai_api_key"])
    for stage in ("scraping", "scoring", "applying"):
        provider_key, model_key = f"task_{stage}_provider", f"task_{stage}_model"
        if provider_key not in values and model_key not in values:
            continue
        provider = values.get(provider_key, get_user_setting(session, user_id, provider_key, legacy))
        provider = _validate_provider(provider)
        if model_key not in values:
            default = _owner_model(session, user_id, provider) if provider == legacy or provider == "ollama" else PROVIDER_DEFAULTS[provider]["model"]
            model = default if provider_key in values else get_user_setting(session, user_id, model_key, default)
            values[model_key] = _validate_model(model)
        if provider == "custom":
            _validate_endpoint(values.get("provider_custom_url", _owner_endpoint(session, user_id, provider)), provider)
    return values


def _settings_feedback(message: str, *, status_code: int = 200) -> HTMLResponse:
    """Return secret-free feedback; Plan 04 owns routing-control rendering.

    A successful save triggers an owner settings refresh without returning
    submitted credentials. Non-2xx fragments remain explicit error states.
    Messages are server-owned constants and escaped as a defense in depth.
    The refresh signal carries no submitted fields, endpoints or key material.
    """
    role = 'role="alert"' if status_code != 200 else 'aria-live="polite"'
    return HTMLResponse(f'<span id="ai-routing-feedback" {role} class="text-xs">{html.escape(message)}</span>',
                        status_code=status_code, headers={"HX-Trigger": "ai-settings-updated"} if status_code == 200 else {})


def _routing_feedback(request: Request, session: Session, user_id: int, message: str, *, status_code: int = 200,
                      warning_html: str = "") -> HTMLResponse:
    """Swap persisted routing only, keeping credential inputs outside the fragment."""
    if request.headers.get("HX-Target", "").startswith("provider-save-"):
        return HTMLResponse(f'<span {"role=alert" if status_code != 200 else "aria-live=polite"}>{html.escape(message)}</span>', status_code=status_code)
    if request.headers.get("HX-Target") != "ai-routing-controls":
        response = _settings_feedback(message, status_code=status_code)
        if warning_html:
            trigger = {"HX-Trigger": response.headers["HX-Trigger"]} if "HX-Trigger" in response.headers else {}
            return HTMLResponse(response.body.decode() + warning_html, status_code=status_code, headers=trigger)
        return response
    if status_code != 200:
        return HTMLResponse(f'<span role="alert">{html.escape(message)}</span>', status_code=status_code,
                            headers={"HX-Retarget": "#ai-routing-feedback", "HX-Reswap": "innerHTML"})
    from app.web.routes import templates
    template = templates.env.get_template("components/settings.html")
    context = template.new_context({"request": request, "provider_configs": PROVIDER_DEFAULTS,
                                    "task_assignments": _routing_settings(session, user_id), "routing_message": message})
    return HTMLResponse("".join(template.blocks["ai_routing"](context)) + warning_html)


def _invalidate_changed_providers(user_id: int, values: dict[str, str]) -> None:
    """A changed key or endpoint makes that provider's cached listing untrustworthy."""
    changed: set[str] = set()
    for key in values:
        if key.startswith("provider_") and key.endswith("_key"):
            changed.add(key.removeprefix("provider_").removesuffix("_key"))
        elif key == "provider_custom_url":
            changed.add("custom")
        elif key == "ollama_base_url":
            changed.add("ollama")
        elif key in ("openai_api_key", "openai_base_url"):
            changed.update(("openai", "custom"))
    catalog = get_model_catalog()
    for provider in changed:
        catalog.invalidate(user_id, provider)


def _save_warning_html(session: Session, user_id: int, values: dict[str, str]) -> str:
    """Non-blocking 'Not in provider list' notice from cached listings only (D-12).

    No network I/O happens here; a missing or expired cache entry, an unreadable
    credential or any client construction failure simply yields no warning.
    Persisted values are never altered. One slot element is always emitted so a
    stale warning is cleared (OOB-swapped into the Plan 04 template slot).
    """
    try:
        routing = _routing_settings(session, user_id)
    except HTTPException:
        routing = {}
    pairs = [(provider, values[f"{provider}_model"]) for provider in PROVIDER_DEFAULTS if f"{provider}_model" in values]
    pairs += [(routing[f"task_{stage}_provider"], values[f"task_{stage}_model"])
              for stage in ("scraping", "scoring", "applying") if f"task_{stage}_model" in values and f"task_{stage}_provider" in routing]
    catalog = get_model_catalog()
    warnings: list[str] = []
    for provider, model in dict.fromkeys(pairs):
        try:
            client = _provider_client(session, user_id, provider, model=model)
            state = validate_configured_model(provider, model, catalog.peek(user_id, _catalog_identity(client)))
        except Exception:
            continue
        if state == "not_listed":
            warnings.append(f"\u26a0 Not in provider list: {html.escape(model)} ({html.escape(provider)})")
    body = "<br>".join(warnings)
    return f'<span id="model-save-warning" hx-swap-oob="outerHTML" aria-live="polite" class="text-xs text-amber-400">{body}</span>'


@router.post("/ai")
@router.post("/ai/credentials")
async def update_ai_settings(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Save optional credential/task fields and legacy forms in one transaction.

    Migration observes submitted legacy configuration, but never overrides
    explicit task choices. All staged changes, including migrated secrets,
    roll back on flush/encryption/commit failure without exposing the cause.
    Credential-only forms need no legacy ai_provider field. The alias shares
    validation and encryption rather than maintaining a second write path.
    A legacy secret replacement updates its matching provider vault slot;
    an explicit new vault field in the same form retains precedence.
    """
    try:
        values = _validated_ai_values(session, current_user.id, await request.form())
    except HTTPException:
        return _routing_feedback(request, session, current_user.id, "Invalid AI settings. Check the provider, endpoint and model.", status_code=422)
    try:
        set_user_settings(session, current_user.id, values, sensitive_keys=("openai_api_key",), commit=False)
        migrate_legacy_ai_settings(session, current_user.id, commit=False)
        session.commit()
    except Exception:
        session.rollback()
        return _routing_feedback(request, session, current_user.id, "AI settings could not be saved.", status_code=500)
    _invalidate_changed_providers(current_user.id, values)
    warning = _save_warning_html(session, current_user.id, values)
    if request.headers.get("HX-Target", "").startswith("provider-save-"):
        provider = _validate_provider(request.headers["HX-Target"].removeprefix("provider-save-"))
        state = "Saved" if _owner_key(session, current_user.id, provider) else "Not configured"
        return HTMLResponse(f'<span aria-live="polite">Saved</span><span id="provider-secret-state-{provider}" data-secret-state hx-swap-oob="outerHTML" class="block text-xs text-slate-400">{state}</span>{warning}')
    return _routing_feedback(request, session, current_user.id, "AI Settings Saved!", warning_html=warning)


@router.post("/ai/preset")
def apply_ai_preset(
    request: Request,
    preset: str = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Apply exactly six assignment values; keys/endpoints never change.

    Presets are editable defaults, not measured cost or quality claims.
    Required keys are checked before writes, with no connectivity/generation
    probe, migration, automatic fallback, retry or other side effect.
    A legacy custom key cannot satisfy the OpenAI requirement even though
    older forms used openai_api_key as the name for both credentials.
    The owner's local model, rather than a global/account neighbor's model,
    is the only mutable input to local and hybrid default assignments.
    """
    if preset not in ("local", "hybrid", "cloud"):
        return _routing_feedback(request, session, current_user.id, "Unknown AI preset.", status_code=422)
    if preset in ("hybrid", "cloud") and not _owner_key(session, current_user.id, "openai").strip():
        return _routing_feedback(request, session, current_user.id, "Save an OpenAI key before applying this preset.", status_code=422)
    local_model = _owner_model(session, current_user.id, "ollama")
    if preset != "cloud":
        local_model = _validate_model(local_model)
    values = {}
    for stage in ("scraping", "scoring", "applying"):
        provider = "openai" if preset == "cloud" or preset == "hybrid" and stage == "applying" else "ollama"
        values[f"task_{stage}_provider"] = provider
        values[f"task_{stage}_model"] = "gpt-4o-mini" if provider == "openai" else local_model
    try:
        set_user_settings(session, current_user.id, values)
    except Exception:
        return _routing_feedback(request, session, current_user.id, "AI routing could not be saved.", status_code=500)
    return _routing_feedback(request, session, current_user.id, "Local routing saved. All three task assignments now use Ollama." if preset == "local" else "AI routing saved.")


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
    """Keep the old form contract while applying the same owner-safe probe rules."""
    provider = _validate_provider(ai_provider or get_default_provider(session, current_user.id))
    client = _provider_client(
        session, current_user.id, provider,
        openai_api_key if provider in ("openai", "custom") else None,
        ollama_base_url if provider == "ollama" else openai_base_url,
        ollama_model if provider == "ollama" else openai_model,
    )
    return _health_fragment(provider, client.model, await _health_details(client), legacy=True)


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

    try:
        ai_client = get_ai_client(session, current_user.id, task_type="scraping")
        extracted_profile = await extract_profile_from_text(raw_text, ai_client)
        vector_store = get_vector_store()
        embedding_client = get_embedding_client(session, current_user.id)
        await ProfileEmbedder.embed_and_store_profile(extracted_profile, vector_store, embedding_client=embedding_client, session=session, user_id=current_user.id)
    except AIProviderError as error:
        from app.web.routes import provider_failure
        return provider_failure(error)
    user_profile = save_profile_to_db(extracted_profile, raw_text, session, source_type="cv", user_id=current_user.id)

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


@router.post("/concurrency")
def update_concurrency_settings(
    concurrency_max_scrapers: int = Form(2),
    concurrency_max_evaluators: int = Form(3),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Update runtime concurrency limits for parallel scraping and AI evaluation workers."""
    max_scrapers = max(1, min(5, concurrency_max_scrapers))
    max_evaluators = max(1, min(8, concurrency_max_evaluators))

    set_user_setting(session, current_user.id, "concurrency_max_scrapers", max_scrapers)
    set_user_setting(session, current_user.id, "concurrency_max_evaluators", max_evaluators)
    set_app_setting("concurrency_max_scrapers", max_scrapers)
    set_app_setting("concurrency_max_evaluators", max_evaluators)

    logger.info(
        "Updated worker concurrency limits: max_scrapers=%d, max_evaluators=%d for user_id=%s",
        max_scrapers, max_evaluators, current_user.id,
    )

    return HTMLResponse(
        '<span class="text-xs text-emerald-400 font-semibold flex items-center space-x-1 animate-fade-in">'
        '<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        '<span>Concurrency Limits Saved!</span></span>'
    )

@router.post("/scraper")
def update_scraper_settings(
    scraper_results_wanted: int = Form(50),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Update automated scraper limits."""
    results_wanted = max(10, min(250, scraper_results_wanted))
    set_user_setting(session, current_user.id, "scraper_results_wanted", results_wanted)
    
    logger.info("Updated scraper limits: results_wanted=%d for user_id=%s", results_wanted, current_user.id)
    return HTMLResponse(
        '<span class="text-xs text-emerald-400 font-semibold flex items-center space-x-1 animate-fade-in">'
        '<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        '<span>Scraper Limits Saved!</span></span>'
    )


@router.post("/ai-scraping")
def update_ai_scraping_setting(
    use_ai_scraping: bool = Form(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Persist the per-user AI extraction toggle and return its truthful status badge."""
    set_user_setting(session, current_user.id, "use_ai_scraping", use_ai_scraping)
    label, cls = (
        ("AI extraction enabled", "bg-emerald-950 border-emerald-800 text-emerald-400")
        if use_ai_scraping else
        ("AI extraction disabled", "bg-slate-900 border-slate-700 text-slate-400")
    )
    return HTMLResponse(f'<span id="ai-scraping-badge" class="text-xs px-2.5 py-1 rounded border font-mono {cls}">{label}</span>')



@router.post("/rescore-all")
async def rescore_all_jobs_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Rescore all stored jobs in database using updated scoring weights."""
    from app.ai.evaluator import JobEvaluator
    try:
        ai_client = get_ai_client(session, current_user.id, task_type="scoring")
        count = await JobEvaluator.rescore_all_jobs(
            session=session, ai_client=ai_client, user_id=current_user.id
        )
    except AIProviderError as error:
        from app.web.routes import provider_failure
        return provider_failure(error, "/api/settings/rescore-all", "#scales-save-feedback")
    return HTMLResponse(
        f'<span class="text-xs text-emerald-400 font-semibold flex items-center space-x-1 animate-fade-in">'
        f'<svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>'
        f'<span>Rescored {count} Jobs Successfully!</span></span>'
    )
