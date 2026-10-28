"""Direct AI provider adapters and account-aware client resolution.

Generation returns text; domain consumers own Pydantic schema validation.
Provider failures are explicit and never select an alternate model or service.
Account calls must retain owner identity even when no session is supplied.
Only trusted installation callers may consume installation-level credentials.
Embedding resolution is separate so generation choices cannot move vectors
between incompatible local and cloud embedding spaces.
Health probes never generate content or certify paid model entitlement.
"""

import abc
import asyncio
import hashlib
import json
import logging
import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any, TypeVar
from urllib.parse import quote, urlsplit

import httpx
import ollama
import openai
from sqlmodel import Session

from app.core.config import get_settings
from app.db.database import get_app_setting

logger = logging.getLogger("jobot.ai.client")
_T = TypeVar("_T")


async def _with_timeout(operation: Awaitable[_T], seconds: float) -> _T:
    """Apply a whole-operation deadline using the Python 3.10 async API."""
    return await asyncio.wait_for(operation, timeout=seconds)


PROVIDER_DEFAULTS = {
    "ollama": {"base_url": "http://localhost:11434", "model": "llama3.1:8b"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-sonnet-4-5"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com", "model": "gemini-2.5-flash"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile"},
    "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": "openai/gpt-4o-mini"},
    "custom": {"base_url": "", "model": ""},
}


class AIProviderError(RuntimeError):
    """Stable public diagnostics, never remote bodies, URLs, or exception messages.

    Provider/model identify the selected configuration; the public message is
    built only from an allowlisted category. Callers must not log raw causes.
    """

    def __init__(self, provider: str, model: str, category: str, status_code: int | None = None):
        self.provider = provider
        self.model = model
        self.category = category
        self.status_code = status_code
        messages = {
            "configuration": "Provider configuration is incomplete or invalid.",
            "authentication": "Provider authentication failed.",
            "quota": "Provider quota or billing limit reached.",
            "rate_limit": "Provider rate limit reached.",
            "timeout": "Provider request timed out.",
            "unavailable": "Provider is unavailable.",
            "invalid_response": "Provider returned invalid or empty content.",
            "embedding_dimension": "Embedding dimensions are incompatible.",
        }
        self.message = messages.get(category, messages["unavailable"])
        super().__init__(f"{category if category in messages else 'unavailable'}: {self.message}")


def _provider_error(provider: str, model: str, error: Exception) -> AIProviderError:
    """Classify transport/SDK failures without stringifying untrusted exceptions.

    HTTP status is useful diagnostic metadata; request objects and response
    bodies are not. SDK timeout subclasses need checking before generic
    connection errors so a deadline remains distinguishable from an outage.
    Parsing/shape errors describe invalid output, not a provider availability
    failure. Cancellation is a BaseException and bypasses this boundary.
    """
    if isinstance(error, AIProviderError):
        return error
    status = getattr(error, "status_code", None)
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
    if not isinstance(status, int):
        status = None
    if isinstance(error, (httpx.TimeoutException, openai.APITimeoutError, TimeoutError)):
        category = "timeout"
    elif status in (401, 403):
        category = "authentication"
    elif status == 402:
        category = "quota"
    elif status == 429:
        category = "rate_limit"
    elif status is not None or isinstance(error, (httpx.RequestError, openai.APIConnectionError, ConnectionError)):
        category = "unavailable"
    elif isinstance(error, (ValueError, TypeError, KeyError, IndexError, AttributeError)):
        category = "invalid_response"
    else:
        category = "unavailable"
    return AIProviderError(provider, model, category, status)


def _validated_url(base_url: str, provider: str, model: str) -> str:
    """Reject credential-bearing endpoints before an SDK can log or follow them.

    Custom and local installations may use HTTP or private hosts; this is URL
    hygiene, not a network allowlist. Redirects are disabled at transport level.
    """
    try:
        parsed = urlsplit(base_url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or "?" in base_url or "#" in base_url
                or any(character.isspace() or ord(character) < 32 for character in base_url)):
            raise ValueError
        parsed.port
    except (ValueError, TypeError, AttributeError):
        raise AIProviderError(provider, model, "configuration") from None
    return base_url.rstrip("/")


# Single definition shared with the settings API so UI validation and discovery filtering cannot drift.
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,199}$")

MAX_LISTING_PAGES = 10
MAX_LISTED_MODELS = 500
MAX_LISTING_BYTES = 1024 * 1024

