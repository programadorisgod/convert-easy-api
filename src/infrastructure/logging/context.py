"""Logging context for request correlation."""

from contextvars import ContextVar

# Current request ID for correlation across log messages
request_id_ctx: ContextVar[str] = ContextVar("request_id_ctx", default="")
job_id_ctx: ContextVar[str] = ContextVar("job_id_ctx", default="")


def set_request_id(request_id: str) -> None:
    """Set the current request ID."""
    request_id_ctx.set(request_id)


def get_request_id() -> str:
    """Get the current request ID, or empty string."""
    return request_id_ctx.get()


def set_job_id(job_id: str) -> None:
    """Set the current job ID."""
    job_id_ctx.set(job_id)


def get_job_id() -> str:
    """Get the current job ID, or empty string."""
    return job_id_ctx.get()
