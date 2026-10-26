import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app import __version__
from app.api.routes import router
from app.config import settings
from app.exceptions import JDAnalyticsError
from app.schemas import ErrorDetail, ErrorResponse
from app.utils.logging_config import setup_logging

# Setup privacy-preserving logging
logger = setup_logging(settings.log_level)


def create_application() -> FastAPI:
    app = FastAPI(
        title="RADIX JD Analytics Service",
        description=(
            "Role 1: Job Description Analytics module for RADIX Talent Match Hackathon. "
            "Accepts PDF/DOCX job descriptions, extracts text and metadata, identifies skills, "
            "categorizes them into standard RADIX categories, and outputs validated structured JSON."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # Enable CORS for local React development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handler: Domain-specific JD Analytics Errors
    @app.exception_handler(JDAnalyticsError)
    async def handle_jd_analytics_error(request: Request, exc: JDAnalyticsError):
        logger.warning(f"Handled JDAnalyticsError [{exc.code}] on {request.url.path}: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code=exc.code,
                    message=exc.message,
                    field=exc.field
                )
            ).model_dump()
        )

    # Exception Handler: FastAPI Request Validation Errors (e.g. missing file form field)
    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(request: Request, exc: RequestValidationError):
        logger.warning(f"Request validation error on {request.url.path}: {str(exc.errors())}")
        first_err = exc.errors()[0] if exc.errors() else {}
        loc = first_err.get("loc", [])
        field_name = str(loc[-1]) if loc else "body"
        msg = first_err.get("msg", "Invalid request parameter.")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message=f"Parameter '{field_name}': {msg}",
                    field=field_name
                )
            ).model_dump()
        )

    # Exception Handler: Pydantic Validation Errors
    @app.exception_handler(ValidationError)
    async def handle_pydantic_validation_error(request: Request, exc: ValidationError):
        logger.warning(f"Schema validation error on {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code="SCHEMA_VALIDATION_ERROR",
                    message="Payload failed schema validation requirements.",
                    field="body"
                )
            ).model_dump()
        )

    # Exception Handler: Unexpected internal server errors
    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        # Never expose stack traces, internal paths, or secrets to the client
        logger.error(f"Unexpected unhandled exception on {request.url.path}: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                success=False,
                error=ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected internal server error occurred while processing the request."
                )
            ).model_dump()
        )

    # Mount API routes
    app.include_router(router)

    return app


app = create_application()
