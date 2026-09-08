"""Dedicated StepStone Playwright crawler and DOM parser."""

import logging
import random
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger("jobot.scrapers.stepstone")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


class StepStoneScraper(BaseScraper):
    """Playwright-based crawler targeting StepStone job listings."""

    BASE_URL = "https://www.stepstone.de"

    def __init__(self, headless: bool = True, user_agent: str | None = None) -> None:
        self.headless = headless
        self.user_agent = user_agent or DEFAULT_USER_AGENT

    @classmethod
    def parse_cards_from_html(
        cls,
        html_content: str,
        base_url: str = BASE_URL,
        search_term: str | None = None,
    ) -> list[ScrapedJob]:
        """Parse StepStone search result cards from raw HTML (for testability and headless runs)."""
        soup = BeautifulSoup(html_content, "html.parser")
        scraped_jobs: list[ScrapedJob] = []

        # StepStone card container selectors
        cards = soup.find_all("article", attrs={"data-testid": "job-item"})
        if not cards:
            cards = soup.find_all("article")

        for card in cards:
            try:
                # 1. Title and URL
                title_elem = card.find("a", attrs={"data-testid": "job-item-title"}) or card.find("h2") or card.find("a")
                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                href = title_elem.get("href") or ""
                if not href and card.name == "a":
                    href = card.get("href") or ""

                if not title or not href:
                    continue

                full_url = urljoin(base_url, href)

                # 2. Company Name
                company_elem = (
                    card.find("span", attrs={"data-testid": "job-item-company-name"})
                    or card.find("div", attrs={"data-at": "job-item-company-name"})
                    or card.find("span", class_=re.compile(r"company", re.IGNORECASE))
                )
                company = company_elem.get_text(strip=True) if company_elem else ""

                # 3. Location & Remote
                location_elem = (
                    card.find("span", attrs={"data-testid": "job-item-location"})
                    or card.find("span", class_=re.compile(r"location", re.IGNORECASE))
                )
                location = location_elem.get_text(strip=True) if location_elem else ""
                is_remote = bool(re.search(r"remote|homeoffice|home-office|mobil", location + " " + card.get_text(), re.IGNORECASE))

                # 4. Salary Tags
                salary_elem = card.find("span", attrs={"data-testid": "job-item-salary"}) or card.find("span", class_=re.compile(r"salary", re.IGNORECASE))
                salary_min = None
                salary_max = None
                salary_currency = None

                if salary_elem:
                    salary_text = salary_elem.get_text(strip=True)
                    if "€" in salary_text or "EUR" in salary_text:
                        salary_currency = "EUR"
                    elif "$" in salary_text:
                        salary_currency = "USD"

                    numbers = re.findall(r"(\d+[\.,]?\d*)", salary_text.replace(".", "").replace(",", "."))
                    if numbers:
                        try:
                            if len(numbers) >= 2:
                                salary_min = float(numbers[0])
                                salary_max = float(numbers[1])
                            else:
                                salary_min = float(numbers[0])
                        except ValueError:
                            pass

                # 5. Snippet / Description
                snippet_elem = card.find("div", attrs={"data-testid": "job-item-snippet"}) or card.find("p")
                description = snippet_elem.get_text(strip=True) if snippet_elem else f"{title} position at {company}."

                scraped_job = ScrapedJob(
                    source="stepstone",
                    source_id=href.split("/")[-1] if href else None,
                    title=title,
                    company=company,
                    location=location,
                    is_remote=is_remote,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=salary_currency,
                    url=full_url,
                    description=description,
                )
                scraped_jobs.append(scraped_job)
            except Exception as card_err:
                logger.debug("Failed parsing StepStone card: %s", card_err)

        # AI-Assisted DOM Extraction Fallback if CSS parsing yielded 0 cards on rich detail/listing page
        cleaned_text = html_content.strip()
        if not scraped_jobs and len(cleaned_text) > 200 and re.search(r"experience|requirements|qualifications|tasks|salary|full-time|developer|engineer", cleaned_text, re.IGNORECASE):
            from app.scrapers.ai_extractor import AIScraperExtractor
            fallback_job = AIScraperExtractor._fallback_heuristic_extractor(
                text=AIScraperExtractor.clean_html_to_markdown_text(html_content),
                source_url=base_url,
                source="stepstone",
                default_title=search_term.strip() if (search_term and search_term.strip()) else None,
            )
            invalid_title_patterns = {"no jobs found", "keine jobs gefunden", "no results found", "404 not found", "error"}
            if fallback_job and fallback_job.title.strip().lower() not in invalid_title_patterns:
                scraped_jobs.append(fallback_job)

        return scraped_jobs

    async def scrape(
        self,
        search_term: str,
        location: str,
        results_wanted: int | None = None,
        is_remote: bool = False,
    ) -> list[ScrapedJob]:
        """Crawl StepStone search results page using Playwright without artificial limits."""
        encoded_term = quote(search_term)
        encoded_loc = quote(location)
        search_url = f"{self.BASE_URL}/work/{encoded_term}-in-{encoded_loc}"

        logger.info("Starting StepStone Playwright scrape: %s", search_url)
        all_jobs: list[ScrapedJob] = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                context = await browser.new_context(
                    user_agent=self.user_agent,
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()

                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=25000)
                    await page.wait_for_timeout(random.randint(1500, 2500))

                    # Dismiss cookie consent dialog if present
                    consent_selectors = [
                        "button#ccmgt_explicit_accept",
                        "button[data-testid='accept-all']",
                        "button:has-text('Alle akzeptieren')",
                        "button:has-text('Accept all')",
                    ]
                    for sel in consent_selectors:
                        try:
                            if await page.is_visible(sel, timeout=1500):
                                await page.click(sel)
                                await page.wait_for_timeout(1000)
                                break
                        except Exception:
                            pass

                    # Extract page HTML
                    content = await page.content()
                    all_jobs = self.parse_cards_from_html(
                        html_content=content,
                        base_url=self.BASE_URL,
                        search_term=search_term,
                    )

                finally:
                    await context.close()
                    await browser.close()

        except Exception as err:
            logger.error("StepStone Playwright scraping encountered an error: %s", err, exc_info=True)

        logger.info("StepStone scraper finished with %d jobs", len(all_jobs))
        if results_wanted is not None:
            return all_jobs[:results_wanted]
        return all_jobs
