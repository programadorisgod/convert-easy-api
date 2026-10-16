"""Custom exceptions for Easy Convert API.

Following Clean Code principles: exceptions should be meaningful and
specific to the domain, not generic technical errors.
"""

import re
from fastapi import HTTPException, status


def sanitize_user_error_message(raw_message: str | None) -> str:
    """Sanitize technical error messages into safe, user-friendly messages.

    Guarantees no internal paths (/tmp/, /app/), C library internals,
    tool command outputs or tracebacks are exposed to the user.
    """
    if not raw_message:
        return "An internal error occurred while processing the file."

    msg = str(raw_message).strip()

    # Detect technical leakage (file paths, C source files, subprocess errors, tracebacks)
    has_leakage = (
        bool(re.search(r"(/tmp/|/app/|/etc/|[a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+\.(?:c|h|py|cpp)\b)", msg))
        or bool(re.search(r"\b(magick:|ffmpeg|WriteBlob|OpenBlob|Traceback|File \")", msg, re.IGNORECASE))
        or "@ warning/" in msg
        or "@ error/" in msg
    )

    if has_leakage:
        if "no encode delegate" in msg.lower() or "unsupported" in msg.lower():
            return "The selected conversion format is currently not supported for this file."
        return "An internal processing error occurred while converting the file."

    # Strip repeated HTTP status and processing prefixes
    msg = re.sub(r"^\d{3}:\s*", "", msg)
    msg = re.sub(r"^(?:Processing failed:\s*)+", "", msg, flags=re.IGNORECASE)
    msg = re.sub(r"^(?:Conversion failed:\s*)+", "", msg, flags=re.IGNORECASE)
    msg = re.sub(r"^(?:Image conversion failed:\s*)+", "", msg, flags=re.IGNORECASE)
    msg = re.sub(r"^(?:Job processing failed:\s*)+", "", msg, flags=re.IGNORECASE)
    msg = re.sub(r"^\d{3}:\s*", "", msg)

    return msg.strip() or "File processing failed."


class AppError(HTTPException):
    """Base application exception with clean user message and technical details."""

    def __init__(
        self,
        status_code: int,
        user_message: str,
        error_code: str,
        technical_details: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(status_code=status_code, detail=user_message, headers=headers)
        self.status_code = status_code
        self.user_message = user_message
        self.error_code = error_code
        self.technical_details = technical_details or user_message

    def __str__(self) -> str:
        return self.user_message


class ValidationError(AppError):
    """Raised when request validation fails."""

    def __init__(self, detail: str, technical_details: str | None = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            user_message=detail,
            error_code="VALIDATION_ERROR",
            technical_details=technical_details,
        )


class JobNotFoundError(AppError):
    """Raised when a job cannot be found."""

    def __init__(self, job_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            user_message=f"Job {job_id} not found or expired",
            error_code="JOB_NOT_FOUND",
            technical_details=f"Job ID '{job_id}' was not found in storage or cache.",
        )


class ProcessingError(AppError):
    """Raised when file processing fails."""

    def __init__(
        self,
        detail: str,
        technical_details: str | None = None,
        user_message: str | None = None,
    ):
        raw_tech = technical_details or detail
        clean_user = user_message or sanitize_user_error_message(detail)
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            user_message=clean_user,
            error_code="PROCESSING_ERROR",
            technical_details=raw_tech,
        )


class UnsupportedFormatError(AppError):
    """Raised when file format is not supported."""

    def __init__(self, format_name: str, supported_formats: list[str] | None = None):
        detail = f"Format '{format_name}' not supported."
        if supported_formats:
            detail += f" Supported formats: {', '.join(supported_formats)}"

        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            user_message=detail,
            error_code="UNSUPPORTED_FORMAT",
            technical_details=f"Requested format: '{format_name}'. Supported: {supported_formats}",
        )


class FileSizeLimitError(AppError):
    """Raised when uploaded file exceeds size limit."""

    def __init__(self, size_mb: float, limit_mb: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            user_message=f"File size {size_mb:.2f}MB exceeds limit of {limit_mb}MB",
            error_code="FILE_TOO_LARGE",
            technical_details=f"File size {size_mb}MB exceeded limit {limit_mb}MB.",
        )


class ChunkAssemblyError(AppError):
    """Raised when chunk assembly fails."""

    def __init__(self, detail: str, technical_details: str | None = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            user_message=sanitize_user_error_message(detail),
            error_code="CHUNK_ASSEMBLY_ERROR",
            technical_details=technical_details or detail,
        )


class RateLimitError(AppError):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            user_message="Rate limit exceeded. Please wait a moment before trying again.",
            error_code="RATE_LIMIT_EXCEEDED",
            technical_details=f"Rate limit exceeded. Retry-After: {retry_after}s",
            headers={"Retry-After": str(retry_after)},
        )


class FileCorruptedError(AppError):
    """Raised when uploaded file is corrupted or cannot be decoded."""

    def __init__(self, detail: str, technical_details: str | None = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            user_message=sanitize_user_error_message(detail),
            error_code="FILE_CORRUPTED",
            technical_details=technical_details or detail,
        )
