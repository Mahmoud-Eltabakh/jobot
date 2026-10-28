"""Owner-scoped, short-lived cache of provider model listings plus a validator.

Invariants:
- Entries are isolated per owner, provider, endpoint and credential; the raw
  credential is never stored, only a salted, truncated digest of its handle.
- Failures are never cached, so a transient outage cannot pin a stale answer.
- Manual refresh bypasses the cache but is rate limited per owner/provider to
  protect provider quotas; the cooldown starts on any attempt, even a failed one.
- The module performs no I/O: callers supply the fetch coroutine.
"""

import asyncio
import hashlib
import secrets
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable

from app.ai.client import ModelListing

DEFAULT_TTL_SECONDS = 300.0
DEFAULT_MAX_ENTRIES = 256
DEFAULT_REFRESH_COOLDOWN_SECONDS = 5.0

CacheKey = tuple[int, str, str, str]


class RefreshCooldown(Exception):
    """A refresh arrived inside the cooldown; not a provider failure, so not an AIProviderError."""

    def __init__(self, seconds_remaining: float) -> None:
        self.seconds_remaining = seconds_remaining
        super().__init__("Refresh is cooling down.")


class ModelCatalog:
    """TTL cache with single-flight fetches and an oldest-first entry cap.

    The clock is injectable so TTL and cooldown can be tested without sleeping.
    """

    def __init__(self, ttl: float = DEFAULT_TTL_SECONDS, max_entries: int = DEFAULT_MAX_ENTRIES,
                 refresh_cooldown: float = DEFAULT_REFRESH_COOLDOWN_SECONDS,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        self._cooldown = refresh_cooldown
        self._clock = clock
        # Per-process salt: digests are meaningless outside this process and cannot be precomputed.
        self._salt = secrets.token_bytes(16)
        self._entries: OrderedDict[CacheKey, tuple[float, ModelListing]] = OrderedDict()
        self._locks: dict[CacheKey, asyncio.Lock] = {}
        self._last_refresh: dict[tuple[int, str], float] = {}

    def __repr__(self) -> str:
        return f"ModelCatalog(entries={len(self._entries)})"

    def _key(self, user_id: int, identity: tuple[str, str, str]) -> CacheKey:
        provider, endpoint, key_handle = identity
        digest = hashlib.sha256(self._salt + key_handle.encode()).hexdigest()[:16] if key_handle else ""
        return (user_id, provider, endpoint, digest)

    def _fresh(self, key: CacheKey) -> ModelListing | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, listing = entry
        if self._clock() - stored_at >= self._ttl:
            del self._entries[key]
            return None
        return listing

    def _store(self, key: CacheKey, listing: ModelListing) -> None:
        self._entries.pop(key, None)
        self._entries[key] = (self._clock(), listing)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def _check_cooldown(self, user_id: int, provider: str) -> None:
        now = self._clock()
        slot = (user_id, provider)
        last = self._last_refresh.get(slot)
        if last is not None and now - last < self._cooldown:
            raise RefreshCooldown(self._cooldown - (now - last))
        # Prune expired slots so the map stays bounded by active owner/provider pairs.
        for stale in [s for s, t in self._last_refresh.items() if now - t >= self._cooldown]:
            del self._last_refresh[stale]
        self._last_refresh[slot] = now

    async def get_or_fetch(self, user_id: int, identity: tuple[str, str, str],
                           fetch: Callable[[], Awaitable[ModelListing]],
                           refresh: bool = False) -> tuple[ModelListing, bool]:
        """Return (listing, from_cache); exceptions from fetch propagate uncached."""
        key = self._key(user_id, identity)
        if refresh:
            self._check_cooldown(user_id, identity[0])
        else:
            cached = self._fresh(key)
            if cached is not None:
                return cached, True
        lock = self._locks.setdefault(key, asyncio.Lock())
        try:
            async with lock:
                if not refresh:
                    # A concurrent caller may have filled the entry while we waited.
                    cached = self._fresh(key)
                    if cached is not None:
                        return cached, True
                listing = await fetch()
                self._store(key, listing)
                return listing, False
        finally:
            if not lock.locked() and self._locks.get(key) is lock:
                del self._locks[key]

    def peek(self, user_id: int, identity: tuple[str, str, str]) -> ModelListing | None:
        """Cache-only lookup for save-time warnings; never triggers a fetch."""
        return self._fresh(self._key(user_id, identity))

    def invalidate(self, user_id: int, provider: str | None = None) -> None:
        """Drop an owner's entries after a credential or endpoint change."""
        for key in [k for k in self._entries if k[0] == user_id and (provider is None or k[1] == provider)]:
            del self._entries[key]


def normalize_model_name(provider: str, model: str) -> str:
    """Comparison form only; callers keep the exact string the owner submitted (D-05)."""
    model = model.strip()
    if provider == "gemini":
        return model.removeprefix("models/")
    if provider == "ollama" and model and ":" not in model:
        return f"{model}:latest"
    return model


def validate_configured_model(provider: str, model: str, listing: ModelListing | None) -> str:
    """Classify as 'listed', 'not_listed' or 'unchecked'.

    A truncated listing cannot prove absence, and an unsupported, failed or
    empty listing proves nothing, so those are 'unchecked'.
    """
    if listing is None or not listing.supported or not listing.models:
        return "unchecked"
    wanted = normalize_model_name(provider, model)
    if wanted in {normalize_model_name(provider, name) for name in listing.models}:
        return "listed"
    return "unchecked" if listing.truncated else "not_listed"


_catalog: ModelCatalog | None = None


def get_model_catalog() -> ModelCatalog:
    """Process-wide singleton, lazily created."""
    global _catalog
    if _catalog is None:
        _catalog = ModelCatalog()
    return _catalog


def reset_model_catalog() -> None:
    """Drop all cached state; used by tests so cache never leaks between cases."""
    global _catalog
    _catalog = None