# Embedding/speech/image/video families are never useful as generation targets.
_GEMINI_EXCLUDED = re.compile(r"embed|tts|image|aqa|veo", re.IGNORECASE)
_OPENAI_EXCLUDED = re.compile(r"embed|whisper|audio|tts|realtime|dall-e|gpt-image|moderation", re.IGNORECASE)


@dataclass(frozen=True)
class ModelListing:
    """Advisory provider model list: listed means advertised, never proven usable.

    supported=False marks adapters without discovery; truncated=True means a page
    or model cap stopped collection, so absence of a model proves nothing.
    """

    provider: str
    models: tuple[str, ...] = ()
    truncated: bool = False
    supported: bool = True
    embedding_models: tuple[str, ...] = ()


def _client_secret(client: Any) -> str:
    """Read the credential without calling _headers (a method on cloud adapters)."""
    headers = getattr(client, "_headers", None)
    if isinstance(headers, dict):  # Ollama keeps its bearer header as a dict
        return headers.get("Authorization", "").removeprefix("Bearer ")
    secret = getattr(client, "api_key", "")
    return secret if isinstance(secret, str) else ""


def _catalog_identity(client: Any) -> tuple[str, str, str]:
    """Stable (provider, endpoint, key digest) used by every cache path; no raw key.

    Discover, test, save and peek must all derive the identity here so that an
    entry written by one path is found by the others.
    """
    parsed = urlsplit(str(getattr(client, "base_url", "")))
    host = (parsed.hostname or "").lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = {"http": 80, "https": 443}.get(parsed.scheme.lower())
    try:
        port = parsed.port
    except ValueError:
        port = None
    netloc = host if port in (None, default_port) else f"{host}:{port}"
    endpoint = f"{parsed.scheme.lower()}://{netloc}{parsed.path.rstrip('/')}"
    secret = _client_secret(client)
    return (str(client.provider), endpoint, hashlib.sha256(secret.encode()).hexdigest() if secret else "")


def _discovery_http_client() -> httpx.AsyncClient:
    """Factory kept separate so tests can inject a MockTransport.

    Redirects are off so credentials can never follow a Location header.
    """
    return httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=5.0), follow_redirects=False)


async def _bounded_json(response: httpx.Response, provider: str) -> dict:
    """Stream at most 1 MiB; oversize, malformed or non-object JSON is invalid_response."""
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body.extend(chunk)
        if len(body) > MAX_LISTING_BYTES:
            raise AIProviderError(provider, "", "invalid_response")
    try:
        data = json.loads(bytes(body))
    except ValueError:
        raise AIProviderError(provider, "", "invalid_response") from None
    if not isinstance(data, dict):
        raise AIProviderError(provider, "", "invalid_response")
    return data


async def _get_listing_json(provider: str, url: str, headers: dict[str, str], params: dict[str, Any] | None) -> dict:
    """One bounded GET; non-2xx (including unfollowed redirects) raises HTTPStatusError."""
    async with _discovery_http_client() as http:
        async with http.stream("GET", url, headers=headers, params=params) as response:
            response.raise_for_status()
            return await _bounded_json(response, provider)


async def _collect_pages(
    provider: str,
    fetch: Callable[[dict[str, Any] | None], Awaitable[dict]],
    entries_key: str,
    next_params: Callable[[dict], dict[str, Any] | None],
) -> tuple[list[Any], bool]:
    """Walk pages until exhausted or capped; hitting a cap reports truncation, not failure."""
    entries: list[Any] = []
    params: dict[str, Any] | None = None
    for _ in range(MAX_LISTING_PAGES):
        data = await fetch(params)
        page = data.get(entries_key)
        if not isinstance(page, list):
            raise AIProviderError(provider, "", "invalid_response")
        entries.extend(page)
        params = next_params(data)
        if params is None:
            return entries, False
        if len(entries) >= MAX_LISTED_MODELS:
            return entries, True
    return entries, True


def _collect_model_ids(ids: Iterable[Any], secret: str = "") -> tuple[tuple[str, ...], bool]:
    """Pattern-filter, dedupe, cap and case-insensitively sort remote IDs.

    Anything failing MODEL_ID_PATTERN (markup, whitespace, control characters,
    over-long values) is dropped; IDs that echo the credential are dropped too.
    """
    seen: dict[str, None] = {}
    for value in ids:
        if isinstance(value, str) and MODEL_ID_PATTERN.fullmatch(value) and not (secret and secret in value):
            seen.setdefault(value, None)
    truncated = len(seen) > MAX_LISTED_MODELS
    ordered = sorted(seen, key=lambda item: (item.casefold(), item))[:MAX_LISTED_MODELS]
    return tuple(ordered), truncated


