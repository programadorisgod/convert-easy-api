"""Exception handlers for HTTP API.

Converts domain exceptions to appropriate HTTP responses.
"""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

from shared.exceptions import (
    ValidationError,
    UnsupportedFormatError,
    FileSizeLimitError,
    JobNotFoundError,
    ProcessingError,
    ChunkAssemblyError,
    RateLimitError,
)


logger = logging.getLogger(__name__)


async def validation_error_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle validation errors."""
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "ValidationError",
            "message": str(exc),
        },
    )


async def unsupported_format_error_handler(
    request: Request, exc: UnsupportedFormatError
) -> JSONResponse:
    """Handle unsupported format errors."""
    logger.warning(f"Unsupported format: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "UnsupportedFormatError",
            "message": str(exc),
        },
    )


async def file_size_limit_error_handler(
    request: Request, exc: FileSizeLimitError
) -> JSONResponse:
    """Handle file size limit errors."""
    logger.warning(f"File size limit exceeded: {exc}")
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={
            "error": "FileSizeLimitError",
            "message": str(exc),
        },
    )


async def job_not_found_error_handler(
    request: Request, exc: JobNotFoundError
) -> JSONResponse:
    """Handle job not found errors."""
    logger.warning(f"Job not found: {exc}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": "JobNotFoundError",
            "message": str(exc),
        },
    )


async def processing_error_handler(
    request: Request, exc: ProcessingError
) -> JSONResponse:
    """Handle processing errors."""
    logger.error(f"Processing error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "ProcessingError",
            "message": str(exc),
        },
    )


async def chunk_assembly_error_handler(
    request: Request, exc: ChunkAssemblyError
) -> JSONResponse:
    """Handle chunk assembly errors."""
    logger.error(f"Chunk assembly error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "ChunkAssemblyError",
            "message": str(exc),
        },
    )


async def rate_limit_error_handler(
    request: Request, exc: RateLimitError
) -> JSONResponse:
    """Handle rate limit errors."""
    logger.warning(f"Rate limit exceeded: {exc}")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "RateLimitError",
            "message": str(exc),
        },
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other unexpected errors."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


def register_exception_handlers(app):
    """Register all exception handlers with the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(ValidationError, validation_error_handler)
    app.add_exception_handler(UnsupportedFormatError, unsupported_format_error_handler)
    app.add_exception_handler(FileSizeLimitError, file_size_limit_error_handler)
    app.add_exception_handler(JobNotFoundError, job_not_found_error_handler)
    app.add_exception_handler(ProcessingError, processing_error_handler)
    app.add_exception_handler(ChunkAssemblyError, chunk_assembly_error_handler)
    app.add_exception_handler(RateLimitError, rate_limit_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)

    logger.info("Exception handlers registered")
