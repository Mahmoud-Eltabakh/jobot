"""Pluggable multi-provider AI client abstraction supporting Local Ollama and Cloud APIs."""

import abc
import json
import logging
from typing import Any, Optional
import httpx
import ollama
import openai
from sqlmodel import Session

from app.core.config import get_settings
from app.db.database import get_app_setting

logger = logging.getLogger("jobot.ai.client")


class BaseAIClient(abc.ABC):
    """Abstract base interface for AI providers (Ollama, OpenAI, Groq, etc.)."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
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


class OllamaAIClient(BaseAIClient):
    """Local Ollama client utilizing ollama-python async client."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
        embed_model: str = "nomic-embed-text",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = embed_model
        self.client = ollama.AsyncClient(host=self.base_url)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
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

        logger.debug("Dispatching generation to Ollama model '%s'", self.model)
        response = await self.client.chat(**kwargs)
        return response["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        """Generate vector embedding via Ollama embedding API."""
        try:
            res = await self.client.embeddings(model=self.embed_model, prompt=text)
            return list(res["embedding"])
        except Exception as err:
            logger.warning("Ollama embeddings failed for model '%s': %s", self.embed_model, err)
            # Return zero vector fallback or raise
            raise

    async def check_health(self) -> bool:
        """Verify Ollama server connectivity."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as http_client:
                res = await http_client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    @classmethod
    async def fetch_available_models(cls, base_url: str = "http://localhost:11434") -> list[str]:
        """Fetch list of model names from Ollama /api/tags endpoint."""
        url = base_url.rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=4.0) as http_client:
                res = await http_client.get(f"{url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    raw_models = data.get("models", [])
                    models = [m.get("name") or m.get("model") for m in raw_models if isinstance(m, dict)]
                    return [m for m in models if m]
        except Exception as err:
            logger.debug("Failed fetching Ollama models from %s: %s", url, err)
        return []

    async def check_health_details(self) -> dict[str, Any]:
        """Verify Ollama server connectivity and retrieve discovered models."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as http_client:
                res = await http_client.get(f"{self.base_url}/api/tags")
                if res.status_code == 200:
                    data = res.json()
                    raw_models = data.get("models", [])
                    models = [m.get("name") or m.get("model") for m in raw_models if isinstance(m, dict)]
                    return {
                        "healthy": True,
                        "base_url": self.base_url,
                        "configured_model": self.model,
                        "available_models": models,
                        "model_present": self.model in models,
                        "message": f"Connected to {self.base_url}.",
                    }
                return {
                    "healthy": False,
                    "base_url": self.base_url,
                    "error": f"HTTP {res.status_code}: {res.text[:120]}",
                    "message": f"Ollama returned HTTP status {res.status_code}.",
                }
        except Exception as err:
            hint = ""
            if "localhost" in self.base_url or "127.0.0.1" in self.base_url:
                hint = " (If Jobot runs in Docker, use 'http://host.docker.internal:11434')"
            return {
                "healthy": False,
                "base_url": self.base_url,
                "error": str(err),
                "message": f"Cannot reach {self.base_url}: {str(err)}.{hint}",
            }


class OpenAICompatibleClient(BaseAIClient):
    """Client for OpenAI, Groq, DeepSeek, or any OpenAI-compatible custom base URL."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        embed_model: str = "text-embedding-3-small",
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = embed_model
        self.client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        json_mode: bool = True,
    ) -> str:
        """Generate response from OpenAI-compatible provider."""
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

        logger.debug("Dispatching generation to OpenAI-compatible model '%s'", self.model)
        response = await self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return content or ""

    async def embed(self, text: str) -> list[float]:
        """Generate embedding vector using OpenAI Embeddings API."""
        response = await self.client.embeddings.create(
            model=self.embed_model,
            input=text,
        )
        return response.data[0].embedding

    async def check_health(self) -> bool:
        """Check API key validity by querying models list."""
        if not self.api_key:
            return False
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False

    async def check_health_details(self) -> dict[str, Any]:
        """Check Cloud AI connectivity with details."""
        if not self.api_key:
            return {
                "healthy": False,
                "base_url": self.base_url,
                "error": "API Key is required.",
                "message": "API key is missing. Please enter your API key.",
            }
        try:
            await self.client.models.list()
            return {
                "healthy": True,
                "base_url": self.base_url,
                "configured_model": self.model,
                "message": f"Connected to {self.base_url} with model '{self.model}'.",
            }
        except Exception as err:
            return {
                "healthy": False,
                "base_url": self.base_url,
                "error": str(err),
                "message": f"Cloud AI connection error: {str(err)}",
            }


class MockAIClient(BaseAIClient):
    """In-memory mock AI client for unit tests and offline development."""

    def __init__(self, default_response: Optional[str] = None) -> None:
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
        system_prompt: Optional[str] = None,
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


def get_ai_client(session: Optional[Session] = None) -> BaseAIClient:
    """Resolve and return active AI client from database settings or environment."""
    settings = get_settings()

    provider = get_app_setting("ai_provider", default=settings.ai_provider)

    if provider == "ollama":
        base_url = get_app_setting("ollama_base_url", default=settings.ollama_base_url)
        model = get_app_setting("ollama_model", default=settings.ollama_model)
        embed_model = get_app_setting("ollama_embed_model", default=settings.ollama_embed_model)
        return OllamaAIClient(base_url=base_url, model=model, embed_model=embed_model)

    elif provider in ("openai", "custom"):
        api_key = get_app_setting("openai_api_key", default=settings.openai_api_key or "")
        base_url = get_app_setting("openai_base_url", default=settings.openai_base_url)
        model = get_app_setting("openai_model", default=settings.openai_model)
        return OpenAICompatibleClient(api_key=api_key, base_url=base_url, model=model)

    return OllamaAIClient()
