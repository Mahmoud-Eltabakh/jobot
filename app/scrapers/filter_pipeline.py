"""Title, company, and keyword pre-filter pipeline for filtering out unwanted jobs before AI evaluation."""

import logging
import re
from dataclasses import dataclass
from typing import Optional, Union
from sqlmodel import Session, select

from app.db.models import FilterRule, Job, JobStatus, utc_now
from app.scrapers.base import ScrapedJob

logger = logging.getLogger("jobot.scrapers.filter_pipeline")


@dataclass
class FilterResult:
    """Outcome of evaluating a job against active blacklist filter rules."""

    is_filtered: bool
    matched_rule: Optional[FilterRule] = None
    reason: Optional[str] = None


class JobFilterPipeline:
    """Evaluates jobs against active FilterRules to reject unwanted positions before AI scoring."""

    @classmethod
    def evaluate_job(
        cls,
        job: Union[ScrapedJob, Job],
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
                try:
                    regex_flags = re.IGNORECASE
                    if rule.rule_type == "title" and re.search(pattern, job.title or "", regex_flags):
                        matched = True
                    elif rule.rule_type == "company" and re.search(pattern, job.company or "", regex_flags):
                        matched = True
                    elif rule.rule_type == "keyword" and (
                        re.search(pattern, job.description or "", regex_flags)
                        or re.search(pattern, job.title or "", regex_flags)
                    ):
                        matched = True
                except re.error as err:
                    logger.warning("Invalid regex in FilterRule id=%s pattern='%s': %s", rule.id, pattern, err)
                    continue
            else:
                pat_lower = pattern.lower()
                if rule.rule_type == "title" and pat_lower in title_lower:
                    matched = True
                elif rule.rule_type == "company" and pat_lower in company_lower:
                    matched = True
                elif rule.rule_type == "keyword" and (pat_lower in desc_lower or pat_lower in title_lower):
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
    ) -> tuple[list[Job], list[Job]]:
        """
        Apply active blacklist rules to newly inserted jobs.
        
        Returns:
            (approved_for_ai_jobs, filtered_out_jobs)
        """
        if not jobs:
            return [], []

        active_rules = session.exec(
            select(FilterRule).where(FilterRule.is_active.is_(True))
        ).all()

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
