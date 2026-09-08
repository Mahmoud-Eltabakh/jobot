"""JobSpy scraper integration for LinkedIn, Google Jobs, and other major platforms."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional
import pandas as pd
from jobspy import scrape_jobs

from app.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger("jobot.scrapers.jobspy")


class JobSpyScraper(BaseScraper):
    """Asynchronous wrapper around python-jobspy library."""

    SUPPORTED_SITES = ["linkedin", "google", "indeed", "glassdoor", "zip_recruiter"]

    def __init__(self, default_sites: Optional[list[str]] = None) -> None:
        self.default_sites = default_sites or ["linkedin", "google"]

    def _sync_scrape(
        self,
        search_term: str,
        location: str,
        results_wanted: int,
        site_name: list[str],
        is_remote: bool,
        hours_old: int,
        country_indeed: str,
    ) -> list[ScrapedJob]:
        """Synchronous scraper invocation running in background thread pool."""
        logger.info(
            "Executing JobSpy scrape: search_term='%s', location='%s', sites=%s, results_wanted=%d",
            search_term,
            location,
            site_name,
            results_wanted,
        )

        try:
            df = scrape_jobs(
                site_name=site_name,
                search_term=search_term,
                location=location,
                results_wanted=results_wanted,
                is_remote=is_remote,
                hours_old=hours_old,
                country_indeed=country_indeed,
            )
        except Exception as err:
            logger.error("JobSpy scraping failed: %s", err, exc_info=True)
            return []

        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            logger.info("JobSpy returned no results for query '%s'", search_term)
            return []

        scraped_jobs: list[ScrapedJob] = []
        for _, row in df.iterrows():
            try:
                title = str(row.get("title") or "").strip()
                company = str(row.get("company") or "").strip()
                url = str(row.get("job_url") or "").strip()

                # Basic validation
                if not title or not url:
                    continue

                location_val = str(row.get("location") or location).strip()
                site_val = str(row.get("site") or "jobspy").lower().strip()
                description_val = str(row.get("description") or "").strip()

                # Parse salary numbers
                salary_min = None
                salary_max = None
                min_amount = row.get("min_amount")
                max_amount = row.get("max_amount")
                if pd.notna(min_amount):
                    try:
                        salary_min = float(min_amount)
                    except (ValueError, TypeError):
                        pass
                if pd.notna(max_amount):
                    try:
                        salary_max = float(max_amount)
                    except (ValueError, TypeError):
                        pass

                currency_val = str(row.get("currency") or "").strip() or None

                # Remote flag
                remote_flag = bool(row.get("is_remote", False)) or is_remote

                # Date posted
                date_posted_val = None
                dp = row.get("date_posted")
                if pd.notna(dp):
                    if isinstance(dp, datetime):
                        date_posted_val = dp
                    elif isinstance(dp, str):
                        try:
                            date_posted_val = datetime.fromisoformat(dp)
                        except Exception:
                            pass

                scraped_job = ScrapedJob(
                    source=site_val,
                    source_id=str(row.get("id") or None) if pd.notna(row.get("id")) else None,
                    title=title,
                    company=company,
                    location=location_val or "",
                    is_remote=remote_flag,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=currency_val,
                    url=url,
                    description=description_val,
                    date_posted=date_posted_val,
                )
                scraped_jobs.append(scraped_job)
            except Exception as row_err:
                logger.warning("Failed to parse JobSpy row: %s", row_err)

        logger.info("JobSpy successfully extracted %d jobs", len(scraped_jobs))
        return scraped_jobs

    async def scrape(
        self,
        search_term: str,
        location: str,
        results_wanted: Optional[int] = None,
        site_name: Optional[list[str]] = None,
        is_remote: bool = False,
        hours_old: int = 72,
        country_indeed: Optional[str] = None,
    ) -> list[ScrapedJob]:
        """Run JobSpy scraper asynchronously in thread pool without artificial small limits."""
        sites = site_name or self.default_sites
        # Validate sites
        valid_sites = [s.lower() for s in sites if s.lower() in self.SUPPORTED_SITES]
        if not valid_sites:
            valid_sites = ["linkedin", "google"]

        # If results_wanted is not provided, fetch up to 100 per query
        limit_val = results_wanted if results_wanted is not None else 100
        country_val = country_indeed or (location.strip())

        return await asyncio.to_thread(
            self._sync_scrape,
            search_term=search_term,
            location=location,
            results_wanted=limit_val,
            site_name=valid_sites,
            is_remote=is_remote,
            hours_old=hours_old,
            country_indeed=country_val,
        )