def _validated_content(provider: str, model: str, content: Any, json_mode: bool) -> str:
    """JSON mode checks syntax only; domain consumers still validate their schemas.

    Whitespace-only output is a failure even in plain-text mode. Valid JSON
    arrays remain supported for existing consumers; adapters do not silently
    unwrap envelopes, repair fenced JSON, or manufacture missing fields.
    The original text is retained for the downstream domain parser.
    """
    if not isinstance(content, str) or not content.strip():
        raise AIProviderError(provider, model, "invalid_response")
    if json_mode:
        try:
            json.loads(content)
        except (ValueError, TypeError):
            raise AIProviderError(provider, model, "invalid_response") from None
    return content


class BaseAIClient(abc.ABC):
    """Abstract base interface for AI providers (Ollama, OpenAI, Groq, etc.).

    Injection of existing clients remains supported by domain services.
    JSON mode is a generation preference, not a domain-schema guarantee.
    Adapters without embeddings implement an explicit unsupported operation
    rather than failing abstract-class construction or returning fake vectors.
    """

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = True,
    ) -> str:
        """Generate text / JSON response from LLM."""
        raise NotImplementedError

    @abc.abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate dense vector embedding representation for text."""
        raise NotImplementedError

    @abc.abstractmethod
    async def check_health(self) -> bool:
        """Check if AI provider service is reachable and responsive."""
        raise NotImplementedError

    async def check_health_details(self) -> dict[str, Any]:
        """Check connectivity and return detailed diagnostics and available models."""
        is_ok = await self.check_health()
        return {"healthy": is_ok, "message": "Connected" if is_ok else "Connection failed"}

    async def list_models(self) -> ModelListing:
        """Adapters without discovery report unsupported rather than an empty catalog."""
        return ModelListing(str(getattr(self, "provider", "unknown")), supported=False)


class _NativeCloudClient(BaseAIClient):
    """Direct REST boundary shared by native adapters; no retries or redirects.

    Keys travel only in headers. Short-lived HTTP clients close on cancellation;
    cancellation itself is intentionally not translated into provider failure.
    """

    provider: str
    base_url: str

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        """Bound connection and generation waits; never propagate raw HTTP context.

        The whole-operation deadline also bounds slow responses that continue
        delivering chunks within HTTPX's per-read timeout. Health wraps this
        with its shorter deadline. Redirects cannot forward provider headers
        to a different host, and there is no hidden transport retry budget.
        Even a successful HTTP status must contain a usable JSON object.
        """
        if not self.api_key:
            raise AIProviderError(self.provider, self.model, "configuration") from None
        try:
            async def perform_request() -> dict:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0), follow_redirects=False) as client:
                    response = await client.request(method, self.base_url + path, headers=self._headers(), json=payload)
                    response.raise_for_status()
                    result = response.json()
                    if not isinstance(result, dict) or "error" in result:
                        raise AIProviderError(self.provider, self.model, "invalid_response")
                    return result

            return await asyncio.wait_for(perform_request(), timeout=120)
        except Exception as error:
            raise _provider_error(self.provider, self.model, error) from None

    async def embed(self, text: str) -> list[float]:
        """Native cloud embeddings are intentionally outside the local vector contract."""
        raise NotImplementedError("Use get_embedding_client for local embeddings")

    async def check_health(self) -> bool:
        return (await self.check_health_details())["healthy"]

    async def check_health_details(self) -> dict[str, Any]:
        """A model listing checks reachability, not billing or generation entitlement."""
        try:
            data = await _with_timeout(
                self._request("GET", "/v1/models" if self.provider == "anthropic" else "/v1beta/models"),
                5,
            )
            if not isinstance(data.get("data" if self.provider == "anthropic" else "models"), list):
                raise AIProviderError(self.provider, self.model, "invalid_response")
            return {"healthy": True, "provider": self.provider, "configured_model": self.model,
                    "model_capability": "unverified", "credential_validation": "unverified",
                    "message": "Provider model listing reachable; generation capability unverified."}
        except Exception as error:
            safe = _provider_error(self.provider, self.model, error)
            return {"healthy": False, "provider": self.provider, "category": safe.category,
                    "status_code": safe.status_code, "error": str(safe), "message": safe.message}


class AnthropicClient(_NativeCloudClient):
    """Claude Messages REST adapter, excluding hidden reasoning and truncated output."""

    provider = "anthropic"
    base_url = "https://api.anthropic.com"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5") -> None:
        super().__init__(api_key, model)

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

    async def list_models(self) -> ModelListing:
        """All listed Claude models, paged by after_id while has_more is true."""
        if not self.api_key:
            raise AIProviderError(self.provider, self.model, "configuration")
        headers = self._headers()

        async def fetch(params: dict[str, Any] | None) -> dict:
            query = {"limit": 100, **(params or {})}
            return await _get_listing_json(self.provider, self.base_url + "/v1/models", headers, query)

        def next_params(data: dict) -> dict[str, Any] | None:
            if data.get("has_more") is not True:
                if not isinstance(data.get("has_more"), bool):
                    raise AIProviderError(self.provider, self.model, "invalid_response")
                return None
            last_id = data.get("last_id")
            if not isinstance(last_id, str) or not last_id.strip():
                raise AIProviderError(self.provider, self.model, "invalid_response")
            return {"after_id": last_id}

        try:
            entries, truncated = await _with_timeout(
                _collect_pages(self.provider, fetch, "data", next_params), 10,
            )
            models, capped = _collect_model_ids((e.get("id") for e in entries if isinstance(e, dict)), self.api_key)
            return ModelListing(self.provider, models, truncated or capped)
        except Exception as error:
            raise _provider_error(self.provider, self.model, error) from None

    async def generate(self, prompt: str, system_prompt: str | None = None, json_mode: bool = True) -> str:
        """Request JSON explicitly without pretending that it enforces a domain schema.

        Messages uses a top-level system field, unlike OpenAI's system role.
        JSON-only guidance is appended to system instructions, not user data.
        Only text blocks are public output; reasoning/tool blocks are excluded.
        Truncated or refused responses remain failures even if their partial
        text happens to parse as JSON.
        """
        payload: dict[str, Any] = {"model": self.model, "max_tokens": 4096, "temperature": 0.2,
                                   "messages": [{"role": "user", "content": prompt}]}
        system = system_prompt or ""
        if json_mode:
            system += "\nReturn only valid JSON, with no markdown fences."
        if system:
            payload["system"] = system
        try:
            result = await self._request("POST", "/v1/messages", payload)
            if result.get("stop_reason") not in (None, "end_turn", "stop_sequence"):
                raise AIProviderError(self.provider, self.model, "invalid_response")
            content = "".join(block["text"] for block in result["content"] if block["type"] == "text")
            return _validated_content(self.provider, self.model, content, json_mode)
        except Exception as error:
            raise _provider_error(self.provider, self.model, error) from None


class GeminiClient(_NativeCloudClient):
    """Gemini REST adapter; keys stay in headers and thought parts stay private."""

    provider = "gemini"
    base_url = "https://generativelanguage.googleapis.com"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        super().__init__(api_key, model)

    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self.api_key}

    async def list_models(self) -> ModelListing:
        """Generation-capable Gemini models; the key stays in the header, never the URL."""
        if not self.api_key:
            raise AIProviderError(self.provider, self.model, "configuration")
        headers = self._headers()

        async def fetch(params: dict[str, Any] | None) -> dict:
            query = {"pageSize": 100, **(params or {})}
            return await _get_listing_json(self.provider, self.base_url + "/v1beta/models", headers, query)

        def next_params(data: dict) -> dict[str, Any] | None:
            if "nextPageToken" not in data or data["nextPageToken"] is None or data["nextPageToken"] == "":
                return None
            token = data["nextPageToken"]
            if not isinstance(token, str) or not token.strip():
                raise AIProviderError(self.provider, self.model, "invalid_response")
            return {"pageToken": token}

        try:
            entries, truncated = await _with_timeout(
                _collect_pages(self.provider, fetch, "models", next_params), 10,
            )
            ids = []
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                    continue
                methods = entry.get("supportedGenerationMethods")
                model_id = entry["name"].removeprefix("models/")
                if isinstance(methods, list) and "generateContent" in methods and not _GEMINI_EXCLUDED.search(model_id):
                    ids.append(model_id)
            models, capped = _collect_model_ids(ids, self.api_key)
            return ModelListing(self.provider, models, truncated or capped)
        except Exception as error:
            raise _provider_error(self.provider, self.model, error) from None

    async def generate(self, prompt: str, system_prompt: str | None = None, json_mode: bool = True) -> str:
        """Reject blocked/truncated candidates rather than substituting synthetic text.

        REST field names deliberately use Gemini's camelCase protocol.
        JSON MIME mode is omitted for free-form application material.
        Model IDs form one escaped URL component and keys never enter URLs.
        The first candidate is the selected output; another candidate is not
        a fallback for a blocked response. Thought parts are never returned.
        """
        payload: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                                   "generationConfig": {"temperature": 0.2}}
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"
        try:
            model_path = quote(self.model.removeprefix("models/"), safe="")
            result = await self._request("POST", f"/v1beta/models/{model_path}:generateContent", payload)
            if result.get("promptFeedback", {}).get("blockReason"):
                raise AIProviderError(self.provider, self.model, "invalid_response")
            candidate = result["candidates"][0]
            if candidate.get("finishReason") not in (None, "STOP"):
                raise AIProviderError(self.provider, self.model, "invalid_response")
            content = "".join(part["text"] for part in candidate["content"]["parts"]
                              if "text" in part and not part.get("thought"))
            return _validated_content(self.provider, self.model, content, json_mode)
        except Exception as error:
            raise _provider_error(self.provider, self.model, error) from None


class OllamaAIClient(BaseAIClient):
    """Local Ollama client utilizing ollama-python async client.

    Optional bearer authentication belongs to this endpoint's owner, not to
    any configured cloud provider. Direct legacy callers can still select
    an embedding model; application code uses the fixed embedding resolver.
    Network failures never produce a zero vector or synthetic generation.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        embed_model: str = "nomic-embed-text",
        *,
        api_key: str = "",
    ) -> None:
        self.provider = "ollama"
        self.base_url = _validated_url(base_url, self.provider, model)
        self.model = model
        self.embed_model = embed_model
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.client = ollama.AsyncClient(host=self.base_url, headers=self._headers,
                                         timeout=httpx.Timeout(120.0, connect=5.0), follow_redirects=False)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = True,
    ) -> str:
        """Generate response from local Ollama LLM."""
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }
        if json_mode:
            kwargs["format"] = "json"

        try:
            response = await _with_timeout(self.client.chat(**kwargs), 120)
            if response.get("done_reason") in ("length", "max_tokens"):
                raise AIProviderError(self.provider, self.model, "invalid_response")
            return _validated_content(self.provider, self.model, response["message"]["content"], json_mode)
        except Exception as error:
            raise _provider_error(self.provider, self.model, error) from None

    async def embed(self, text: str) -> list[float]:
        """Generate vector embedding via Ollama embedding API.

        Empty vectors are invalid provider output. Collection dimension and
        finite-value checks belong to vector consumers, which know the stored
        collection contract; this adapter never resets an existing collection.
        """
        try:
            res = await _with_timeout(self.client.embeddings(model=self.embed_model, prompt=text), 120)
            embedding = list(res["embedding"])
            if not embedding:
                raise AIProviderError(self.provider, self.embed_model, "invalid_response")
            return embedding
        except Exception as error:
            raise _provider_error(self.provider, self.embed_model, error) from None

    async def check_health(self) -> bool:
        """Verify Ollama server connectivity."""
        return (await self.check_health_details())["healthy"]

    async def list_models(self) -> ModelListing:
        """Chat models from /api/tags; embedding families are reported separately.

        Unlike fetch_available_models this distinguishes an unreachable host
        (typed error) from a host with no models (empty listing).
        """
        secret = _client_secret(self)
        try:
            data = await _with_timeout(
                _get_listing_json(self.provider, f"{self.base_url}/api/tags", self._headers, None), 10,
            )
            entries = data.get("models")
            if not isinstance(entries, list):
                raise AIProviderError(self.provider, self.model, "invalid_response")
            chat, embedding = [], []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name") or entry.get("model")
                details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
                family = str(details.get("family") or "").lower()
                # Family heuristic avoids an N+1 /api/show call per model (D-13).
                is_embedding = family in ("bert", "nomic-bert") or (isinstance(name, str) and "embed" in name.lower())
                (embedding if is_embedding else chat).append(name)
            models, capped = _collect_model_ids(chat, secret)
            embeddings, embedding_capped = _collect_model_ids(embedding, secret)
            return ModelListing(self.provider, models, capped or embedding_capped, embedding_models=embeddings)
        except Exception as error:
            raise _provider_error(self.provider, self.model, error) from None

    @classmethod
    async def fetch_available_models(cls, base_url: str = "http://localhost:11434") -> list[str]:
        """Fetch list of model names from Ollama /api/tags endpoint."""
        try:
            url = _validated_url(base_url, "ollama", "")
            async def fetch() -> list[str]:
                async with httpx.AsyncClient(timeout=4.0, follow_redirects=False) as http_client:
                    res = await http_client.get(f"{url}/api/tags")
                    res.raise_for_status()
                    data = res.json()
                    return [model["name"] if model.get("name") else model["model"]
                            for model in data.get("models", []) if isinstance(model, dict)
                            and isinstance(model.get("name") or model.get("model"), str)]
            return await _with_timeout(fetch(), 5)
        except Exception:
            pass
        return []

    async def check_health_details(self) -> dict[str, Any]:
        """Verify Ollama server connectivity and retrieve discovered models."""
        try:
            async def fetch() -> list[str]:
                async with httpx.AsyncClient(timeout=4.0, follow_redirects=False) as http_client:
                    res = await http_client.get(f"{self.base_url}/api/tags", headers=self._headers)
                    res.raise_for_status()
                    data = res.json()
                    return [model.get("name") or model.get("model") for model in data["models"]
                            if isinstance(model, dict) and isinstance(model.get("name") or model.get("model"), str)]
            models = await _with_timeout(fetch(), 5)
            return {"healthy": True, "configured_model": self.model, "available_models": models,
                    "model_present": self.model in models, "message": "Connected to Ollama."}
        except Exception as error:
            safe = _provider_error(self.provider, self.model, error)
            return {"healthy": False, "category": safe.category, "status_code": safe.status_code,
                    "error": str(safe), "message": safe.message}


