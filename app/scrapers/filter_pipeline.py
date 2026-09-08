"""Title, company, and keyword pre-filter pipeline for filtering out unwanted jobs before AI evaluation."""

import concurrent.futures
import logging
import re
from dataclasses import dataclass

from sqlmodel import Session, select

from app.db.models import FilterRule, Job, JobStatus
from app.scrapers.base import ScrapedJob

logger = logging.getLogger("jobot.scrapers.filter_pipeline")

# Timeout (seconds) for a single regex match to prevent ReDoS catastrophic backtracking
_REGEX_TIMEOUT_SECONDS = 1.0

# Pre-compiled patterns that signal a potentially catastrophic regex
_DANGEROUS_PATTERN = re.compile(
    r"(\([^)]*[+*][^)]*\)[+*])"  # e.g. (a+)+ or (a*)* — exponential backtracking risk
)
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="regex_guard")


def _is_safe_regex(pattern: str) -> bool:
    """Return False if the regex exhibits known catastrophic backtracking constructs."""
    return not bool(_DANGEROUS_PATTERN.search(pattern))


def _safe_regex_search(pattern: str, text: str, flags: int = 0) -> bool:
    """Execute a regex search with a hard timeout to prevent ReDoS.

    Returns False if the pattern times out or raises an error.
    """
    future = _EXECUTOR.submit(re.search, pattern, text, flags)
    try:
        result = future.result(timeout=_REGEX_TIMEOUT_SECONDS)
        return result is not None
    except concurrent.futures.TimeoutError:
        logger.warning("Regex pattern timed out (possible ReDoS): '%s'", pattern[:80])
        future.cancel()
        return False
    except re.error as err:
        logger.warning("Invalid regex pattern '%s': %s", pattern[:80], err)
        return False


@dataclass
class FilterResult:
    """Outcome of evaluating a job against active blacklist filter rules."""

    is_filtered: bool
    matched_rule: FilterRule | None = None
    reason: str | None = None


class JobFilterPipeline:
    """Evaluates jobs against active FilterRules to reject unwanted positions before AI scoring."""

    @classmethod
    def evaluate_job(
        cls,
        job: ScrapedJob | Job,
        active_rules: list[FilterRule],
    ) -> FilterResult:
        """
        Evaluate a job against active filter rules.
        
        Rule types:
          - 'title': Checked against job.title
          - 'company': Checked against job.company
          - 'keyword': Checked against job.description and job.title
        """
        title_lower = (job.title or "").lower()
        company_lower = (job.company or "").lower()
        desc_lower = (job.description or "").lower()

        for rule in active_rules:
            if not rule.is_active or not rule.pattern:
                continue

            pattern = rule.pattern.strip()
            matched = False

            if rule.is_regex:
                if not _is_safe_regex(pattern):
                    logger.warning(
                        "FilterRule id=%s pattern='%s' rejected: potential catastrophic backtracking (ReDoS)",
                        rule.id, pattern[:80],
                    )
                    continue
                regex_flags = re.IGNORECASE
                if rule.rule_type == "title":
                    matched = _safe_regex_search(pattern, job.title or "", regex_flags)
                elif rule.rule_type == "company":
                    matched = _safe_regex_search(pattern, job.company or "", regex_flags)
                elif rule.rule_type == "keyword":
                    matched = _safe_regex_search(pattern, job.description or "", regex_flags) or \
                              _safe_regex_search(pattern, job.title or "", regex_flags)
            else:
                pat_lower = pattern.lower()
                if rule.rule_type == "title" and pat_lower in title_lower or rule.rule_type == "company" and pat_lower in company_lower or rule.rule_type == "keyword" and (pat_lower in desc_lower or pat_lower in title_lower):
                    matched = True

            if matched:
                reason = f"Filtered by {rule.rule_type} blacklist rule: '{pattern}'"
                logger.debug("Job '%s' at '%s' matched filter rule %s", job.title, job.company, reason)
                return FilterResult(is_filtered=True, matched_rule=rule, reason=reason)

        return FilterResult(is_filtered=False)

    @classmethod
    def apply_filters_and_save(
        cls,
        jobs: list[Job],
        session: Session,
        user_id: int | None = None,
    ) -> tuple[list[Job], list[Job]]:
        """
        Apply active blacklist rules to newly inserted jobs.
        
        Returns:
            (approved_for_ai_jobs, filtered_out_jobs)
        """
        if not jobs:
            return [], []

        stmt = select(FilterRule).where(FilterRule.is_active.is_(True))
        if user_id is not None:
            stmt = stmt.where(FilterRule.user_id == user_id)
        active_rules = session.exec(stmt).all()

        approved_for_ai: list[Job] = []
        filtered_out: list[Job] = []

        for job in jobs:
            result = cls.evaluate_job(job, active_rules)
            if result.is_filtered:
                job.status = JobStatus.NOT_A_FIT.value
                job.fit_score = 0
                job.fit_summary = result.reason
                logger.info("Deleting blacklisted Job id=%d ('%s' at '%s') from databank: %s", job.id, job.title, job.company, result.reason)
                session.delete(job)
                filtered_out.append(job)
            else:
                approved_for_ai.append(job)

        if filtered_out:
            session.commit()

        logger.info(
            "Filter pipeline processed %d jobs: %d approved for AI, %d deleted as blacklisted/NOT_A_FIT",
            len(jobs),
            len(approved_for_ai),
            len(filtered_out),
        )
        return approved_for_ai, filtered_out
