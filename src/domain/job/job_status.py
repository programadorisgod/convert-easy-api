"""Job status enumeration.

Following Domain-Driven Design: status is a domain concept,
not a technical implementation detail.
"""

from enum import Enum


class JobStatus(str, Enum):
    """Job lifecycle states."""
    
    PENDING = "pending"           # Job created, waiting for file upload
    UPLOADING = "uploading"       # Chunks being uploaded
    QUEUED = "queued"             # Job enqueued for processing
    PROCESSING = "processing"     # Worker is processing the conversion
    COMPLETED = "completed"       # Conversion successful
    FAILED = "failed"             # Conversion failed
    CANCELLED = "cancelled"       # Job cancelled by user
    
    def is_terminal(self) -> bool:
        """Check if this is a terminal state (no further transitions)."""
        return self in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED)
    
    def can_transition_to(self, new_status: "JobStatus") -> bool:
        """Check if transition to new status is valid."""
        valid_transitions = {
            JobStatus.PENDING: {JobStatus.UPLOADING, JobStatus.QUEUED, JobStatus.FAILED},
            JobStatus.UPLOADING: {JobStatus.QUEUED, JobStatus.FAILED},
            JobStatus.QUEUED: {JobStatus.PROCESSING, JobStatus.CANCELLED, JobStatus.FAILED},
            JobStatus.PROCESSING: {JobStatus.COMPLETED, JobStatus.FAILED},
            JobStatus.COMPLETED: set(),  # Terminal state
            JobStatus.FAILED: set(),     # Terminal state
            JobStatus.CANCELLED: set(),  # Terminal state
        }
        return new_status in valid_transitions.get(self, set())
