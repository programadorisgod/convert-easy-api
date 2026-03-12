"""Job domain module."""

from .job import Job
from .job_status import JobStatus
from .job_events import (
    JobEvent,
    JobCreated,
    ChunkUploaded,
    JobStarted,
    JobCompleted,
    JobFailed,
    JobCancelled,
    # Image processing events
    ImageProcessingConfigured,
    BackgroundRemoved,
    ImageCompressed,
    WatermarkApplied,
)

__all__ = [
    "Job",
    "JobStatus",
    "JobEvent",
    "JobCreated",
    "ChunkUploaded",
    "JobStarted",
    "JobCompleted",
    "JobFailed",
    "JobCancelled",
    # Image processing events
    "ImageProcessingConfigured",
    "BackgroundRemoved",
    "ImageCompressed",
    "WatermarkApplied",
]
