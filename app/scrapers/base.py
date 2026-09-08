"""Base scraping contracts and standardized ScrapedJob data model."""

import abc
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ScrapedJob(BaseModel):
    """Standardized representation of a job listing scraped from any board."""

    source: str = Field(description="Platform source, e.g. 'linkedin', 'google', 'stepstone'")
    source_id: Optional[str] = Field(default=None, description="External job ID if available")
    title: str = Field(description="Job title")
    company: str = Field(description="Hiring company name")
    location: str = Field(default="", description="Job location or region")
    is_remote: bool = Field(default=False, description="Remote work availability flag")
    salary_min: Optional[float] = Field(default=None, description="Minimum compensation amount")
    salary_max: Optional[float] = Field(default=None, description="Maximum compensation amount")
    salary_currency: Optional[str] = Field(default=None, description="Currency code (e.g. USD, EUR)")
    url: str = Field(description="Direct URL to the job posting")
    description: str = Field(default="", description="Full or summary job description text")
    date_posted: Optional[datetime] = Field(default=None, description="Posting date if available")


class BaseScraper(abc.ABC):
    """Abstract base class for all job scrapers."""

    @abc.abstractmethod
    async def scrape(
        self,
        search_term: str,
        location: str,
        results_wanted: Optional[int] = None,
        is_remote: bool = False,
    ) -> list[ScrapedJob]:
        """Scrape jobs matching search criteria and return standardized ScrapedJob objects."""
        raise NotImplementedError
