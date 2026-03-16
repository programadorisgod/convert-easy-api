"""Custom exceptions for Easy Convert API.

Following Clean Code principles: exceptions should be meaningful and
specific to the domain, not generic technical errors.
"""

from fastapi import HTTPException, status


class ValidationError(HTTPException):
    """Raised when request validation fails."""

    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class JobNotFoundError(HTTPException):
    """Raised when a job cannot be found."""

    def __init__(self, job_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found or expired",
        )


class ProcessingError(HTTPException):
    """Raised when file processing fails."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {detail}",
        )


class UnsupportedFormatError(HTTPException):
    """Raised when file format is not supported."""

    def __init__(self, format_name: str, supported_formats: list[str] | None = None):
        detail = f"Format '{format_name}' not supported."
        if supported_formats:
            detail += f" Supported formats: {', '.join(supported_formats)}"

        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


class FileSizeLimitError(HTTPException):
    """Raised when uploaded file exceeds size limit."""

    def __init__(self, size_mb: float, limit_mb: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size {size_mb:.2f}MB exceeds limit of {limit_mb}MB",
        )


class ChunkAssemblyError(HTTPException):
    """Raised when chunk assembly fails."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chunk assembly failed: {detail}",
        )


class RateLimitError(HTTPException):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
