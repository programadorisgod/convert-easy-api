"""Command handlers (application use cases).

Handlers orchestrate domain logic, infrastructure services, and events
to fulfill business use cases. Each handler corresponds to one command.
"""

import logging
from uuid import uuid4

from shared.events import get_event_bus
from shared.exceptions import (
    ValidationError,
    UnsupportedFormatError,
    FileSizeLimitError,
)
from src.application.commands import (
    CreateJobCommand,
    UploadChunkCommand,
    UploadCompleteFileCommand,
    MergeChunksCommand,
    StartConversionCommand,
    CancelJobCommand,
    GetJobStatusCommand,
)
from src.domain.job import (
    JobCreated,
    ChunkUploaded,
    JobCancelled,
)
from src.infrastructure.persistence import JobRepository
from src.infrastructure.storage.file_storage import FileStorage
from src.infrastructure.queue import BullMQAdapter


logger = logging.getLogger(__name__)


class CreateJobHandler:
    """Handler for creating new conversion jobs."""

    def __init__(
        self,
        repository: JobRepository,
        storage: FileStorage,
    ):
        """Initialize handler.

        Args:
            repository: Job repository
            storage: File storage
        """
        self.repository = repository
        self.storage = storage
        self.event_bus = get_event_bus()

    async def handle(self, command: CreateJobCommand) -> str:
        """Create a new job.

        Args:
            command: CreateJobCommand

        Returns:
            Created job_id

        Raises:
            ValidationError: If command validation fails
            UnsupportedFormatError: If format not supported
            FileSizeLimitError: If file too large
        """
        # Validate input format
        from shared.config import get_settings

        settings = get_settings()

        if not settings.is_image_format_supported(command.input_format):
            raise UnsupportedFormatError(command.input_format)

        # Validate output formats
        for fmt in command.output_formats:
            if not settings.is_image_format_supported(fmt):
                raise UnsupportedFormatError(fmt)

        # Validate file size
        max_size = settings.max_file_size_mb * 1024 * 1024
        if command.original_size > max_size:
            raise FileSizeLimitError(
                f"File size {command.original_size} bytes exceeds limit of {max_size} bytes"
            )

        # Generate IDs
        job_id = str(uuid4())
        file_id = str(uuid4())

        # Create job aggregate
        # Note: We take the first output format for now (single conversion per job)
        output_format = command.output_formats[0] if command.output_formats else "jpg"
        event = JobCreated.create(
            job_id=job_id,
            file_id=file_id,
            input_format=command.input_format,
            output_format=output_format,
            file_size_bytes=command.original_size,
            total_chunks=command.total_chunks,
        )

        # Persist event
        await self.repository.save_events(job_id, [event])

        # Publish event
        await self.event_bus.publish(event)

        logger.info(
            f"Created job {job_id} for {command.input_format} → {command.output_formats}"
        )

        return job_id


class UploadChunkHandler:
    """Handler for uploading file chunks."""

    def __init__(
        self,
        repository: JobRepository,
        storage: FileStorage,
    ):
        """Initialize handler.

        Args:
            repository: Job repository
            storage: File storage
        """
        self.repository = repository
        self.storage = storage
        self.event_bus = get_event_bus()

    async def handle(self, command: UploadChunkCommand) -> dict:
        """Upload a chunk.

        Args:
            command: UploadChunkCommand

        Returns:
            Upload result with progress info

        Raises:
            JobNotFoundError: If job doesn't exist
            ValidationError: If chunk validation fails
        """
        # Get job
        job = await self.repository.get_job(command.job_id)

        # Validate chunk can be uploaded
        if not job.can_upload_chunks():
            raise ValidationError(
                f"Cannot upload chunks for job in state: {job.status}"
            )

        # Validate chunk index
        if command.chunk_index >= job.total_chunks:
            raise ValidationError(
                f"Chunk index {command.chunk_index} exceeds total {job.total_chunks}"
            )

        # Save chunk to storage
        await self.storage.save_chunk(
            job.file_id, command.chunk_index, command.chunk_data
        )

        # Create and apply event
        event = ChunkUploaded.create(
            job_id=command.job_id,
            file_id=job.file_id,
            chunk_index=command.chunk_index,
            total_chunks=job.total_chunks,
            chunk_size_bytes=len(command.chunk_data),
        )
        job.add_event(event)

        # Persist event
        await self.repository.save_events(command.job_id, [event])

        # Publish event
        await self.event_bus.publish(event)

        logger.info(
            f"Uploaded chunk {command.chunk_index}/{job.total_chunks} "
            f"for job {command.job_id}"
        )

        return {
            "job_id": command.job_id,
            "chunk_index": command.chunk_index,
            "chunks_uploaded": job.chunks_uploaded,
            "total_chunks": job.total_chunks,
            "is_complete": job.chunks_uploaded == job.total_chunks,
        }


