"""LinkedIn Playwright automated login handler and session cookie validator."""

import asyncio
import logging
from typing import Any, Optional
from playwright.async_api import async_playwright
from sqlmodel import Session, select

from app.db.models import UserProfile, utc_now

logger = logging.getLogger("jobot.scrapers.linkedin_auth")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class LinkedInAuthManager:
    """Manages automated Playwright login, 2FA challenge handling, and session cookie capture."""

    @classmethod
    async def login_and_capture_session(
        cls,
        email: str,
        password: str,
        headless: bool = True,
        session: Optional[Session] = None,
    ) -> dict[str, Any]:
        """
        Execute automated login to LinkedIn with provided credentials.
        Returns dictionary containing status, session cookie (li_at), and messages.
        """
        if not email or not password or not email.strip() or not password.strip():
            return {
                "success": False,
                "error": "Email and password are required for login.",
                "session_cookie": None,
            }

        logger.info("Initiating LinkedIn Playwright login for account '%s'", email.strip())
        session_cookie = None
        user_name = None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=headless,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent=DEFAULT_USER_AGENT,
                    viewport={"width": 1280, "height": 900},
                )
                page = await context.new_page()

                await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=25000)
                await page.wait_for_timeout(1000)

                # Fill credentials
                if await page.is_visible("#username", timeout=3000):
                    await page.fill("#username", email.strip())
                    await page.fill("#password", password.strip())
                    await page.click("button[type='submit']")
                    await page.wait_for_timeout(3500)

                    # Check for 2FA / checkpoint / captcha
                    current_url = page.url
                    if "checkpoint" in current_url or "challenge" in current_url:
                        logger.warning("LinkedIn presented a security challenge or 2FA prompt for '%s'", email)
                        await browser.close()
                        return {
                            "success": False,
                            "error": "LinkedIn requires 2FA or email PIN verification. Please copy your li_at session cookie from your browser and paste it into the Session Cookie field.",
                            "requires_2fa": True,
                            "session_cookie": None,
                        }

                    # Extract cookies
                    cookies = await context.cookies()
                    for c in cookies:
                        if c.get("name") == "li_at":
                            session_cookie = c.get("value")
                            break

                await browser.close()

        except Exception as err:
            logger.error("LinkedIn login process failed: %s", err)
            return {
                "success": False,
                "error": f"Login automation error: {str(err)}",
                "session_cookie": None,
            }

        if session_cookie:
            logger.info("Successfully extracted LinkedIn li_at cookie")
            if session:
                profile = session.exec(select(UserProfile)).first()
                if profile:
                    profile.linkedin_session_cookie = session_cookie
                    profile.updated_at = utc_now()
                    session.add(profile)
                    session.commit()

            return {
                "success": True,
                "message": "Successfully logged in to LinkedIn and captured session cookie!",
                "session_cookie": session_cookie,
            }

        return {
            "success": False,
            "error": "Could not capture li_at session cookie after login attempt. Please check credentials or provide cookie manually.",
            "session_cookie": None,
        }

    @classmethod
    async def validate_session_cookie(cls, session_cookie: str) -> bool:
        """Verify whether a given li_at cookie is valid by querying LinkedIn feed header."""
        if not session_cookie or len(session_cookie) < 10:
            return False

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(user_agent=DEFAULT_USER_AGENT)
                await context.add_cookies([{
                    "name": "li_at",
                    "value": session_cookie.strip(),
                    "domain": ".linkedin.com",
                    "path": "/",
                }])
                page = await context.new_page()
                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2000)

                # If redirected to login page, cookie is expired
                is_valid = "login" not in page.url and "authwall" not in page.url
                await browser.close()
                return is_valid
        except Exception:
            return False
