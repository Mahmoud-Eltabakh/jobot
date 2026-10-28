"""JobSpy scraper integration for LinkedIn, Google Jobs, and other major platforms."""

import asyncio
import logging
from datetime import datetime

import pandas as pd
from jobspy import scrape_jobs
from jobspy.model import Country

from app.scrapers.base import BaseScraper, ScrapedJob

logger = logging.getLogger("jobot.scrapers.jobspy")

# JobSpy's own default market, used when a location does not name a country.
DEFAULT_JOBSPY_COUNTRY = "usa"


def resolve_jobspy_country(location: str | None, explicit_country: str | None = None) -> str:
    """Return a country string JobSpy accepts for Indeed/Glassdoor domain selection.

    JobSpy validates ``country_indeed`` even for sites that ignore it, so an empty
    or city-style location (e.g. "Berlin, Germany") must never be passed raw.
    """
    candidates = [explicit_country or "", location or ""]
    # Also try the trailing comma segment, which usually holds the country name.
    if location and "," in location:
        candidates.append(location.rsplit(",", 1)[1])

    for candidate in candidates:
        value = candidate.strip()
        if not value:
            continue
        try:
            Country.from_string(value)
            return value
        except ValueError:
            continue
    return DEFAULT_JOBSPY_COUNTRY


class JobSpyScraper(BaseScraper):
    """Asynchronous wrapper around python-jobspy library."""

    SUPPORTED_SITES = ["linkedin", "google", "indeed", "glassdoor", "zip_recruiter"]

    def __init__(self, default_sites: list[str] | None = None) -> None:
        self.default_sites = default_sites or []

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
        results_wanted: int | None = None,
        site_name: list[str] | None = None,
        is_remote: bool = False,
        hours_old: int = 72,
        country_indeed: str | None = None,
    ) -> list[ScrapedJob]:
        """Run JobSpy scraper asynchronously across target websites in parallel threads.

        When multiple job boards are requested (e.g. LinkedIn and Google Jobs),
        individual site extractions are dispatched to concurrent background threads
        to eliminate serial I/O bottlenecks.
        """
        sites = site_name or self.default_sites
        # Validate requested platforms against supported list
        valid_sites = [s.lower() for s in sites if s.lower() in self.SUPPORTED_SITES]
        if not valid_sites:
            valid_sites = ["linkedin", "google"]

        limit_val = results_wanted if results_wanted is not None else 50
        loc_val = location.strip() if location else ""
        country_val = resolve_jobspy_country(location, country_indeed)

        # Parallel multi-site scraping dispatch
        if len(valid_sites) > 1:
            tasks = [
                asyncio.to_thread(
                    self._sync_scrape,
                    search_term=search_term,
                    location=loc_val,
                    results_wanted=limit_val,
                    site_name=[site],
                    is_remote=is_remote,
                    hours_old=hours_old,
                    country_indeed=country_val,
                )
                for site in valid_sites
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            all_jobs: list[ScrapedJob] = []
            for res in results:
                if isinstance(res, list):
                    all_jobs.extend(res)
                elif isinstance(res, Exception):
                    logger.warning("Parallel JobSpy site scrape failed: %s", res)
            return all_jobs

        # Single site invocation
        return await asyncio.to_thread(
            self._sync_scrape,
            search_term=search_term,
            location=loc_val,
            results_wanted=limit_val,
            site_name=valid_sites,
            is_remote=is_remote,
            hours_old=hours_old,
            country_indeed=country_val,
        )