class OpenAICompatibleClient(BaseAIClient):
    """Client for OpenAI, Groq, DeepSeek, or any OpenAI-compatible custom base URL.

    Existing positional key, endpoint, model, and embedding arguments retain
    their meaning. The optional provider ID selects defaults and safe error
    metadata, not failover behavior. Custom providers must supply their own
    endpoint and model; provider hints do not prove live account entitlement.
    SDK retries and redirect following are explicitly disabled.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        embed_model: str = "text-embedding-3-small",
        *,
        provider: str = "openai",
    ) -> None:
        if provider not in ("openai", "groq", "deepseek", "openrouter", "custom"):
            raise ValueError("Unknown OpenAI-compatible provider")
        self.provider = provider
        self.api_key = api_key
        self.model = model if model is not None else PROVIDER_DEFAULTS[provider]["model"]
        self.base_url = _validated_url(base_url if base_url is not None else PROVIDER_DEFAULTS[provider]["base_url"], provider, self.model)
        if not api_key or not self.model.strip():
            raise AIProviderError(provider, self.model, "configuration") from None
        self.embed_model = embed_model
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=httpx.Timeout(120.0, connect=5.0),
            max_retries=0,
            http_client=openai.DefaultAsyncHttpxClient(follow_redirects=False),
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = True,
    ) -> str:
        """Generate response from OpenAI-compatible provider.

        json_object is the existing SDK contract; domain consumers that need
        an array must request a suitable envelope themselves. Refusals and
        non-stop finish reasons are failures, never apparently successful
        empty strings or partial application material.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await _with_timeout(self.client.chat.completions.create(**kwargs), 120)
            choice = response.choices[0]
            if choice.finish_reason not in (None, "stop") or getattr(choice.message, "refusal", None):
                raise AIProviderError(self.provider, self.model, "invalid_response")
            return _validated_content(self.provider, self.model, choice.message.content, json_mode)
        except Exception as error:
            raise _provider_error(self.provider, self.model, error) from None

    async def embed(self, text: str) -> list[float]:
        """Generate embedding vector using OpenAI Embeddings API.

        Retained for direct client compatibility, not application RAG routing.
        The separate local resolver is the application embedding boundary.
        Provider failures retain the embedding model in their safe metadata.
        """
        try:
            response = await _with_timeout(self.client.embeddings.create(model=self.embed_model, input=text), 120)
            embedding = response.data[0].embedding
            if not embedding:
                raise AIProviderError(self.provider, self.embed_model, "invalid_response")
            return embedding
        except Exception as error:
            raise _provider_error(self.provider, self.embed_model, error) from None

    async def list_models(self) -> ModelListing:
        """Direct bounded GET <base>/models; the SDK would drop OpenRouter's architecture field."""
        try:
            data = await _with_timeout(
                _get_listing_json(self.provider, f"{self.base_url}/models",
                                  {"Authorization": f"Bearer {self.api_key}"}, None),
                10,
            )
            entries = data.get("data")
            if not isinstance(entries, list):
                raise AIProviderError(self.provider, self.model, "invalid_response")
            ids = []
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                    continue
                if _OPENAI_EXCLUDED.search(entry["id"]):
                    continue
                if self.provider == "openrouter":
                    architecture = entry.get("architecture")
                    modalities = architecture.get("output_modalities") if isinstance(architecture, dict) else None
                    if not isinstance(modalities, list) or "text" not in modalities:
                        continue
                ids.append(entry["id"])
            models, capped = _collect_model_ids(ids, self.api_key)
            return ModelListing(self.provider, models, capped)
        except Exception as error:
            raise _provider_error(self.provider, self.model, error) from None

    async def check_health(self) -> bool:
        """Check API key validity by querying models list."""
        return (await self.check_health_details())["healthy"]

    async def check_health_details(self) -> dict[str, Any]:
        """Check Cloud AI connectivity with details.

        Gateways may expose public model lists even for unusable credentials.
        Report reachability only, with entitlement and credential validation
        explicitly unverified. A malformed success body is not healthy.
        No paid generation probe or model substitution is permitted here.
        """
        if not self.api_key:
            return {
                "healthy": False,
                "error": "API Key is required.",
                "message": "API key is missing. Please enter your API key.",
            }
        try:
            listing = await _with_timeout(self.client.models.list(), 5)
            if not isinstance(listing.data, list):
                raise AIProviderError(self.provider, self.model, "invalid_response")
            return {
                "healthy": True,
                "provider": self.provider,
                "configured_model": self.model,
                "model_capability": "unverified",
                "credential_validation": "unverified",
                "message": "Provider model listing reachable; generation capability unverified.",
            }
        except Exception as error:
            safe = _provider_error(self.provider, self.model, error)
            return {"healthy": False, "provider": self.provider, "category": safe.category,
                    "status_code": safe.status_code, "error": str(safe), "message": safe.message}


