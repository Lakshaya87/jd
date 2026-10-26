from typing import Optional


class JDAnalyticsError(Exception):
    """Base exception for JD Analytics errors."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500, field: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.field = field


class FileSizeExceededError(JDAnalyticsError):
    """Raised when an uploaded document exceeds the configured size limit (413)."""
    def __init__(self, message: str = "Uploaded file exceeds maximum allowed size"):
        super().__init__(message=message, code="FILE_TOO_LARGE", status_code=413, field="file")


class UnsupportedFileTypeError(JDAnalyticsError):
    """Raised when file extension or magic header is unsupported (415)."""
    def __init__(self, message: str = "Unsupported file type. Only .pdf and .docx files are accepted"):
        super().__init__(message=message, code="UNSUPPORTED_MEDIA_TYPE", status_code=415, field="file")


class DocumentEmptyError(JDAnalyticsError):
    """Raised when document contains no text content (400)."""
    def __init__(self, message: str = "Uploaded document contains no readable text"):
        super().__init__(message=message, code="EMPTY_DOCUMENT", status_code=400, field="file")


class MalformedDocumentError(JDAnalyticsError):
    """Raised when file is corrupted, malformed, or unreadable (400)."""
    def __init__(self, message: str = "Document is corrupted or cannot be parsed"):
        super().__init__(message=message, code="MALFORMED_DOCUMENT", status_code=400, field="file")


class ScannedPDFError(JDAnalyticsError):
    """Raised when a PDF appears to be a scanned image with no embedded text (400)."""
    def __init__(
        self,
        message: str = (
            "Document appears to be a scanned image-only PDF with no extractable text layer. "
            "OCR (Optical Character Recognition) is currently unsupported. "
            "Please upload a text-based PDF or DOCX file."
        )
    ):
        super().__init__(message=message, code="SCANNED_PDF_UNSUPPORTED", status_code=400, field="file")


class ExtractionServiceUnavailableError(JDAnalyticsError):
    """Raised when LLM extraction is required but unavailable and fallback is disabled (503)."""
    def __init__(self, message: str = "Extraction service is unavailable and fallback is disabled"):
        super().__init__(message=message, code="SERVICE_UNAVAILABLE", status_code=503)


class ContractValidationError(JDAnalyticsError):
    """Raised when the generated or submitted response violates the shared RADIX contract (422)."""
    def __init__(self, message: str = "Response payload violates the shared contract specification"):
        super().__init__(message=message, code="CONTRACT_VALIDATION_ERROR", status_code=422)
