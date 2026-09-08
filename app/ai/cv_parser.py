"""Secure document parsing for candidate resumes (PDF, DOCX, TXT)."""

import io
import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional
import pdfplumber
import pypdf

logger = logging.getLogger("jobot.ai.cv_parser")

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB limit (STRIDE T-02)
PDF_MAGIC_BYTES = b"%PDF-"
DOCX_MAGIC_BYTES = b"PK\x03\x04"


class CVParser:
    """Extracts clean plain text from uploaded CV documents with security validations."""

    def __init__(self, max_file_size: int = MAX_FILE_SIZE) -> None:
        self.max_file_size = max_file_size

    def validate_file(self, file_bytes: bytes, filename: str) -> str:
        """Validate file size and magic bytes against supported extensions."""
        if len(file_bytes) > self.max_file_size:
            raise ValueError(
                f"File size exceeds maximum limit of {self.max_file_size // (1024 * 1024)}MB"
            )

        filename_lower = filename.lower()
        if filename_lower.endswith(".pdf"):
            if not file_bytes.startswith(PDF_MAGIC_BYTES):
                raise ValueError("Invalid PDF file format: missing '%PDF-' header signature")
            return "pdf"
        elif filename_lower.endswith(".docx"):
            if not file_bytes.startswith(DOCX_MAGIC_BYTES):
                raise ValueError("Invalid DOCX file format: missing ZIP magic bytes")
            return "docx"
        elif filename_lower.endswith(".txt"):
            return "txt"
        else:
            raise ValueError(
                f"Unsupported file format: {filename}. Supported formats are .pdf, .docx, .txt"
            )

    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF using pdfplumber with fallback to pypdf."""
        text_chunks: list[str] = []

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    page_text = page.extract_text(layout=True) or ""
                    if not page_text.strip():
                        # Fallback to standard text extraction
                        page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_chunks.append(page_text)
        except Exception as err:
            logger.warning("pdfplumber extraction failed (%s), falling back to pypdf", err)
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        text_chunks.append(page_text)
            except Exception as pypdf_err:
                raise ValueError(f"Failed to extract text from PDF: {pypdf_err}") from pypdf_err

        return "\n\n".join(text_chunks)

    def extract_text_from_docx(self, file_bytes: bytes) -> str:
        """Extract text from DOCX document XML without requiring external heavy dependencies."""
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                xml_content = z.read("word/document.xml")
                tree = ET.fromstring(xml_content)
                # Word XML namespaces
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                paragraphs = []
                for p in tree.findall(".//w:p", ns):
                    texts = [t.text for t in p.findall(".//w:t", ns) if t.text]
                    if texts:
                        paragraphs.append("".join(texts))
                return "\n\n".join(paragraphs)
        except Exception as err:
            raise ValueError(f"Failed to extract text from DOCX: {err}") from err

    def clean_text(self, text: str) -> str:
        """Sanitize non-printable characters, normalize whitespace and newlines."""
        if not text:
            return ""

        # Remove null bytes and non-printable control characters (except \n, \r, \t)
        text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Collapse excess empty lines (max 2 consecutive newlines)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Strip trailing/leading spaces per line
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    def extract_text_from_bytes(self, file_bytes: bytes, filename: str) -> str:
        """Extract and clean plain text from document bytes."""
        file_type = self.validate_file(file_bytes, filename)

        if file_type == "pdf":
            raw_text = self.extract_text_from_pdf(file_bytes)
        elif file_type == "docx":
            raw_text = self.extract_text_from_docx(file_bytes)
        elif file_type == "txt":
            raw_text = file_bytes.decode("utf-8", errors="replace")
        else:
            raw_text = ""

        cleaned = self.clean_text(raw_text)
        if not cleaned:
            logger.warning("Extracted text from %s is empty", filename)
        return cleaned