class MockAIClient(BaseAIClient):
    """In-memory mock AI client for unit tests and offline development."""

    def __init__(self, default_response: str | None = None) -> None:
        self.default_response = default_response or json.dumps({
            "fit_score": 85,
            "fit_summary": "Strong match with candidate background in Python and FastAPI.",
            "pros": ["5+ years Python experience", "Strong backend architecture skills"],
            "cons": ["Limited frontend expertise"],
            "missing_skills": ["GraphQL"],
            "recommendation": "Strong Match"
        })

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = True,
    ) -> str:
        return self.default_response

    async def embed(self, text: str) -> list[float]:
        # Return deterministic 384-dim pseudo-embedding
        return [float((hash(text + str(i)) % 1000) / 1000.0) for i in range(384)]

    async def check_health(self) -> bool:
        return True

    async def check_health_details(self) -> dict[str, Any]:
        return {
            "healthy": True,
            "base_url": "mock://in-memory",
            "message": "Mock client is active.",
        }


def _configured(session: Session | None, user_id: int | None, key: str, default: Any = None) -> Any:
    """Read exactly one provenance: account-owned or trusted installation settings.

    Never put a global credential lookup in an account lookup's default argument:
    Python evaluates that argument even when the owner already has a value.
    """
    if user_id is not None:
        from app.db.database import get_user_setting
        return get_user_setting(session, user_id, key, default)
    return get_app_setting(key, default)


