"""AI-Assisted Web Scraper: Dynamic DOM, HTML & Text Job Extractor."""

import json
import logging
import re
from typing import Any, Optional
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from app.ai.client import BaseAIClient, get_ai_client
from app.scrapers.base import ScrapedJob

logger = logging.getLogger("jobot.scrapers.ai_extractor")

EXTRACTION_SYSTEM_PROMPT = """You are an expert AI web scraping and job listing extraction engine.
Analyze the provided raw HTML or web page text and extract the structured job listing details into a valid JSON object.

Output JSON fields required:
1. title: string (exact job title)
2. company: string (hiring company name)
3. location: string (city, country, or Remote)
4. is_remote: boolean (true if remote, hybrid-remote, or work from home allowed)
5. salary_min: float or null (numeric minimum annual/hourly compensation if specified)
6. salary_max: float or null (numeric maximum annual/hourly compensation if specified)
7. salary_currency: string or null (e.g. "EUR", "USD", "GBP")
8. description: string (comprehensive cleaned summary of role, duties, and qualifications)
9. required_skills: list of strings (programming languages, tools, frameworks, concepts)
10. visa_sponsorship: string or null ("available", "not_available", or null if not stated)
11. language_requirement: string or null (e.g. "English", "German (B2)", "Bilingual")
12. is_legitimate_job: boolean (false if spam, course advertisement, or promotional banner)

Return ONLY valid JSON matching this schema without markdown fences.
"""


class AIExtractedJobListing(BaseModel):
    """Structured job details extracted from unstructured web page content."""

    title: str = Field(default="")
    company: str = Field(default="")
    location: str = Field(default="")
    is_remote: bool = Field(default=False)
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    description: str = Field(default="")
    required_skills: list[str] = Field(default_factory=list)
    visa_sponsorship: Optional[str] = None
    language_requirement: Optional[str] = None
    is_legitimate_job: bool = Field(default=True)


class AIScraperExtractor:
    """Extracts clean job records from arbitrary rendered HTML or text using LLM."""

    @classmethod
    def clean_html_to_markdown_text(cls, html_content: str, max_chars: int = 8000) -> str:
        """Strip scripts, styles, and boilerplate DOM to provide high-density text for LLM."""
        if not html_content or not html_content.strip():
            return ""

        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "svg", "noscript", "iframe"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Collapse excessive newlines
        cleaned = re.sub(r"\n{3,}", "\n\n", text)
        return cleaned[:max_chars]

    @classmethod
    async def extract_from_html(
        cls,
        html_or_text: str,
        source_url: str = "",
        source: str = "web",
        ai_client: Optional[BaseAIClient] = None,
    ) -> Optional[ScrapedJob]:
        """Parse raw HTML/DOM into a normalized ScrapedJob using AI."""
        cleaned_text = cls.clean_html_to_markdown_text(html_or_text)
        if not cleaned_text:
            return None

        client = ai_client or get_ai_client()

        try:
            prompt = f"Extract structured job posting from this web page content:\n\nURL: {source_url}\nSource: {source}\n\n{cleaned_text}"
            response = await client.generate(
                prompt=prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                json_mode=True,
            )

            clean_json = response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            clean_json = clean_json.strip()

            data = json.loads(clean_json)
            extracted = AIExtractedJobListing.model_validate(data)

            if not extracted.is_legitimate_job:
                logger.info("AI extractor flagged listing at %s as non-job content", source_url)
                return None

            return ScrapedJob(
                source=source,
                source_id=None,
                title=extracted.title,
                company=extracted.company,
                location=extracted.location,
                is_remote=extracted.is_remote,
                salary_min=extracted.salary_min,
                salary_max=extracted.salary_max,
                salary_currency=extracted.salary_currency,
                url=source_url or "https://example.com/job",
                description=extracted.description or cleaned_text[:1000],
            )
        except Exception as err:
            logger.warning("AI extraction failed (%s), falling back to heuristic extractor", err)
            return cls._fallback_heuristic_extractor(cleaned_text, source_url, source)

    @classmethod
    def _fallback_heuristic_extractor(
        cls,
        text: str,
        source_url: str,
        source: str,
        default_title: Optional[str] = None,
    ) -> ScrapedJob:
        """Heuristic regex-based fallback extractor for offline or non-AI modes."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        title = default_title.strip() if (default_title and default_title.strip()) else (lines[0] if lines else "")
        company = lines[1] if len(lines) > 1 else ""

        is_remote = bool(re.search(r"\b(remote|homeoffice|work from home)\b", text, re.IGNORECASE))
        
        salary_min, salary_max, curr = None, None, None
        salary_match = re.search(r"(\d{2,3})[,\.]?(\d{3})\s*[-–]\s*(\d{2,3})[,\.]?(\d{3})\s*(€|\$|EUR|USD)?", text)
        if salary_match:
            try:
                salary_min = float(salary_match.group(1) + salary_match.group(2))
                salary_max = float(salary_match.group(3) + salary_match.group(4))
                if salary_match.group(5):
                    curr = salary_match.group(5)
            except Exception:
                pass

        return ScrapedJob(
            source=source,
            source_id=None,
            title=title[:100],
            company=company[:100],
            location="Remote" if is_remote else "",
            is_remote=is_remote,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=curr,
            url=source_url or "",
            description=text[:2500],
        )
