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


class LinkedInProfileAnalyzer:
    """Scrapes, parses, and synchronizes candidate LinkedIn profiles using li_at session cookie."""

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

            curr_url = page.url.lower()
            body_elem = page.locator("body")
            raw_body = await body_elem.inner_text()

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

        # Guard against authwall / privacy policy banner text
        lower_text = raw_text.lower()
        if "linkedin respects your privacy" in lower_text or "join linkedin to view" in lower_text:
            raise ValueError("LinkedIn profile page returned a privacy/login gate. Valid 'li_at' session cookie is required.")

        client = ai_client or get_ai_client()

        try:
            prompt = (
                f"Analyze this LinkedIn profile and extract the structured profile JSON:\n\n"
                f"{raw_text[:10000]}"
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
