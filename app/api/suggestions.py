"""Owner-scoped suggestions from feedback: blacklist rules and search terms.

Suggestions are never applied automatically. Approving creates a normal
FilterRule or SearchConfig for the caller; dismissing a rule stores it inactive
so the suggester does not propose the same pattern again.
"""

from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.ai.blacklist_suggester import BlacklistSuggester
from app.auth.dependencies import get_current_user
from app.db.database import get_session
from app.db.models import FilterRule, SearchConfig, User, UserProfile, utc_now
from app.db.ownership import get_user_profile
from app.scrapers.query_optimizer import SearchQueryOptimizer

router = APIRouter(prefix="/api/suggestions", tags=["Suggestions"])
templates = Jinja2Templates(directory="templates")

RULE_TYPES = {"title", "keyword", "company"}
SOURCES = {"linkedin", "stepstone", "google"}


async def _gather(session: Session, user: User) -> dict[str, Any]:
    rules = await BlacklistSuggester.analyze_rejections_and_suggest_rules(session=session, user_id=user.id)
    terms = SearchQueryOptimizer.get_optimized_search_terms(session, user_id=user.id)
    existing = {c.keywords.lower().strip() for c in session.exec(
        select(SearchConfig).where(SearchConfig.user_id == user.id)).all()}
    terms = [t for t in terms if t.lower() not in existing]
    profile = get_user_profile(session, user.id)
    return {"rules": rules, "terms": terms, "default_location": _first_location(profile)}


def _first_location(profile: UserProfile | None) -> str:
    import json
    try:
        locations = json.loads(profile.target_locations_json or "[]") if profile else []
    except ValueError:
        return ""
    return str(locations[0]) if locations else ""


@router.get("")
async def list_suggestions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Return pending blacklist-rule and search-term suggestions for the caller."""
    data = await _gather(session, current_user)
    return {"blacklist_rules": [r.model_dump() for r in data["rules"]], "search_terms": data["terms"]}


@router.get("/panel", response_class=HTMLResponse)
async def suggestions_panel(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the settings panel with approve/dismiss controls."""
    data = await _gather(session, current_user)
    return templates.TemplateResponse(request=request, name="components/suggestions.html", context=data)


def _add_rule(session: Session, user: User, rule_type: str, pattern: str, active: bool) -> None:
    rule_type = rule_type.strip().lower()
    pattern = pattern.strip()
    if rule_type not in RULE_TYPES or not pattern or len(pattern) > 200:
        raise HTTPException(status_code=422, detail="Invalid rule")
    dup = session.exec(select(FilterRule).where(FilterRule.user_id == user.id)).all()
    if any(r.pattern.lower().strip() == pattern.lower() and r.rule_type == rule_type for r in dup):
        return
    session.add(FilterRule(user_id=user.id, rule_type=rule_type, pattern=pattern,
                           is_active=active, created_at=utc_now()))
    session.commit()


@router.post("/blacklist/approve")
async def approve_rule(
    rule_type: str = Form(...),
    pattern: str = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Create an active FilterRule from an approved suggestion."""
    _add_rule(session, current_user, rule_type, pattern, True)
    return {"status": "approved"}


@router.post("/blacklist/dismiss")
async def dismiss_rule(
    rule_type: str = Form(...),
    pattern: str = Form(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Store the pattern as an inactive rule so it is not suggested again."""
    _add_rule(session, current_user, rule_type, pattern, False)
    return {"status": "dismissed"}


@router.post("/search-terms/approve")
async def approve_search_term(
    keywords: str = Form(...),
    location: str = Form(...),
    source: str = Form("linkedin"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Create an active SearchConfig from an approved optimizer term."""
    keywords, location, source = keywords.strip(), location.strip(), source.strip().lower()
    if not keywords or not location or source not in SOURCES or len(keywords) > 200 or len(location) > 200:
        raise HTTPException(status_code=422, detail="Invalid search configuration")
    taken = session.exec(select(SearchConfig).where(
        SearchConfig.user_id == current_user.id, SearchConfig.source == source,
        SearchConfig.location == location)).all()
    if not any(c.keywords.lower().strip() == keywords.lower() for c in taken):
        session.add(SearchConfig(user_id=current_user.id, source=source, keywords=keywords, location=location))
        session.commit()
    return {"status": "approved"}
