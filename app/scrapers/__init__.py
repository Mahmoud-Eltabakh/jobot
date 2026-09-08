"""Job scraping subsystem coordinating JobSpy, StepStone, deduplication, and pre-filtering."""

from app.scrapers.base import BaseScraper, ScrapedJob
from app.scrapers.dedup import compute_dedup_hash, save_scraped_jobs
from app.scrapers.jobspy_scraper import JobSpyScraper
from app.scrapers.stepstone import StepStoneScraper

__all__ = [
    "BaseScraper",
    "JobSpyScraper",
    "ScrapedJob",
    "StepStoneScraper",
    "compute_dedup_hash",
    "save_scraped_jobs",
]