class UploadCompleteFileHandler:
    """Handler for uploading complete files (non-chunked)."""

    def __init__(
        self,
        repository: JobRepository,
        storage: FileStorage,
    ):
        """Initialize handler.

        Args:
            repository: Job repository
            storage: File storage
        """
        self.repository = repository
        self.storage = storage
        self.event_bus = get_event_bus()

    async def handle(self, command: UploadCompleteFileCommand) -> dict:
        """Upload complete file.

        Args:
            command: UploadCompleteFileCommand

        Returns:
            Upload result

        Raises:
            JobNotFoundError: If job doesn't exist
            ValidationError: If upload validation fails
        """
        # Get job
        job = await self.repository.get_job(command.job_id)

        # Validate upload
        if not job.can_upload_chunks():
            raise ValidationError(f"Cannot upload file for job in state: {job.status}")

        if job.total_chunks != 1:
            raise ValidationError(
                f"Job expects {job.total_chunks} chunks, use chunk upload instead"
            )

        # Save file to storage
        await self.storage.save_file(job.file_id, command.file_data)

        # Create and apply event (simulating single chunk upload)
        event = ChunkUploaded.create(
            job_id=command.job_id,
            file_id=job.file_id,
            chunk_index=0,
            total_chunks=1,
            chunk_size_bytes=len(command.file_data),
        )
        job.add_event(event)

        # Persist event
        await self.repository.save_events(command.job_id, [event])

        # Publish event
        await self.event_bus.publish(event)

        logger.info(f"Uploaded complete file for job {command.job_id}")

        return {
            "job_id": command.job_id,
            "file_size": len(command.file_data),
            "is_complete": True,
        }


class MergeChunksHandler:
    """Handler for merging uploaded chunks into a single file."""

    def __init__(
        self,
        repository: JobRepository,
        storage: FileStorage,
    ):
        """Initialize handler.

        Args:
            repository: Job repository
            storage: File storage
        """
        self.repository = repository
        self.storage = storage

    async def handle(self, command: MergeChunksCommand) -> dict:
        """Merge uploaded chunks into single file.

        Args:
            command: MergeChunksCommand

        Returns:
            Merge result with file info

        Raises:
            JobNotFoundError: If job doesn't exist
            ValidationError: If chunks cannot be merged
        """
        # Get job
        job = await self.repository.get_job(command.job_id)

        # Validate all chunks are uploaded
        if not job.can_start_processing():
            raise ValidationError(
                f"Cannot merge chunks for job in state: {job.status}. "
                f"Ensure all {job.total_chunks} chunks are uploaded "
                f"({job.chunks_uploaded} uploaded so far)."
            )

        # If single chunk/file, no merge needed
        if job.total_chunks == 1:
            file_path = await self.storage.get_file(job.file_id)
            logger.info(f"Job {command.job_id} has single file, no merge needed")
            return {
                "job_id": command.job_id,
                "file_id": job.file_id,
                "merged": False,
                "reason": "Single file, no merge needed",
                "file_size": file_path.stat().st_size,
            }

        # Assemble chunks
        assembled_path = await self.storage.assemble_chunks(
            job.file_id, job.total_chunks
        )

        logger.info(
            f"Merged {job.total_chunks} chunks for job {command.job_id} "
            f"({assembled_path.stat().st_size} bytes)"
        )

        return {
            "job_id": command.job_id,
            "file_id": job.file_id,
            "merged": True,
            "total_chunks": job.total_chunks,
            "file_size": assembled_path.stat().st_size,
        }


