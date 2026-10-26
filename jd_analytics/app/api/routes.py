import logging
from typing import Any, Dict
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app import __version__
from app.config import settings
from app.exceptions import (
    ContractValidationError,
    DocumentEmptyError,
    FileSizeExceededError,
    JDAnalyticsError,
    MalformedDocumentError,
    ScannedPDFError,
    UnsupportedFileTypeError,
)
from app.schemas import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    JobDescriptionResponse,
    ModuleReadinessResponse,
    ValidationFailureResponse,
    ValidationSuccessResponse,
)
from app.services.document_extractor import DocumentExtractor
from app.services.jd_analyzer import JobDescriptionAnalyzer
from app.utils.security import sanitize_prompt_text, validate_file_upload

logger = logging.getLogger("jd_analytics")

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Lightweight service health check",
    tags=["Health"]
)
async def service_health():
    """
    Returns immediate status of the JD Analytics service.
    Requires no authentication, credentials, or file payloads.
    """
    return HealthResponse(
        status="healthy",
        version=__version__,
        service="jd-analytics"
    )


@router.get(
    "/api/v1/jd-analytics/health",
    response_model=ModuleReadinessResponse,
    summary="Detailed module readiness check",
    tags=["Health"]
)
async def module_health():
    """
    Returns readiness information including supported formats, upload limits,
    and LLM configuration state without exposing any secrets or keys.
    """
    llm_configured = bool(settings.llm_enabled and settings.llm_api_key)
    readiness_status = "ready" if (llm_configured or settings.allow_deterministic_fallback) else "degraded"

    return ModuleReadinessResponse(
        status=readiness_status,
        service="jd-analytics",
        version=__version__,
        llm_enabled=settings.llm_enabled,
        llm_provider=settings.llm_provider,
        llm_configured=llm_configured,
        deterministic_fallback_enabled=settings.allow_deterministic_fallback,
        supported_formats=["pdf", "docx"],
        max_upload_size_mb=settings.max_upload_size_mb
    )


@router.post(
    "/api/v1/jd-analytics/analyze",
    response_model=JobDescriptionResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"model": JobDescriptionResponse, "description": "Successful extraction following the shared contract"},
        400: {"model": ErrorResponse, "description": "Invalid, unreadable, or empty document"},
        413: {"model": ErrorResponse, "description": "File upload exceeds size limit"},
        415: {"model": ErrorResponse, "description": "Unsupported document format (only PDF and DOCX supported)"},
        422: {"model": ErrorResponse, "description": "Unprocessable entity or contract violation"},
        500: {"model": ErrorResponse, "description": "Unexpected internal error without stack traces"},
        503: {"model": ErrorResponse, "description": "Extraction service unavailable and fallback disabled"}
    },
    summary="Analyze Job Description file (PDF/DOCX)",
    tags=["JD Analytics"]
)
async def analyze_job_description(
    file: UploadFile = File(..., description="Job Description document in PDF or DOCX format")
):
    """
    Accepts a job description file via multipart/form-data with field name 'file'.
    Extracts text, identifies required and preferred skills, categorizes them according
    to the 13 RADIX category codes, and returns validated structured JSON conforming to the
    mandatory shared contract.
    """
    raw_filename = file.filename or "unknown.pdf"
    
    # 1. Read file content safely in memory
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file stream: {str(e)}")
        raise MalformedDocumentError("Could not read uploaded file content.")

    # 2. Security validation: Size, extension, and magic bytes
    safe_filename, extension = validate_file_upload(
        filename=raw_filename,
        content=content,
        max_size_bytes=settings.max_upload_size_bytes
    )

    # 3. Document text extraction
    extracted_text, metadata = DocumentExtractor.extract_from_bytes(content, extension)

    # 4. Prompt text sanitization and length check
    sanitized_text = sanitize_prompt_text(
        extracted_text,
        max_chars=settings.max_extracted_text_length
    )

    if not sanitized_text.strip():
        raise DocumentEmptyError("Document contains no readable text content.")

    # 5. Semantic skill extraction and analysis
    analyzer = JobDescriptionAnalyzer()
    result = await analyzer.analyze(
        text=sanitized_text,
        filename=safe_filename,
        doc_metadata=metadata
    )

    return result


@router.post(
    "/api/v1/jd-analytics/validate",
    summary="Validate a candidate JSON payload against the shared JD contract",
    responses={
        200: {"model": ValidationSuccessResponse, "description": "Payload is strictly valid"},
        422: {"model": ValidationFailureResponse, "description": "Payload violates the contract"}
    },
    tags=["Validation"]
)
async def validate_jd_payload(payload: Dict[str, Any]):
    """
    Validates any arbitrary JSON object against the mandatory RADIX Job Description contract.
    Ensures:
      - source_type == 'jd'
      - valid category_code from the authorized 13 RADIX codes
      - confidence is high, medium, or low
      - all 4 required skill fields exist
      - no invalid fields or structure
    """
    try:
        validated = JobDescriptionResponse.model_validate(payload)
        
        categories = sorted(list({
            s.category_code if isinstance(s.category_code, str) else s.category_code.value
            for s in validated.skills
        }))
        return ValidationSuccessResponse(
            valid=True,
            message="Job description payload conforms strictly to the RADIX contract.",
            skill_count=len(validated.skills),
            categories_present=categories
        )
    except ValidationError as e:
        formatted_errors = []
        for err in e.errors():
            formatted_errors.append({
                "loc": err.get("loc"),
                "msg": err.get("msg"),
                "type": err.get("type")
            })
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ValidationFailureResponse(
                valid=False,
                message="Job description payload failed validation against the shared contract.",
                errors=formatted_errors
            ).model_dump()
        )
