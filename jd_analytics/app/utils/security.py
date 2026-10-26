import os
import re
from typing import Tuple
from app.exceptions import FileSizeExceededError, UnsupportedFileTypeError


# Magic bytes signatures
PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"  # DOCX files are standard OpenXML zip containers


def sanitize_filename(filename: str, max_length: int = 150) -> str:
    """
    Sanitize an uploaded filename for safe display and metadata storage.
    NEVER use client-supplied filenames directly in filesystem paths.
    Strips directory traversal sequences, control characters, and dangerous characters.
    """
    if not filename:
        return "unnamed_document.pdf"

    # Replace backslashes with forward slashes so basename handles Windows paths portably
    normalized = filename.replace("\\", "/")
    base = os.path.basename(normalized)
    
    # Remove null bytes and control chars
    cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", base)
    
    # Replace path separators
    cleaned = cleaned.replace("/", "_")
    
    # Replace problematic filesystem characters
    cleaned = re.sub(r'["\'<>:|?*]', "_", cleaned)
    
    # Collapse consecutive whitespace characters to a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    
    if not cleaned or cleaned.startswith("."):
        cleaned = f"document_{cleaned}".strip("_")
        
    if len(cleaned) > max_length:
        name_parts = os.path.splitext(cleaned)
        ext = name_parts[1][:10]
        cleaned = name_parts[0][:max_length - len(ext)] + ext

    return cleaned or "document"


def validate_file_upload(filename: str, content: bytes, max_size_bytes: int) -> Tuple[str, str]:
    """
    Validates file extension, upload size, and binary magic bytes.
    Returns (sanitized_filename, detected_extension) or raises specific exceptions.
    """
    safe_name = sanitize_filename(filename)
    ext = os.path.splitext(safe_name)[1].lower()

    if ext not in [".pdf", ".docx"]:
        raise UnsupportedFileTypeError(
            f"Unsupported file extension '{ext}'. Only .pdf and .docx documents are accepted."
        )

    if len(content) > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise FileSizeExceededError(
            f"File size ({len(content) / (1024 * 1024):.2f} MB) exceeds maximum allowed limit of {max_mb:.1f} MB."
        )

    # Magic byte header validation
    if ext == ".pdf":
        if not content.startswith(PDF_MAGIC):
            raise UnsupportedFileTypeError("Invalid PDF: File does not start with valid PDF magic bytes.")
    elif ext == ".docx":
        if not content.startswith(ZIP_MAGIC):
            raise UnsupportedFileTypeError("Invalid DOCX: File is not a valid OpenXML document container.")

    return safe_name, ext


def sanitize_prompt_text(text: str, max_chars: int = 50000) -> str:
    """
    Prepares extracted job description text for LLM ingestion.
    Enforces maximum character length and provides isolation against prompt injection.
    """
    if not text:
        return ""
    
    truncated = text[:max_chars]
    
    # Remove null bytes and dangerous control characters
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", truncated)
    return sanitized
