# Jobot — Static Code Analysis Report

**Date:** 2026-09-08  
**Analyzer:** Ruff (v0.8+) + Manual Code Review  
**Codebase:** `f:\Workspace\Jobot`  
**Python Version Target:** 3.10+  
**Total Files Analyzed:** 49 (app/ + tests/)

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Issues Found (app/ + tests/) | **644** |
| Issues in `app/` only | **590** |
| Auto-fixable (app/ + tests/) | **410** (64%) |
| Critical Security Issues | **0** |
| High Priority Issues | **7** |
| Medium Priority Issues | **15** |
| Low Priority / Style | **622** |

> [!NOTE]
> The vast majority (256/644 = 40%) of issues are `UP045` — a purely cosmetic Python 3.10 type-hint migration (`Optional[X]` to `X | None`). No critical security vulnerabilities were found via static analysis.

---

## Issue Breakdown by Rule

| Rule | Count | Category | Fixable | Description |
|------|-------|----------|---------|-------------|
| `UP045` | 256 | Style | Yes | `Optional[X]` → `X | None` (PEP 604) |
| `B008` | 118 | Bug Risk | No | Function call in default argument |
| `BLE001` | 72 | Robustness | No | Blind `except Exception as e:` |
| `I001` | 56 | Style | Yes | Unsorted / unformatted imports |
| `F401` | 53 | Cleanliness | Yes | Unused imports |
| `S110` | 24 | Security | No | `try/except/pass` (silent failures) |
| `FURB188` | 15 | Style | Yes | Slice to remove prefix/suffix |
| `RUF012` | 7 | Bug Risk | No | Mutable class-level default |
| `FURB167` | 6 | Style | Yes | `re.IGNORECASE` flag alias |
| `UP035` | 5 | Style | Yes | Deprecated import (`typing` → `collections.abc`) |
| `SIM114` | 5 | Style | Yes | `if` with identical arms |
| `RUF010` | 4 | Style | Yes | Explicit f-string type conversion |
| `G201` | 3 | Logging | No | `logger.error(..., exc_info=True)` |
| `RUF022` | 3 | Style | Yes | Unsorted `__all__` |
| `F841` | 3 | Cleanliness | No | Assigned but unused variable |
| `RUF046` | 2 | Style | No | Unnecessary `int()` cast |
| `RUF059` | 2 | Bug Risk | No | Unused unpacked variable |
| `DTZ005` | 1 | Bug Risk | No | `datetime.now()` without tzinfo |
| `B017` | 1 | Testing | No | `pytest.raises(Exception)` too broad |
| `SIM102` | 1 | Style | Yes | Collapsible nested `if` |
| `F541` | 1 | Bug Risk | Yes | f-string with no placeholders |
| `UP011` | 1 | Style | Yes | `@lru_cache()` → `@lru_cache` |
| `UP007` | 1 | Style | Yes | `Union[X, Y]` → `X | Y` |
| `UP012` | 1 | Style | Yes | Unnecessary `encode("utf-8")` |
| `RUF019` | 1 | Style | Yes | Unnecessary key check before dict access |

---

## Detailed Findings by Priority

### High Priority

#### `B008` — Function Call in Default Argument (118 occurrences)

**Risk:** Medium-High. FastAPI's `Depends()` is intentionally used in default arguments, which is the correct FastAPI pattern. However, non-FastAPI occurrences can cause shared mutable state bugs.

**Files affected:** Primarily across all `app/api/*.py` route files.

```python
# Example — CORRECT in FastAPI context:
def get_jobs(session: Session = Depends(get_session)):  # OK
    ...

# Example — POTENTIALLY PROBLEMATIC (non-FastAPI):
def __init__(self, items: list = []):  # Bug: mutable default
    ...
```

**Recommendation:** Suppress `B008` for FastAPI `Depends()` patterns with `# noqa: B008`. Audit remaining occurrences in non-API code.

---

#### `BLE001` — Blind Exception Handling (72 occurrences)