def get_default_provider(session: Session | None, user_id: int | None) -> str:
    """Resolve non-secret owner legacy selection, then installation defaults.

    This fallback does not establish ownership of a legacy credential.
    Secret readers must independently require the owner's matching provider.
    """
    return _configured(session, user_id, "ai_provider", get_app_setting("ai_provider", get_settings().ai_provider))


def get_provider_defaults(session: Session | None, user_id: int | None, provider: str) -> dict[str, str]:
    """Share effective non-secret configuration with forms and transient probes.

    Installation local hosts/models are safe defaults for accounts; secrets
    never pass through this resolver. Legacy custom endpoints remain owned.
    """
    settings = get_settings()
    defaults = PROVIDER_DEFAULTS[provider]
    model = defaults["model"]
    endpoint = defaults["base_url"]
    legacy = get_default_provider(session, user_id)
    model_key = f"{provider}_model"
    if provider == "ollama":
        model = get_app_setting("ollama_model", settings.ollama_model)
        endpoint = _configured(session, user_id, "ollama_base_url", get_app_setting("ollama_base_url", settings.ollama_base_url))
    elif provider == "openai" and provider == legacy:
        model = get_app_setting("openai_model", settings.openai_model)
    elif provider == "custom":
        if legacy == "custom":
            model = _configured(session, user_id, "openai_model", model)
        legacy_url = _configured(session, user_id, "openai_base_url", "") if legacy == "custom" else ""
        endpoint = _configured(session, user_id, "provider_custom_url", legacy_url)
    return {"base_url": endpoint, "model": _configured(session, user_id, model_key, model)}


