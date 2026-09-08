"""Tests for CV document parsing and structured profile extraction."""

import io
import pytest
import pypdf
from sqlmodel import Session

from app.ai.cv_parser import CVParser, MAX_FILE_SIZE
from app.ai.profile_extractor import (
    ExtractedProfile,
    _fallback_heuristic_extraction,
    extract_profile_from_text,
    save_profile_to_db,
)
from app.db.database import engine, init_db
from app.db.models import UserProfile


@pytest.fixture(autouse=True)
def setup_db() -> None:
    init_db()


def create_minimal_pdf_bytes(text: str) -> bytes:
    """Helper to generate valid PDF binary in memory with text."""
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    # pypdf blank page is valid PDF
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_cv_parser_valid_txt() -> None:
    """Test extracting clean text from TXT resume."""
    parser = CVParser()
    sample_text = b"John Doe\nSenior Python Engineer\nSkills: Python, FastAPI, Docker, SQL\n5+ years of experience."
    extracted = parser.extract_text_from_bytes(sample_text, "resume.txt")
    assert "John Doe" in extracted
    assert "Python" in extracted


def test_cv_parser_file_size_limit() -> None:
    """Test rejection of files exceeding MAX_FILE_SIZE."""
    parser = CVParser()
    oversized = b"a" * (MAX_FILE_SIZE + 100)
    with pytest.raises(ValueError, match="File size exceeds maximum limit"):
        parser.extract_text_from_bytes(oversized, "resume.pdf")


def test_cv_parser_invalid_pdf_magic_bytes() -> None:
    """Test rejection of file with .pdf extension but invalid header."""
    parser = CVParser()
    fake_pdf = b"THIS IS NOT A VALID PDF FILE"
    with pytest.raises(ValueError, match="missing '%PDF-' header signature"):
        parser.extract_text_from_bytes(fake_pdf, "corrupted.pdf")


def test_cv_parser_unsupported_format() -> None:
    """Test rejection of unsupported file extension."""
    parser = CVParser()
    with pytest.raises(ValueError, match="Unsupported file format"):
        parser.extract_text_from_bytes(b"content", "resume.exe")


def test_profile_heuristic_extraction() -> None:
    """Test fallback heuristic extraction when LLM is unavailable."""
    sample_text = """
    Jane Smith
    Senior Fullstack Developer with 6+ years of experience building web applications.
    Core Skills: Python, FastAPI, Docker, TypeScript, React, PostgreSQL.
    Location: Berlin, Germany (Open to Remote).
    """
    profile = _fallback_heuristic_extraction(sample_text)
    assert profile.full_name.startswith("Jane Smith")
    assert profile.experience_years == 6.0
    assert "Python" in profile.skills
    assert "FastAPI" in profile.skills
    assert "Docker" in profile.skills


@pytest.mark.asyncio
async def test_extract_profile_from_text_fallback() -> None:
    """Test async extract_profile_from_text without LLM."""
    sample_text = "Alice Developer\nBackend Engineer with 4 years experience in Python and Kubernetes."
    profile = await extract_profile_from_text(sample_text, ai_client=None)
    assert profile.experience_years == 4.0
    assert "Python" in profile.skills


def test_save_profile_to_db() -> None:
    """Test saving extracted profile to SQLite database."""
    profile = ExtractedProfile(
        full_name="Bob Engineer",
        summary="Experienced backend engineer",
        skills=["Python", "FastAPI", "Redis"],
        experience_years=5.0,
        target_titles=["Backend Engineer", "Senior Developer"],
        target_locations=["Remote"],
        target_salary_min=85000.0,
    )

    with Session(engine) as session:
        saved = save_profile_to_db(profile, "Raw resume text...", session)
        assert saved.id is not None
        assert saved.full_name == "Bob Engineer"
        assert "Redis" in saved.skills_json
        assert saved.target_salary_min == 85000.0
