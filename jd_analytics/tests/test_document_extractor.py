import pytest
from app.exceptions import DocumentEmptyError, MalformedDocumentError, ScannedPDFError
from app.services.document_extractor import DocumentExtractor, normalize_whitespace


def test_normalize_whitespace():
    raw = "Line 1   \r\n\r\n\r\n   Line 2\t\twith tabs\n\n\n\nLine 3"
    result = normalize_whitespace(raw)
    assert "Line 1\n\nLine 2    with tabs\n\nLine 3" == result


def test_valid_pdf_extraction(make_pdf):
    content = make_pdf(["Page 1: Senior Software Engineer at TechCorp.\nMust know Python and Docker."])
    text, meta = DocumentExtractor.extract_from_bytes(content, ".pdf")
    assert "Senior Software Engineer at TechCorp." in text
    assert "Must know Python and Docker." in text
    assert meta["pages"] == "1"


def test_multi_page_pdf_extraction(make_pdf):
    content = make_pdf([
        "Page 1: Company Overview and Requirements.\nProficiency in SQL required.",
        "Page 2: Preferred skills: Kubernetes, AWS, and Distributed Systems."
    ])
    text, meta = DocumentExtractor.extract_from_bytes(content, ".pdf")
    assert "Page 1" in text
    assert "Page 2" in text
    assert "Proficiency in SQL required." in text
    assert "Kubernetes, AWS, and Distributed Systems." in text
    assert meta["pages"] == "2"


def test_valid_docx_extraction(make_docx):
    content = make_docx([
        "Role: Full Stack Engineer",
        "Required Skills: JavaScript, TypeScript, and React.",
        "Database: PostgreSQL and MongoDB."
    ])
    text, meta = DocumentExtractor.extract_from_bytes(content, ".docx")
    assert "Role: Full Stack Engineer" in text
    assert "JavaScript, TypeScript, and React" in text
    assert "PostgreSQL and MongoDB" in text


def test_docx_table_extraction(make_docx):
    tables = [
        [
            ["Skill", "Minimum Experience", "Category"],
            ["Python", "3 Years", "Coding"],
            ["PostgreSQL", "2 Years", "Database"]
        ]
    ]
    content = make_docx(["Job Description Details:"], tables_data=tables)
    text, _ = DocumentExtractor.extract_from_bytes(content, ".docx")
    assert "Python" in text
    assert "PostgreSQL" in text
    assert "Coding" in text


def test_empty_pdf(make_pdf):
    content = make_pdf([""])
    with pytest.raises((DocumentEmptyError, ScannedPDFError)):
        DocumentExtractor.extract_from_bytes(content, ".pdf")


def test_empty_docx(make_docx):
    content = make_docx([])
    with pytest.raises(DocumentEmptyError):
        DocumentExtractor.extract_from_bytes(content, ".docx")


def test_malformed_pdf():
    corrupted_bytes = b"%PDF-1.4\n%not a real pdf content junk random data"
    with pytest.raises(MalformedDocumentError):
        DocumentExtractor.extract_from_bytes(corrupted_bytes, ".pdf")


def test_malformed_docx():
    corrupted_bytes = b"PK\x03\x04corrupted zip archive content that cannot be opened"
    with pytest.raises(MalformedDocumentError):
        DocumentExtractor.extract_from_bytes(corrupted_bytes, ".docx")


def test_scanned_pdf_detection(make_scanned_pdf):
    content = make_scanned_pdf()
    with pytest.raises(ScannedPDFError) as exc_info:
        DocumentExtractor.extract_from_bytes(content, ".pdf")
    assert "OCR" in str(exc_info.value.message)
    assert exc_info.value.code == "SCANNED_PDF_UNSUPPORTED"
