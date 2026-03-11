"""Job aggregate root - the heart of the domain model.

Implements Event Sourcing: the Job's state is derived from its event history.
This provides a complete audit trail and enables time-travel debugging.

Following DDD principles:
- Job is the aggregate root
- All state changes happen through domain events
- Business rules are enforced here, not in infrastructure
"""

from datetime import datetime, timezone
from typing import Any

from .job_status import JobStatus
from .job_events import (
    JobEvent,
    JobCreated,
    ChunkUploaded,
    JobStarted,
    JobCompleted,
    JobFailed,
    JobCancelled,
)


class Job:
    """Job aggregate root with event sourcing.

    The Job represents a file conversion request. Its state is completely
    determined by the sequence of events that have been applied to it.
    """

    def __init__(self, job_id: str):
        """Initialize a new Job aggregate.

        Args:
            job_id: Unique job identifier
        """
        # Identity
        self.job_id = job_id

        # State (derived from events)
        self.status = JobStatus.PENDING
        self.file_id: str | None = None
        self.input_format: str | None = None
        self.output_format: str | None = None
        self.file_size_bytes: int = 0
        self.output_file_path: str | None = None
        self.output_size_bytes: int = 0
        self.error_message: str | None = None
        self.worker_id: str | None = None
        self.processing_time_seconds: float = 0.0
        self.chunks_uploaded: int = 0
        self.total_chunks: int = 0
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = datetime.now(timezone.utc)

        # Event tracking
        self._events: list[JobEvent] = []
        self._version = 0

    def apply_event(self, event: JobEvent) -> None:
        """Apply an event to update aggregate state.

        This is the ONLY way to change the Job's state.
        All mutations must go through events.

        Args:
            event: Domain event to apply
        """
        # Route event to specific handler
        handler_name = f"_apply_{event.event_type.replace('.', '_')}"
        handler = getattr(self, handler_name, None)

        if handler is None:
            raise ValueError(f"No handler for event type: {event.event_type}")

        handler(event)
        self._version += 1
        self.updated_at = event.timestamp

    def add_event(self, event: JobEvent) -> None:
        """Add a new event and apply it.

        Args:
            event: Domain event to add and apply
        """
        self._events.append(event)
        self.apply_event(event)

    def get_uncommitted_events(self) -> list[JobEvent]:
        """Get events that haven't been persisted yet."""
        return self._events.copy()

    def clear_events(self) -> None:
        """Clear uncommitted events after persistence."""
        self._events.clear()

    # Event handlers (state mutations)

    def _apply_job_created(self, event: JobCreated) -> None:
        """Apply JobCreated event."""
        self.file_id = event.file_id
        self.input_format = event.input_format
        self.output_format = event.output_format
        self.file_size_bytes = event.file_size_bytes
        self.total_chunks = event.total_chunks
        self.status = JobStatus.PENDING
        self.created_at = event.timestamp

    def _apply_job_chunk_uploaded(self, event: ChunkUploaded) -> None:
        """Apply ChunkUploaded event."""
        self.chunks_uploaded = event.chunk_index + 1
        self.total_chunks = event.total_chunks
        self.status = JobStatus.UPLOADING

    def _apply_job_started(self, event: JobStarted) -> None:
        """Apply JobStarted event."""
        self.status = JobStatus.PROCESSING
        self.worker_id = event.worker_id

    def _apply_job_completed(self, event: JobCompleted) -> None:
        """Apply JobCompleted event."""
        self.status = JobStatus.COMPLETED
        self.output_file_path = event.output_file_path
        self.output_size_bytes = event.output_size_bytes
        self.processing_time_seconds = event.processing_time_seconds

    def _apply_job_failed(self, event: JobFailed) -> None:
        """Apply JobFailed event."""
        self.status = JobStatus.FAILED
        self.error_message = event.error_message

    def _apply_job_cancelled(self, event: JobCancelled) -> None:
        """Apply JobCancelled event."""
        self.status = JobStatus.CANCELLED
        self.error_message = event.reason

    # Business logic methods

    def can_upload_chunks(self) -> bool:
        """Check if job can accept chunk uploads."""
        return self.status in (JobStatus.PENDING, JobStatus.UPLOADING)

    def can_start_processing(self) -> bool:
        """Check if job is ready to start processing."""
        return self.status in (JobStatus.PENDING, JobStatus.UPLOADING)

    def can_cancel(self) -> bool:
        """Check if job can be cancelled."""
        return not self.status.is_terminal()

    def is_complete(self) -> bool:
        """Check if job is in a final state."""
        return self.status.is_terminal()

    def all_chunks_uploaded(self) -> bool:
        """Check if all expected chunks have been uploaded."""
        if self.total_chunks == 0:
            return True  # No chunks expected (direct upload)
        return self.chunks_uploaded >= self.total_chunks

    def to_dict(self) -> dict[str, Any]:
        """Serialize job state to dictionary."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "file_id": self.file_id,
            "input_format": self.input_format,
            "output_format": self.output_format,
            "file_size_bytes": self.file_size_bytes,
            "output_file_path": self.output_file_path,
            "output_size_bytes": self.output_size_bytes,
            "error_message": self.error_message,
            "worker_id": self.worker_id,
            "processing_time_seconds": self.processing_time_seconds,
            "chunks_uploaded": self.chunks_uploaded,
            "total_chunks": self.total_chunks,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self._version,
        }

    @classmethod
    def from_events(cls, job_id: str, events: list[JobEvent]) -> "Job":
        """Reconstruct Job aggregate from event history.

        This is the essence of event sourcing: state is derived from events.

        Args:
            job_id: Job identifier
            events: Ordered list of events to apply

        Returns:
            Reconstructed Job instance
        """
        job = cls(job_id)
        for event in events:
            job.apply_event(event)
        return job
