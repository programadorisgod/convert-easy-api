"""Domain events for job lifecycle.

Events are immutable records of things that happened in the domain.
They allow event sourcing: reconstructing aggregate state from event history.
"""

from pydantic import model_validator
from shared.events import DomainEvent


class JobEvent(DomainEvent):
    """Base class for all job-related events."""

    job_id: str

    @model_validator(mode="before")
    @classmethod
    def set_aggregate_id_from_job_id(cls, data):
        """Automatically set aggregate_id from job_id."""
        if isinstance(data, dict):
            # If aggregate_id is not set, use job_id
            if "aggregate_id" not in data or not data.get("aggregate_id"):
                data["aggregate_id"] = data.get("job_id")
        return data


class JobCreated(JobEvent):
    """Event: A new conversion job was created."""

    event_type: str = "job.created"
    file_id: str
    input_format: str
    output_format: str
    file_size_bytes: int = 0
    total_chunks: int = 1

    @classmethod
    def create(
        cls,
        job_id: str,
        file_id: str,
        input_format: str,
        output_format: str,
        file_size_bytes: int = 0,
        total_chunks: int = 1,
    ) -> "JobCreated":
        """Factory method to create event."""
        return cls(
            job_id=job_id,
            file_id=file_id,
            input_format=input_format,
            output_format=output_format,
            file_size_bytes=file_size_bytes,
            total_chunks=total_chunks,
            data={
                "file_id": file_id,
                "input_format": input_format,
                "output_format": output_format,
                "file_size_bytes": file_size_bytes,
                "total_chunks": total_chunks,
            },
        )


class ChunkUploaded(JobEvent):
    """Event: A file chunk was uploaded."""

    event_type: str = "job.chunk_uploaded"
    chunk_index: int
    total_chunks: int
    chunk_size_bytes: int

    @classmethod
    def create(
        cls,
        job_id: str,
        file_id: str,
        chunk_index: int,
        total_chunks: int,
        chunk_size_bytes: int,
    ) -> "ChunkUploaded":
        """Factory method to create event."""
        return cls(
            job_id=job_id,
            file_id=file_id,
            chunk_index=chunk_index,
            total_chunks=total_chunks,
            chunk_size_bytes=chunk_size_bytes,
            data={
                "file_id": file_id,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "chunk_size_bytes": chunk_size_bytes,
            },
        )


class JobStarted(JobEvent):
    """Event: Job processing started by worker."""

    event_type: str = "job.started"
    worker_id: str | None = None

    @classmethod
    def create(
        cls,
        job_id: str,
        worker_id: str | None = None,
    ) -> "JobStarted":
        """Factory method to create event."""
        return cls(job_id=job_id, worker_id=worker_id, data={"worker_id": worker_id})


class JobCompleted(JobEvent):
    """Event: Job completed successfully."""

    event_type: str = "job.completed"
    output_file_path: str
    output_size_bytes: int
    processing_time_seconds: float

    @classmethod
    def create(
        cls,
        job_id: str,
        output_file_path: str,
        output_size_bytes: int,
        processing_time_seconds: float,
    ) -> "JobCompleted":
        """Factory method to create event."""
        return cls(
            job_id=job_id,
            output_file_path=output_file_path,
            output_size_bytes=output_size_bytes,
            processing_time_seconds=processing_time_seconds,
            data={
                "output_file_path": output_file_path,
                "output_size_bytes": output_size_bytes,
                "processing_time_seconds": processing_time_seconds,
            },
        )


class JobFailed(JobEvent):
    """Event: Job processing failed."""

    event_type: str = "job.failed"
    error_message: str
    error_code: str | None = None
    retry_count: int = 0

    @classmethod
    def create(
        cls,
        job_id: str,
        error_message: str,
        error_code: str | None = None,
        retry_count: int = 0,
    ) -> "JobFailed":
        """Factory method to create event."""
        return cls(
            job_id=job_id,
            error_message=error_message,
            error_code=error_code,
            retry_count=retry_count,
            data={
                "error_message": error_message,
                "error_code": error_code,
                "retry_count": retry_count,
            },
        )


class JobCancelled(JobEvent):
    """Event: Job was cancelled by user."""

    event_type: str = "job.cancelled"
    reason: str | None = None

    @classmethod
    def create(
        cls,
        job_id: str,
        reason: str | None = None,
    ) -> "JobCancelled":
        """Factory method to create event."""
        return cls(job_id=job_id, reason=reason, data={"reason": reason})
