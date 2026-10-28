"""Tests for the owner-scoped model catalog cache and configured-model validator."""

import asyncio

import pytest

from app.ai.client import AIProviderError, ModelListing
from app.ai.model_catalog import (
    ModelCatalog, RefreshCooldown, get_model_catalog, reset_model_catalog, validate_configured_model,
)


class Clock:
    """Manual monotonic clock so TTL/cooldown tests never sleep."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Fetcher:
    """Counts calls and returns a distinct listing per call."""

    def __init__(self, error: Exception | None = None, delay: float = 0.0) -> None:
        self.calls = 0
        self.error = error
        self.delay = delay

    async def __call__(self) -> ModelListing:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return ModelListing("gemini", (f"model-{self.calls}",))


IDENTITY = ("gemini", "https://generativelanguage.googleapis.com", "handle-a")


@pytest.mark.asyncio
async def test_second_identical_call_is_served_from_cache() -> None:
    """Tracer: one provider fetch for repeated identical lookups."""
    catalog, fetch = ModelCatalog(), Fetcher()
    first, cached_first = await catalog.get_or_fetch(1, IDENTITY, fetch)
    second, cached_second = await catalog.get_or_fetch(1, IDENTITY, fetch)
    assert fetch.calls == 1 and first is second
    assert (cached_first, cached_second) == (False, True)


def test_singleton_accessor_and_reset() -> None:
    reset_model_catalog()
    assert get_model_catalog() is get_model_catalog()
    first = get_model_catalog()
    reset_model_catalog()
    assert get_model_catalog() is not first


@pytest.mark.parametrize("provider, model, models, expected", [
    ("gemini", "models/gemini-2.5-flash", ("gemini-2.5-flash",), "listed"),
    ("gemini", "gemini-2.5-flash", ("models/gemini-2.5-flash",), "listed"),
    ("ollama", "nomic-embed-text", ("nomic-embed-text:latest",), "listed"),
    ("ollama", "nomic-embed-text:latest", ("nomic-embed-text",), "listed"),
    ("ollama", "llama3.1", ("llama3.1:8b",), "not_listed"),
    ("openai", "gpt-9", ("gpt-4o",), "not_listed"),
])
def test_validate_configured_model_normalizes_for_comparison(provider, model, models, expected) -> None:
    assert validate_configured_model(provider, model, ModelListing(provider, models)) == expected


def test_validate_is_unchecked_when_listing_proves_nothing() -> None:
    assert validate_configured_model("openai", "x", None) == "unchecked"
    assert validate_configured_model("openai", "x", ModelListing("openai", supported=False)) == "unchecked"
    assert validate_configured_model("openai", "x", ModelListing("openai", ())) == "unchecked"
    truncated = ModelListing("openai", ("a",), truncated=True)
    assert validate_configured_model("openai", "x", truncated) == "unchecked"
    assert validate_configured_model("openai", "a", truncated) == "listed"


@pytest.mark.asyncio
async def test_ttl_expiry_boundary() -> None:
    """299 s is a hit; 300 s refetches."""
    clock, fetch = Clock(), Fetcher()
    catalog = ModelCatalog(clock=clock)
    await catalog.get_or_fetch(1, IDENTITY, fetch)
    clock.now += 299
    assert (await catalog.get_or_fetch(1, IDENTITY, fetch))[1] is True
    clock.now += 1
    assert (await catalog.get_or_fetch(1, IDENTITY, fetch))[1] is False
    assert fetch.calls == 2


@pytest.mark.asyncio
async def test_failures_propagate_and_are_never_cached() -> None:
    catalog = ModelCatalog()
    failing = Fetcher(error=AIProviderError("gemini", "", "unavailable"))
    for _ in range(2):
        with pytest.raises(AIProviderError):
            await catalog.get_or_fetch(1, IDENTITY, failing)
    assert failing.calls == 2 and catalog.peek(1, IDENTITY) is None
    assert (await catalog.get_or_fetch(1, IDENTITY, Fetcher()))[1] is False


@pytest.mark.asyncio
async def test_entry_cap_evicts_oldest_first() -> None:
    catalog, fetch = ModelCatalog(max_entries=3), Fetcher()
    for index in range(4):
        await catalog.get_or_fetch(1, ("gemini", f"https://host{index}", "k"), fetch)
    assert catalog.peek(1, ("gemini", "https://host0", "k")) is None
    assert catalog.peek(1, ("gemini", "https://host3", "k")) is not None


@pytest.mark.asyncio
async def test_concurrent_identical_calls_fetch_once_without_cross_key_blocking() -> None:
    catalog, slow, other = ModelCatalog(), Fetcher(delay=0.05), Fetcher()
    other_identity = ("openai", "https://api.openai.com/v1", "k")
    results = await asyncio.gather(*(catalog.get_or_fetch(1, IDENTITY, slow) for _ in range(5)),
                                   catalog.get_or_fetch(1, other_identity, other))
    assert slow.calls == 1 and other.calls == 1
    assert sum(1 for _, from_cache in results[:5] if not from_cache) == 1


@pytest.mark.asyncio
async def test_cancelled_fetch_releases_lock_and_caches_nothing() -> None:
    catalog = ModelCatalog()
    task = asyncio.create_task(catalog.get_or_fetch(1, IDENTITY, Fetcher(delay=10)))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert catalog.peek(1, IDENTITY) is None
    assert (await asyncio.wait_for(catalog.get_or_fetch(1, IDENTITY, Fetcher()), 1))[1] is False


@pytest.mark.asyncio
async def test_peek_never_fetches_and_invalidate_scopes_by_owner_and_provider() -> None:
    catalog, fetch = ModelCatalog(), Fetcher()
    openai = ("openai", "https://api.openai.com/v1", "k")
    assert catalog.peek(1, IDENTITY) is None and fetch.calls == 0
    for owner, identity in ((1, IDENTITY), (1, openai), (2, IDENTITY)):
        await catalog.get_or_fetch(owner, identity, fetch)
    catalog.invalidate(1, "gemini")
    assert catalog.peek(1, IDENTITY) is None
    assert catalog.peek(1, openai) is not None and catalog.peek(2, IDENTITY) is not None
    catalog.invalidate(1)
    assert catalog.peek(1, openai) is None and catalog.peek(2, IDENTITY) is not None


@pytest.mark.asyncio
async def test_refresh_bypasses_cache_then_enforces_cooldown() -> None:
    clock, fetch = Clock(), Fetcher()
    catalog = ModelCatalog(clock=clock)
    await catalog.get_or_fetch(1, IDENTITY, fetch)
    _, cached = await catalog.get_or_fetch(1, IDENTITY, fetch, refresh=True)
    assert cached is False and fetch.calls == 2
    clock.now += 2
    with pytest.raises(RefreshCooldown) as raised:
        await catalog.get_or_fetch(1, IDENTITY, fetch, refresh=True)
    assert 2.9 < raised.value.seconds_remaining < 3.1 and fetch.calls == 2
    clock.now += 3
    await catalog.get_or_fetch(1, IDENTITY, fetch, refresh=True)
    assert fetch.calls == 3


@pytest.mark.asyncio
async def test_failed_refresh_still_starts_cooldown() -> None:
    catalog = ModelCatalog(clock=Clock())
    with pytest.raises(AIProviderError):
        await catalog.get_or_fetch(1, IDENTITY, Fetcher(error=AIProviderError("gemini", "", "timeout")), refresh=True)
    with pytest.raises(RefreshCooldown):
        await catalog.get_or_fetch(1, IDENTITY, Fetcher(), refresh=True)


@pytest.mark.asyncio
async def test_cache_isolated_by_owner_key_and_endpoint() -> None:
    catalog, fetch = ModelCatalog(), Fetcher()
    variants = [(1, IDENTITY), (2, IDENTITY), (1, ("gemini", IDENTITY[1], "handle-b")),
                (1, ("gemini", "https://other.example", "handle-a"))]
    for owner, identity in variants:
        assert (await catalog.get_or_fetch(owner, identity, fetch))[1] is False
    assert fetch.calls == 4


@pytest.mark.asyncio
async def test_cooldown_is_per_owner_and_provider() -> None:
    catalog, fetch = ModelCatalog(clock=Clock()), Fetcher()
    await catalog.get_or_fetch(1, IDENTITY, fetch, refresh=True)
    await catalog.get_or_fetch(2, IDENTITY, fetch, refresh=True)
    await catalog.get_or_fetch(1, ("openai", "https://api.openai.com/v1", "k"), fetch, refresh=True)
    assert fetch.calls == 3


@pytest.mark.asyncio
async def test_sentinel_key_never_appears_in_repr_str_or_keys() -> None:
    sentinel = "sk-sentinel-secret-9999"
    catalog = ModelCatalog()
    await catalog.get_or_fetch(1, ("gemini", "https://h", sentinel), Fetcher())
    assert sentinel not in repr(catalog) and sentinel not in str(catalog)
    assert sentinel not in repr(list(catalog._entries)) and sentinel not in repr(catalog._entries)
    assert all(len(key[3]) == 16 for key in catalog._entries)
