"""LinkedIn profile scraper, AI analyzer, and profile synchronizer."""

import json
import logging
import re
from typing import Any, Optional
from playwright.async_api import async_playwright
from sqlmodel import Session, select

from app.ai.client import BaseAIClient, get_ai_client
from app.ai.embeddings import ProfileEmbedder
from app.ai.profile_extractor import ExtractedProfile, save_profile_to_db
from app.db.models import UserProfile, utc_now
from app.db.vector import get_vector_store

logger = logging.getLogger("jobot.ai.linkedin_analyzer")

LINKEDIN_ANALYSIS_SYSTEM_PROMPT = """You are an expert LinkedIn profile analyst and career architect.
Analyze the extracted LinkedIn profile data and return a structured candidate profile JSON.
Fields required:
1. full_name: string
2. headline: string (current professional headline)
3. summary: string (rich 2-3 sentence executive summary)
4. skills: list of technical & domain skills
5. active_search_skills: list of the top 5-8 primary skills to use in job searches
6. experience_years: float (estimated total years of professional experience)
7. target_titles: list of 3-5 relevant target job titles
8. target_locations: list of preferred locations or remote preference
9. experience_history: list of dicts with keys: title, company, duration, description
10. education: list of dicts with keys: school, degree, field_of_study, year
"""


def extract_public_id_from_url(url: str) -> str:
    """Extract public LinkedIn username / ID from profile URL."""
    clean_url = url.split("?")[0].rstrip("/")
    parts = [p for p in clean_url.split("/") if p]
    if "in" in parts:
        idx = parts.index("in")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return parts[-1] if parts else ""