**Risk:** Medium-High. Masking exceptions silently can hide bugs and make debugging production issues difficult.

**Key locations:**
- [app/scrapers/jobspy_scraper.py:52](file:///f:/Workspace/Jobot/app/scrapers/jobspy_scraper.py#L52) — broad `except Exception` swallows scraper errors
- [app/scrapers/linkedin_auth.py:88](file:///f:/Workspace/Jobot/app/scrapers/linkedin_auth.py#L88) — broad `except Exception` in Playwright automation
- [app/ai/client.py:89](file:///f:/Workspace/Jobot/app/ai/client.py#L89) — broad `except Exception` in embedding calls
- [app/security/encryption.py:91](file:///f:/Workspace/Jobot/app/security/encryption.py#L91) — catches `Exception` in encryption

**Recommendation:** Replace broad `except Exception` with specific exception types.

---

#### `S110` — Try/Except/Pass (24 occurrences)

**Risk:** Medium. Silent failures are a significant operational risk in scraper and AI pipelines.

**Key locations:**
- [app/db/database.py:121](file:///f:/Workspace/Jobot/app/db/database.py#L121) — column migration silently swallows errors
- Various scraper data-parsing loops

```python
# Current problematic pattern:
except Exception as e:
    logger.debug("Column migration for %s skipped: %s", table_name, e)

# Better pattern:
except OperationalError as e:
    logger.warning("Column %s already exists in %s: %s", col, table_name, e)
```

---

### Medium Priority

#### `RUF012` — Mutable Class-Level Default (7 occurrences)

**Risk:** Medium. Shared mutable class attributes between instances can cause hard-to-trace data corruption bugs.

```python
# Problematic:
class ScrapedJob:
    tags: list[str] = []  # shared across all instances!

# Fixed:
class ScrapedJob:
    tags: list[str] = field(default_factory=list)
```

#### `DTZ005` — `datetime.now()` Without Timezone (1 occurrence)

**Risk:** Medium. Timezone-naive datetimes mixed with timezone-aware datetimes cause comparison errors and subtle time bugs.

```python
# Found pattern:
datetime.now()  # Naive — dangerous

# Correct pattern (already used in utc_now()):
datetime.now(timezone.utc)  # Aware
```

---

### Low Priority / Style

#### `UP045` — `Optional[X]` Annotations (256 occurrences)

The entire codebase uses `Optional[X]` syntax from `typing` module. Python 3.10+ prefers `X | None`.

```python
# Current:
from typing import Optional
def foo(x: Optional[str]) -> None: ...

# Modern (Python 3.10+):
def foo(x: str | None) -> None: ...
```

**Recommendation:** Auto-fix with `ruff check --fix`. Low priority since both forms are functionally equivalent.

#### `I001` — Import Sorting (56 occurrences)

Standard `isort` ordering not followed. Auto-fixable.

#### `F401` — Unused Imports (53 occurrences)

Mostly in test files. Auto-fixable.

---

## Code Quality Observations (Manual Review)

### Strengths

1. **Strong Authentication Layer** — scrypt password hashing with proper salting, session tokens via `secrets.token_urlsafe(32)`, `hmac.compare_digest` for timing-safe comparison.
2. **Data Isolation** — `owned_by_id()` consistently used across API routes. Ownership boundary checks before every database access.
3. **Encryption at Rest** — Fernet AES-128 encryption for sensitive profile fields with scope-bound key derivation (`_get_fernet_key` with `user_id` scope).
4. **Proper CORS Configuration** — CORS restricted to `localhost` origins; session cookies use `httponly=True`, `samesite="lax"`.
5. **Testing Coverage** — 99 test cases covering auth, encryption, AI evaluation, scraping, task queues, and database operations.
6. **Background Worker Architecture** — SQLite-backed persistent task queue with atomic `UPDATE`-based claiming prevents race conditions.
7. **Input Validation** — Regex patterns validate Tailscale hostnames and SSH usernames before persistence.

### Issues Found in Manual Review

#### 1. Settings API HTML Injection Risk ([app/api/settings.py:117](file:///f:/Workspace/Jobot/app/api/settings.py#L117))

```python
# Line 117 — model names injected directly into HTML without escaping:
f'<option value="{m}" {"selected" if m == current_model else ""}>{m}</option>'
```

Model names from Ollama's `/api/tags` could contain `<script>` or HTML characters if an attacker controls the Ollama server. The `m` variable is not HTML-escaped.

**Fix:** Apply `html.escape(m)` to all model names before HTML injection.

#### 2. LinkedIn Raw Text Leak in AI Prompt ([app/ai/linkedin_analyzer.py](file:///f:/Workspace/Jobot/app/ai/linkedin_analyzer.py))

The raw LinkedIn profile text (which may include personal data) is passed directly to the AI client. If using an external cloud provider (OpenAI), this data leaves the user's machine. This is a privacy concern.

**Recommendation:** Add a user warning when using cloud AI with LinkedIn data.

#### 3. No Rate Limiting on Auth Endpoints ([app/api/auth.py](file:///f:/Workspace/Jobot/app/api/auth.py))

The `/api/auth/login` and `/api/auth/register` endpoints have no rate limiting, making brute-force attacks possible.

**Recommendation:** Add `slowapi` or FastAPI middleware for rate limiting.

#### 4. Email Validation is Weak ([app/api/auth.py:47](file:///f:/Workspace/Jobot/app/api/auth.py#L47))

```python
if not email or "@" not in email:  # Too simple
```

`RegisterRequest` uses `email: str` not `email: EmailStr` (Pydantic's EmailStr validates RFC 5322 properly).

**Fix:** Use `email: EmailStr` in `RegisterRequest`.

#### 5. LinkedIn Session Cookie Returned in API Response ([app/scrapers/linkedin_auth.py:110](file:///f:/Workspace/Jobot/app/scrapers/linkedin_auth.py#L110))

The `li_at` session cookie value is returned in the API response body as `session_cookie`. This is sensitive and gets stored in browser history and potentially logs.

**Fix:** Return only a boolean `session_captured: true` rather than the raw cookie value.

#### 6. Global Singleton AI Client ([app/queue/worker.py:154](file:///f:/Workspace/Jobot/app/queue/worker.py#L154))

```python
client = self.ai_client or get_ai_client()  # No session, no user_id
```

The fallback `get_ai_client()` without a session reads global settings, ignoring per-user AI configuration.

#### 7. Uncapped JSON Payload in ScrapeTask

```python
payload_json: str = Field(default="{}")
```

No size limit on `payload_json`. Malicious users could enqueue tasks with very large payloads.

**Fix:** Add payload size validation in `TaskQueue.enqueue()`.

---

## Auto-Fix Summary

Running `ruff check --fix app/ tests/` would automatically fix **410 of 644** issues (64%):

```bash
# To apply automatic fixes:
.venv/Scripts/python.exe -m ruff check app/ tests/ --fix
```

Remaining **234 issues** require manual remediation (BLE001, B008, S110, RUF012, etc.).

---

## Recommendations Priority Matrix

| Priority | Action | Effort |
|----------|--------|--------|
| P0 — Critical | None found | — |
| P1 — High | Escape HTML in Ollama model name rendering | 1h |
| P1 — High | Add auth endpoint rate limiting | 2h |
| P1 — High | Fix weak email validation → use `EmailStr` | 30m |
| P2 — Medium | Replace blind exceptions with specific types | 4h |
| P2 — Medium | Don't return raw `li_at` cookie in API response | 1h |
| P2 — Medium | Fix global AI client in worker (pass user context) | 2h |
| P2 — Medium | Add payload size cap in TaskQueue.enqueue() | 1h |
| P3 — Low | Run `ruff --fix` to auto-fix 410 style issues | 15m |
| P3 — Low | Fix `Optional[X]` → `X | None` across codebase | 15m (auto) |