class StartConversionHandler:
    """Handler for starting the conversion process."""

    def __init__(
        self,
        repository: JobRepository,
        storage: FileStorage,
        queue: BullMQAdapter,
    ):
        """Initialize handler.

        Args:
            repository: Job repository
            storage: File storage
            queue: Queue adapter
        """
        self.repository = repository
        self.storage = storage
        self.queue = queue

    async def handle(self, command: StartConversionCommand) -> dict:
        """Start conversion process.

        Args:
            command: StartConversionCommand

        Returns:
            Result with queue job ID

        Raises:
            JobNotFoundError: If job doesn't exist
            ValidationError: If job cannot be processed
        """
        # Get job
        job = await self.repository.get_job(command.job_id)

        # Validate job can be processed
        if not job.can_start_processing():
            raise ValidationError(
                f"Cannot start processing for job in state: {job.status}. "
                f"Ensure all chunks are uploaded and merged."
            )

        # Verify file exists (chunks should already be merged)
        try:
            file_path = await self.storage.get_file(job.file_id)
            logger.info(
                f"Starting conversion for {file_path} ({file_path.stat().st_size} bytes)"
            )
        except Exception as e:
            raise ValidationError(
                f"File not ready for conversion. "
                f"If using chunked upload, call /merge endpoint first. Error: {e}"
            )

        # Enqueue job for processing
        queue_job_id = await self.queue.enqueue(
            command.job_id,
            {
                "job_id": command.job_id,
                "file_id": job.file_id,
                "input_format": job.input_format,
                "output_format": job.output_format,
            },
        )

        logger.info(f"Enqueued job {command.job_id} for conversion")

        return {
            "job_id": command.job_id,
            "queue_job_id": queue_job_id,
            "status": "queued",
        }


class CancelJobHandler:
    """Handler for cancelling jobs."""

    def __init__(
        self,
        repository: JobRepository,
        queue: BullMQAdapter,
    ):
        """Initialize handler.

        Args:
            repository: Job repository
            queue: Queue adapter
        """
        self.repository = repository
        self.queue = queue
        self.event_bus = get_event_bus()

    async def handle(self, command: CancelJobCommand) -> dict:
        """Cancel a job.

        Args:
            command: CancelJobCommand

        Returns:
            Cancellation result

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        # Get job
        job = await self.repository.get_job(command.job_id)

        # Check if job can be cancelled
        if not job.can_cancel():
            raise ValidationError(f"Cannot cancel job in state: {job.status}")

        # Cancel in queue if queued/processing
        await self.queue.cancel_job(command.job_id)

        # Create and apply cancellation event
        event = JobCancelled.create(
            job_id=command.job_id,
            reason=command.reason or "User requested cancellation",
        )
        job.add_event(event)

        # Persist event
        await self.repository.save_events(command.job_id, [event])

        # Publish event
        await self.event_bus.publish(event)

        logger.info(f"Cancelled job {command.job_id}")

        return {
            "job_id": command.job_id,
            "status": "cancelled",
            "reason": event.reason,
        }


class GetJobStatusHandler:
    """Handler for retrieving job status."""

    def __init__(self, repository: JobRepository):
        """Initialize handler.

        Args:
            repository: Job repository
        """
        self.repository = repository

    async def handle(self, command: GetJobStatusCommand) -> dict:
        """Get job status.

        Args:
            command: GetJobStatusCommand

        Returns:
            Job status information

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        # Get job
        job = await self.repository.get_job(command.job_id)

        return job.to_dict()
