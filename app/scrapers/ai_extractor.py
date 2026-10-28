"""Normalize untrusted listing text through the owner's scraping assignment.

HTML cleaning reduces the prompt payload; it is not a provider fallback.
The system prompt and user content remain separate at the generation boundary.
An explicitly injected generation client preserves existing integration tests.
Otherwise the session and owner select credentials and the scraping model.
No account client is cached or shared between independent extraction calls.
Schema failures are reported through the same safe error contract as adapters.
An empty object cannot become an apparently successful job with default fields.
A valid non-job classification may still discard advertising without an error.
No deterministic parser fabricates a listing from page text or a placeholder URL.
Cancellation is not caught and can unwind the caller's worker normally.
"""

import json
import logging
import re

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.ai.client import AIProviderError, BaseAIClient, _provider_error, get_ai_client
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
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    description: str = Field(default="")
    required_skills: list[str] = Field(default_factory=list)
    visa_sponsorship: str | None = None
    language_requirement: str | None = None
    is_legitimate_job: bool = Field(default=True)


class AIScraperExtractor:
    """Extract job records without converting provider failures into jobs.

    Owner context is keyword-only so the established four positional
    arguments keep their meanings for existing scraper integrations.
    """

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
        ai_client: BaseAIClient | None = None,
        *,
        session: Session | None = None,
        user_id: int | None = None,
    ) -> ScrapedJob | None:
        """Parse raw HTML/DOM through an owner-scoped scraping client.

        Empty source input is a no-op, not a model failure. Nonempty input
        requires a valid provider response with a usable listing identity.
        Fenced JSON remains accepted for compatible existing clients, while
        invalid schemas are normalized without logging the response body.
        A legitimate listing retains source provenance and cleaned content.
        Typed adapter failures propagate unchanged, preserving status/model
        metadata for queue and API consumers. Other parsing failures are
        sanitized before crossing the same public error boundary.
        """
        cleaned_text = cls.clean_html_to_markdown_text(html_or_text)
        if not cleaned_text:
            return None

        client = ai_client or get_ai_client(session, user_id, task_type="scraping")

        try:
            prompt = f"Extract structured job posting from this web page content:\n\nURL: {source_url}\nSource: {source}\n\n{cleaned_text}"
            response = await client.generate(
                prompt=prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
                json_mode=True,
            )

            clean_json = response.strip()
            clean_json = clean_json.removeprefix("```json")
            clean_json = clean_json.removeprefix("```")
            clean_json = clean_json.removesuffix("```")
            clean_json = clean_json.strip()

            data = json.loads(clean_json)
            extracted = AIExtractedJobListing.model_validate(data)

            if not extracted.is_legitimate_job:
                logger.info("AI extractor flagged listing at %s as non-job content", source_url)
                return None

            if not extracted.title.strip() or not extracted.company.strip():
                raise ValueError("Missing job identity")

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
                url=source_url,
                description=extracted.description or cleaned_text[:1000],
            )
        except AIProviderError:
            raise
        except Exception as err:
            raise _provider_error(
                getattr(client, "provider", "ollama"), getattr(client, "model", ""), err,
            ) from None

