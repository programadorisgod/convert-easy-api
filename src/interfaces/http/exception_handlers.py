"""Exception handlers for HTTP API.

Converts domain exceptions to appropriate HTTP responses while preventing
information disclosure of internal paths, tool stderr, or tracebacks.
"""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

from shared.exceptions import (
    AppError,
    ValidationError,
    UnsupportedFormatError,
    FileSizeLimitError,
    JobNotFoundError,
    ProcessingError,
    ChunkAssemblyError,
    RateLimitError,
    FileCorruptedError,
)


logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> str:
    """Extract request_id from request state or header."""
    return getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID", "")


def _create_error_response(
    request: Request,
    status_code: int,
    error_code: str,
    user_message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Create standardized error response."""
    request_id = _get_request_id(request)
    response_headers = dict(headers or {})
    if request_id:
        response_headers["X-Request-ID"] = request_id

    content = {
        "error": error_code,
        "message": user_message,
        "request_id": request_id,
    }
    return JSONResponse(status_code=status_code, content=content, headers=response_headers)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle all domain AppError exceptions."""
    req_id = _get_request_id(request)
    if exc.status_code >= 500:
        logger.error(
            f"Server AppError [{req_id}] {exc.error_code}: {exc.user_message} | "
            f"Technical details: {exc.technical_details}",
            exc_info=True,
        )
    else:
        logger.warning(
            f"Client AppError [{req_id}] {exc.error_code}: {exc.user_message} | "
            f"Technical details: {exc.technical_details}"
        )

    return _create_error_response(
        request=request,
        status_code=exc.status_code,
        error_code=exc.error_code,
        user_message=exc.user_message,
        headers=exc.headers,
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all other uncaught unexpected errors."""
    req_id = _get_request_id(request)
    logger.error(f"Uncaught unexpected error [{req_id}]: {exc}", exc_info=True)
    return _create_error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_SERVER_ERROR",
        user_message="An unexpected error occurred while processing your request. Please try again or contact support.",
    )


def register_exception_handlers(app):
    """Register all exception handlers with the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(ValidationError, app_error_handler)
    app.add_exception_handler(UnsupportedFormatError, app_error_handler)
    app.add_exception_handler(FileSizeLimitError, app_error_handler)
    app.add_exception_handler(JobNotFoundError, app_error_handler)
    app.add_exception_handler(ProcessingError, app_error_handler)
    app.add_exception_handler(ChunkAssemblyError, app_error_handler)
    app.add_exception_handler(RateLimitError, app_error_handler)
    app.add_exception_handler(FileCorruptedError, app_error_handler)
    app.add_exception_handler(Exception, generic_error_handler)
