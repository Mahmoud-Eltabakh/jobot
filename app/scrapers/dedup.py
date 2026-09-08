"""Deterministic deduplication hashing and database persistence for scraped jobs."""

import hashlib
import logging
import re
from typing import Optional
from sqlmodel import Session, select

from app.db.models import Job, JobStatus, utc_now
from app.scrapers.base import ScrapedJob

logger = logging.getLogger("jobot.scrapers.dedup")


def normalize_string(val: Optional[str]) -> str:
    """Normalize string for hash stability: lowercase, remove non-alphanumeric/spaces, collapse whitespace."""
    if not val:
        return ""
    # Lowercase and convert whitespace
    cleaned = val.lower().strip()
    # Remove punctuation except letters and digits
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def compute_dedup_hash(company: str, title: str, location: str) -> str:
    """Compute deterministic SHA-256 hash from normalized company, title, and location."""
    norm_company = normalize_string(company)
    norm_title = normalize_string(title)
    norm_location = normalize_string(location)
    raw = f"{norm_company}|{norm_title}|{norm_location}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def save_scraped_jobs(
    scraped_jobs: list[ScrapedJob],
    session: Session,
) -> tuple[list[Job], int]:
    """
    Deduplicate and insert new ScrapedJob records into SQLite.
    
    Returns:
        (list_of_newly_inserted_jobs, count_of_skipped_duplicates)
    """
    if not scraped_jobs:
        return [], 0

    # Precompute hashes
    jobs_with_hashes: list[tuple[ScrapedJob, str]] = [
        (sj, compute_dedup_hash(sj.company, sj.title, sj.location))
        for sj in scraped_jobs
    ]

    all_hashes = [h for _, h in jobs_with_hashes]

    # Query all existing hashes in one batch
    existing_jobs = session.exec(
        select(Job.dedup_hash).where(Job.dedup_hash.in_(all_hashes))
    ).all()
    existing_hashes_set = set(existing_jobs)

    inserted_jobs: list[Job] = []
    skipped_count = 0
    seen_in_batch_set: set[str] = set()

    for sj, h in jobs_with_hashes:
        if h in existing_hashes_set or h in seen_in_batch_set:
            skipped_count += 1
            continue

        seen_in_batch_set.add(h)
        db_job = Job(
            source=sj.source,
            source_id=sj.source_id,
            title=sj.title,
            company=sj.company,
            location=sj.location,
            is_remote=sj.is_remote,
            salary_min=sj.salary_min,
            salary_max=sj.salary_max,
            salary_currency=sj.salary_currency,
            url=sj.url,
            description=sj.description,
            status=JobStatus.SEEN.value,
            dedup_hash=h,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(db_job)
        inserted_jobs.append(db_job)

    if inserted_jobs:
        session.commit()
        for j in inserted_jobs:
            session.refresh(j)

    logger.info(
        "Processed %d scraped jobs: %d newly inserted, %d duplicates skipped",
        len(scraped_jobs),
        len(inserted_jobs),
        skipped_count,
    )
    return inserted_jobs, skipped_count