def get_embedding_client(session: Session | None = None, user_id: int | None = None) -> OllamaAIClient:
    """Resolve local vectors independently of every generation assignment.

    The collection contract is nomic-embed-text, never a cloud embedding model.
    A user ID alone is still an account call: open and close a read-only session,
    not an invitation to borrow installation credentials.
    """
    if user_id is not None and session is None:
        from app.db.database import engine
        with Session(engine) as owner_session:
            return get_embedding_client(owner_session, user_id)
    host = get_provider_defaults(session, user_id, "ollama")["base_url"]
    key = _configured(session, user_id, "provider_ollama_key", "")
    return OllamaAIClient(base_url=host, embed_model="nomic-embed-text", api_key=key)


def get_ai_client(
    session: Session | None = None,
    user_id: int | None = None,
    *,
    task_type: str = "scoring",
) -> BaseAIClient:
    """Resolve a stage while preserving get_ai_client(session, user_id).

    Precedence is task assignment, same-owner legacy configuration, non-secret
    installation defaults. Credentials are different: authenticated calls read
    only that owner's vault or the matching legacy OpenAI/custom configuration.
    No lookup writes settings, switches providers on failure, or caches a session.
    """
    if task_type not in ("scraping", "scoring", "applying", "embeddings"):
        raise ValueError("Unknown AI task type")
    if task_type == "embeddings":
        return get_embedding_client(session, user_id)
    if user_id is not None and session is None:
        from app.db.database import engine
        with Session(engine) as owner_session:
            return get_ai_client(owner_session, user_id, task_type=task_type)

    settings = get_settings()
    legacy_provider = get_default_provider(session, user_id)
    provider = _configured(session, user_id, f"task_{task_type}_provider", legacy_provider)
    if not isinstance(provider, str) or provider not in PROVIDER_DEFAULTS:
        raise ValueError("Unknown AI provider")
    defaults = get_provider_defaults(session, user_id, provider)

    # Legacy model/endpoint settings belong to their provider, not to whichever
    # provider a newly assigned task happens to select.
    model_default = defaults["model"] if provider == legacy_provider or provider == "ollama" else PROVIDER_DEFAULTS[provider]["model"]
    model = _configured(session, user_id, f"task_{task_type}_model", model_default)
    if not isinstance(model, str) or not model.strip():
        raise AIProviderError(provider, "", "configuration") from None

    if provider == "openai" and provider == legacy_provider:
        legacy_endpoint = _configured(session, user_id, "openai_base_url", defaults["base_url"])
        canonical_endpoint = PROVIDER_DEFAULTS["openai"]["base_url"]
        if (not isinstance(legacy_endpoint, str)
                or legacy_endpoint.rstrip("/") != canonical_endpoint.rstrip("/")):
            raise AIProviderError(provider, model, "configuration") from None

    key = _configured(session, user_id, f"provider_{provider}_key", "")
    credential_provider = _configured(session, user_id, "ai_provider", legacy_provider if user_id is None else None)
    if not key and provider in ("openai", "custom") and provider == credential_provider:
        # Environment keys are allowed only for a trusted non-account caller.
        key = _configured(session, user_id, "openai_api_key", settings.openai_api_key or "" if user_id is None else "")
    if provider == "ollama":
        return OllamaAIClient(base_url=defaults["base_url"], model=model, api_key=key)
    if not isinstance(key, str) or not key.strip():
        raise AIProviderError(provider, model, "configuration") from None
    if provider == "anthropic":
        return AnthropicClient(api_key=key, model=model)
    if provider == "gemini":
        return GeminiClient(api_key=key, model=model)

    base_url = defaults["base_url"]
    return OpenAICompatibleClient(api_key=key, base_url=base_url, model=model, provider=provider)