class LinkedInProfileAnalyzer:
    """Scrapes, parses, and synchronizes candidate LinkedIn profiles using li_at session cookie and linkedin-api Voyager REST API."""

    @classmethod
    def fetch_profile_via_linkedin_api(
        cls,
        linkedin_url: str,
        session_cookie: str,
    ) -> Optional[ExtractedProfile]:
        """
        Fetch structured candidate profile using Tom Quirk's official `linkedin-api` (Voyager REST API).
        """
        try:
            from linkedin_api import Linkedin

            public_id = extract_public_id_from_url(linkedin_url)
            if not public_id:
                return None

            cookie_val = session_cookie.strip()
            api = Linkedin("", "", authenticate=False, cookies={"li_at": cookie_val})

            profile_data = api.get_profile(public_id)
            if not profile_data or not isinstance(profile_data, dict):
                return None

            first_name = profile_data.get("firstName") or ""
            last_name = profile_data.get("lastName") or ""
            full_name = f"{first_name} {last_name}".strip() or ""

            headline = profile_data.get("headline") or ""
            summary = profile_data.get("summary") or ""

            # Extract skills
            raw_skills = profile_data.get("skills") or []
            skills: list[str] = []
            for s in raw_skills:
                if isinstance(s, dict) and "name" in s:
                    skills.append(s["name"])
                elif isinstance(s, str):
                    skills.append(s)

            # Extract experience
            raw_exp = profile_data.get("experience") or []
            exp_history: list[dict[str, Any]] = []
            total_exp_years = 0.0

            for exp in raw_exp:
                if isinstance(exp, dict):
                    title = exp.get("title") or ""
                    company = exp.get("companyName") or ""
                    desc = exp.get("description") or ""
                    time_period = exp.get("timePeriod") or {}
                    dur_str = ""
                    if isinstance(time_period, dict):
                        start = time_period.get("startDate") or {}
                        end = time_period.get("endDate") or {}
                        s_year = start.get("year")
                        e_year = end.get("year", "Present")
                        if s_year:
                            dur_str = f"{s_year} - {e_year}"
                            import datetime
                            e_yr_num = datetime.datetime.now().year if e_year == "Present" else (int(e_year) if str(e_year).isdigit() else s_year)
                            total_exp_years += max(0.0, float(int(e_yr_num) - int(s_year)))

                    exp_history.append({
                        "title": title,
                        "company": company,
                        "duration": dur_str,
                        "description": desc,
                    })

            # Extract education
            raw_edu = profile_data.get("education") or []
            education: list[dict[str, str]] = []
            for edu in raw_edu:
                if isinstance(edu, dict):
                    school = edu.get("schoolName") or ""
                    degree = edu.get("degreeName") or ""
                    field = edu.get("fieldOfStudy") or ""
                    education.append({
                        "school": school,
                        "degree": degree,
                        "field_of_study": field,
                    })

            target_titles = [headline] if headline else []
            if exp_history and exp_history[0].get("title"):
                target_titles.append(exp_history[0]["title"])

            location_name = profile_data.get("locationName") or ""
            target_locations = [location_name] if location_name else []

            extracted = ExtractedProfile(
                full_name=full_name,
                headline=headline,
                summary=summary,
                skills=skills,
                active_search_skills=skills[:8],
                experience_years=round(total_exp_years, 1),
                target_titles=list(dict.fromkeys(target_titles)),
                target_locations=target_locations,
                experience_history=exp_history,
                education=education,
                linkedin_url=linkedin_url,
            )

            logger.info("Successfully extracted structured LinkedIn profile for '%s' via linkedin-api Voyager REST API", full_name)
            return extracted

        except Exception as err:
            logger.warning("linkedin-api Voyager REST extraction failed (%s), falling back to Playwright DOM scraper", err)
            return None

    @classmethod
    async def fetch_profile_via_joeyism_scraper(
        cls,
        linkedin_url: str,
        session_cookie: str,
        headless: bool = True,
    ) -> Optional[ExtractedProfile]:
        """
        Fetch structured candidate profile using Joeyism's `linkedin_scraper` (Playwright-based).
        """
        if not linkedin_url or "linkedin.com" not in linkedin_url:
            return None

        if not session_cookie or not session_cookie.strip():
            return None

        try:
            from linkedin_scraper import BrowserManager, PersonScraper

            cookie_val = session_cookie.strip()

            async with BrowserManager(
                headless=headless,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
            ) as browser:
                await browser.page.context.add_cookies([
                    {
                        "name": "li_at",
                        "value": cookie_val,
                        "domain": ".linkedin.com",
                        "path": "/",
                    },
                    {
                        "name": "JSESSIONID",
                        "value": "ajax:1234567890123456789",
                        "domain": ".linkedin.com",
                        "path": "/",
                    },
                ])

                scraper = PersonScraper(browser.page)
                person = await scraper.scrape(linkedin_url)

                if not person:
                    return None

                full_name = getattr(person, "name", "") or ""
                headline = getattr(person, "headline", "") or ""
                summary = getattr(person, "about", "") or ""
                location = getattr(person, "location", "") or ""

                if not full_name and not headline:
                    return None

                # Extract skills
                raw_skills = getattr(person, "skills", []) or []
                skills: list[str] = []
                for s in raw_skills:
                    if hasattr(s, "name"):
                        skills.append(s.name)
                    elif isinstance(s, dict) and "name" in s:
                        skills.append(s["name"])
                    elif isinstance(s, str):
                        skills.append(s)

                # Extract experiences
                raw_exp = getattr(person, "experiences", []) or []
                exp_history: list[dict[str, Any]] = []
                total_exp_years = 0.0

                for exp in raw_exp:
                    title = getattr(exp, "title", "") or (exp.get("title", "") if isinstance(exp, dict) else "")
                    company = getattr(exp, "company", "") or (exp.get("company", "") if isinstance(exp, dict) else "")
                    duration = getattr(exp, "duration", "") or (exp.get("duration", "") if isinstance(exp, dict) else "")
                    description = getattr(exp, "description", "") or (exp.get("description", "") if isinstance(exp, dict) else "")

                    if duration:
                        yrs_match = re.search(r"(\d+)\s*yr", duration, re.I)
                        if yrs_match:
                            total_exp_years += float(yrs_match.group(1))

                    exp_history.append({
                        "title": title,
                        "company": company,
                        "duration": duration,
                        "description": description,
                    })

                # Extract educations
                raw_edu = getattr(person, "educations", []) or []
                education: list[dict[str, str]] = []
                for edu in raw_edu:
                    school = getattr(edu, "institution", "") or (edu.get("institution", "") if isinstance(edu, dict) else "")
                    degree = getattr(edu, "degree", "") or (edu.get("degree", "") if isinstance(edu, dict) else "")
                    field = getattr(edu, "field_of_study", "") or (edu.get("field_of_study", "") if isinstance(edu, dict) else "")
                    education.append({
                        "school": school,
                        "degree": degree,
                        "field_of_study": field,
                    })

                target_titles = [headline] if headline else []
                if exp_history and exp_history[0].get("title"):
                    target_titles.append(exp_history[0]["title"])

                extracted = ExtractedProfile(
                    full_name=full_name,
                    headline=headline,
                    summary=summary,
                    skills=skills,
                    active_search_skills=skills[:8],
                    experience_years=round(total_exp_years, 1),
                    target_titles=list(dict.fromkeys([t for t in target_titles if t])),
                    target_locations=[location] if location else [],
                    experience_history=exp_history,
                    education=education,
                    linkedin_url=linkedin_url,
                )

                logger.info("Successfully extracted structured LinkedIn profile for '%s' via joeyism/linkedin_scraper", full_name)
                return extracted

        except Exception as err:
            logger.warning("joeyism/linkedin_scraper extraction failed (%s), falling back to Playwright DOM scraper", err)
            return None

    @classmethod
    async def fetch_profile_text_via_playwright(
        cls,
        linkedin_url: str,
        session_cookie: Optional[str] = None,
        headless: bool = True,
    ) -> str:
        """
        Fetch candidate profile page using Playwright authenticated with LinkedIn li_at session cookie.
        """
        if not linkedin_url or "linkedin.com" not in linkedin_url:
            raise ValueError(f"Invalid LinkedIn profile URL: {linkedin_url}")

        if not session_cookie or not session_cookie.strip():
            raise ValueError(
                "LinkedIn 'li_at' session cookie is required to authenticate. "
                "Please copy your 'li_at' cookie from your browser and paste it into the field."
            )

        text_content = ""
        cookie_val = session_cookie.strip()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )

            # Inject li_at authentication cookie
            await context.add_cookies([
                {
                    "name": "li_at",
                    "value": cookie_val,
                    "domain": ".linkedin.com",
                    "path": "/",
                }
            ])

            page = await context.new_page()

            # Helper to dismiss cookie/privacy consent overlays if shown
            async def dismiss_consent():
                consent_selectors = [
                    "button[action-type='ACCEPT']",
                    "button:has-text('Accept cookies')",
                    "button:has-text('Accept')",
                    "button:has-text('Reject non-essential cookies')",
                    "button:has-text('Reject')",
                    "button:has-text('Agree & Join')",
                ]
                for sel in consent_selectors:
                    try:
                        if await page.is_visible(sel, timeout=1200):
                            await page.click(sel)
                            await page.wait_for_timeout(800)
                            break
                    except Exception:
                        pass

            logger.info("Navigating to LinkedIn profile with li_at cookie: %s", linkedin_url)
            await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(2500)
            await dismiss_consent()

            # Perform page scrolling to trigger lazy rendering of Experience, Skills, and About sections
            for scroll_step in range(1, 4):
                try:
                    await page.evaluate(f"window.scrollTo(0, (document.body.scrollHeight / 3) * {scroll_step})")
                    await page.wait_for_timeout(600)
                except Exception:
                    pass

            curr_url = page.url.lower()
            
            # Target main content area to bypass global header navigation bar
            main_locator = page.locator("main, .scaffold-layout__main, #main")
            if await main_locator.count() > 0:
                raw_body = await main_locator.first.inner_text()
            else:
                raw_body = await page.locator("body").inner_text()

            # Detect authwall / invalid session cookie redirect
            if ("authwall" in curr_url or "login" in curr_url or "signup" in curr_url or 
                "linkedin respects your privacy" in raw_body.lower() or 
                "sign in to view full profile" in raw_body.lower()):
                
                has_profile_headline = await page.locator("h1, .top-card, .pv-top-card").count() > 0
                if not has_profile_headline or "linkedin respects your privacy" in raw_body.lower():
                    await browser.close()
                    raise ValueError(
                        "Your LinkedIn 'li_at' session cookie appears to be invalid, expired, or blocked. "
                        "Please refresh LinkedIn in your browser and copy a fresh 'li_at' cookie."
                    )

            text_content = raw_body
            await browser.close()

        return text_content

    @classmethod
    async def analyze_profile_text(
        cls,
        raw_text: str,
        ai_client: Optional[BaseAIClient] = None,
        linkedin_url: Optional[str] = None,
    ) -> ExtractedProfile:
        """Analyze raw LinkedIn profile content with LLM into structured ExtractedProfile."""
        if not raw_text or not raw_text.strip():
            return ExtractedProfile(linkedin_url=linkedin_url)

        # Filter out site navigation bar and boilerplate UI lines
        ui_navigation_terms = {
            "benachrichtigungen", "weiter", "hauptinhalt", "start", "ihr", "netzwerk", "jobs",
            "nachrichten", "mitteilungen", "sie", "produkte", "linkedin", "learning", "profil",
            "abschnitt", "offen", "notifications", "next", "main", "home", "network", "messaging",
            "me", "products", "settings", "search", "privacy", "terms", "help", "signout", "signin"
        }
        cleaned_lines = [
            line.strip() for line in raw_text.split("\n")
            if line.strip() and line.strip().lower() not in ui_navigation_terms
        ]
        clean_text = "\n".join(cleaned_lines)

        # Guard against authwall / privacy policy banner text
        lower_text = clean_text.lower()
        if "linkedin respects your privacy" in lower_text or "join linkedin to view" in lower_text:
            raise ValueError("LinkedIn profile page returned a privacy/login gate. Valid 'li_at' session cookie is required.")

        client = ai_client or get_ai_client()

        try:
            prompt = (
                f"Analyze this LinkedIn profile and extract the structured profile JSON:\n\n"
                f"{clean_text[:10000]}"
            )
            response = await client.generate(
                prompt=prompt,
                system_prompt=LINKEDIN_ANALYSIS_SYSTEM_PROMPT,
                json_mode=True,
            )

            # Strip markdown formatting if any
            clean_json = response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            data = json.loads(clean_json)
            extracted = ExtractedProfile.model_validate(data)
            if linkedin_url:
                extracted.linkedin_url = linkedin_url
        except Exception as err:
            logger.warning("LLM LinkedIn profile parsing failed (%s), using regex extraction", err)

            # Filter out boilerplate web navigation lines
            ignored_prefixes = {"linkedin", "skip to", "agree", "cookie", "sign in", "join", "about"}
            lines = [l.strip() for l in raw_text.split("\n") if l.strip() and not any(l.strip().lower().startswith(p) for p in ignored_prefixes)]
            name = lines[0] if lines else "Candidate"
            
            from app.ai.profile_extractor import extract_dynamic_skills_from_text
            found_skills = extract_dynamic_skills_from_text(raw_text)

            # Check for headline in second/third line if available
            extracted_headline = lines[1] if len(lines) > 1 and len(lines[1]) < 120 else None

            extracted = ExtractedProfile(
                full_name=name[:50],
                headline=extracted_headline,
                summary="",
                skills=found_skills,
                active_search_skills=found_skills,
                experience_years=0.0,
                target_titles=[extracted_headline] if extracted_headline else [],
                target_locations=[],
                work_preference="remote_first",
                linkedin_url=linkedin_url,
            )

        # Automatically generate professional executive summary using AI if empty or generic
        if not extracted.summary or len(extracted.summary.strip()) < 25 or "Profile imported" in extracted.summary:
            try:
                from app.ai.profile_extractor import generate_candidate_bio
                extracted.summary = await generate_candidate_bio(
                    profile_data={
                        "full_name": extracted.full_name,
                        "headline": extracted.headline,
                        "experience_years": extracted.experience_years,
                        "target_titles": extracted.target_titles,
                        "skills": extracted.skills,
                        "work_preference": extracted.work_preference,
                        "cv_raw_text": raw_text,
                    },
                    ai_client=client,
                )
            except Exception as b_err:
                logger.warning("Failed auto-generating bio during LinkedIn analysis: %s", b_err)

        return extracted

    @classmethod
    async def sync_linkedin_to_profile(
        cls,
        session: Session,
        linkedin_url: str,
        session_cookie: Optional[str] = None,
        raw_text_override: Optional[str] = None,
        ai_client: Optional[BaseAIClient] = None,
    ) -> UserProfile:
        """
        Scrape, analyze, persist to SQLite UserProfile, and re-embed in ChromaDB using li_at session cookie.
        """
        extracted: Optional[ExtractedProfile] = None
        raw_text = ""

        # 1. Try Tom Quirk's official linkedin-api (Voyager REST API) first if cookie is provided
        if not raw_text_override and session_cookie and session_cookie.strip():
            extracted = cls.fetch_profile_via_linkedin_api(
                linkedin_url=linkedin_url,
                session_cookie=session_cookie,
            )
            if extracted:
                raw_text = f"Name: {extracted.full_name}\nHeadline: {extracted.headline}\nSummary: {extracted.summary}\nSkills: {', '.join(extracted.skills)}"

        # 2. Joeyism's Playwright linkedin_scraper if Voyager REST did not return a profile
        if not extracted and not raw_text_override and session_cookie and session_cookie.strip():
            extracted = await cls.fetch_profile_via_joeyism_scraper(
                linkedin_url=linkedin_url,
                session_cookie=session_cookie,
            )
            if extracted:
                raw_text = f"Name: {extracted.full_name}\nHeadline: {extracted.headline}\nSummary: {extracted.summary}\nSkills: {', '.join(extracted.skills)}"

        # 3. Fallback to raw Playwright DOM scraping & LLM analysis
        if not extracted:
            if raw_text_override and raw_text_override.strip():
                raw_text = raw_text_override.strip()
            else:
                raw_text = await cls.fetch_profile_text_via_playwright(
                    linkedin_url=linkedin_url,
                    session_cookie=session_cookie,
                )

            extracted = await cls.analyze_profile_text(
                raw_text=raw_text,
                ai_client=ai_client,
                linkedin_url=linkedin_url,
            )

        user_profile = save_profile_to_db(
            profile=extracted,
            raw_text=raw_text,
            session=session,
            source_type="linkedin",
        )

        if session_cookie and session_cookie.strip():
            user_profile.linkedin_session_cookie = session_cookie.strip()
            session.add(user_profile)
            session.commit()
            session.refresh(user_profile)

        # Synchronize vector store
        try:
            client = ai_client or get_ai_client()
            vector_store = get_vector_store()
            await ProfileEmbedder.embed_and_store_profile(
                profile=extracted,
                vector_store=vector_store,
                ai_client=client,
            )
            logger.info("Synchronized ChromaDB vector embeddings for LinkedIn profile %s", user_profile.full_name)
        except Exception as v_err:
            logger.warning("Vector sync after LinkedIn import failed: %s", v_err)

        return user_profile
