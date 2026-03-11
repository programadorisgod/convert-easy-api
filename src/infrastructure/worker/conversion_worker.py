"""Conversion worker using BullMQ.

Processes image conversion jobs from the queue using ImageMagick.
Handles job lifecycle, error recovery, and progress tracking.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bullmq import Worker, Job as BullMQJob

from shared.config import get_settings
from shared.events import get_event_bus
from shared.exceptions import ProcessingError
from src.domain.job import JobStarted, JobCompleted, JobFailed
from src.infrastructure.persistence import JobRepository
from src.infrastructure.storage.file_storage import FileStorage
from src.infrastructure.converters.image_converter import get_image_converter


logger = logging.getLogger(__name__)


class ConversionWorker:
    """Worker for processing image conversion jobs.

    Uses BullMQ Worker to consume jobs from the queue and process them
    using ImageMagick for image format conversion.

    Features:
    - Automatic retry with exponential backoff (handled by BullMQ)
    - Progress tracking and event publishing
    - Graceful shutdown
    - Error handling and logging
    """

    def __init__(
        self,
        redis_url: str,
        repository: JobRepository,
        storage: FileStorage,
    ):
        """Initialize conversion worker.

        Args:
            redis_url: Redis connection URL
            repository: Job repository for persistence
            storage: File storage for accessing input/output files
        """
        self.redis_url = redis_url
        self.repository = repository
        self.storage = storage
        self.converter = get_image_converter()
        self.settings = get_settings()
        self.event_bus = get_event_bus()

        self.worker: Worker | None = None
        self._shutdown = False

        logger.info("ConversionWorker initialized")

    async def start(self) -> None:
        """Start the worker to process jobs from the queue."""
        try:
            logger.info("🚀 Starting ConversionWorker...")

            # Create BullMQ Worker
            self.worker = Worker(
                "easy-convert-jobs",
                self._process_job,
                {
                    "connection": self.redis_url,
                    "concurrency": self.settings.worker_concurrency,
                },
            )

            logger.info(
                f"✅ Worker started with concurrency={self.settings.worker_concurrency}"
            )

            # Keep worker running until shutdown
            while not self._shutdown:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"❌ Worker failed to start: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        logger.info("🛑 Stopping ConversionWorker...")
        self._shutdown = True

        if self.worker:
            await self.worker.close()
            logger.info("✅ Worker stopped")

    async def _process_job(
        self, bullmq_job: BullMQJob, token: str | None = None
    ) -> dict[str, Any]:
        """Process a single conversion job.

        Called by BullMQ Worker for each job in the queue.

        Args:
            bullmq_job: BullMQ job instance
            token: Worker token for progress updates

        Returns:
            Result dictionary with output information

        Raises:
            ProcessingError: If conversion fails
        """
        job_id = bullmq_job.id
        start_time = datetime.now(timezone.utc)

        logger.info(f"📋 Processing job {job_id}")

        try:
            # Get job data from BullMQ
            job_data = bullmq_job.data
            input_format = job_data.get("input_format")
            output_format = job_data.get("output_format")
            file_id = job_data.get("file_id")

            if not all([input_format, output_format, file_id]):
                raise ProcessingError("Invalid job data: missing required fields")

            # Reconstruct Job aggregate from events
            job = await self.repository.get_job(job_id)

            # Check if job is already in a terminal state (avoid retries on failed/completed jobs)
            if job.status.is_terminal():
                logger.warning(
                    f"⚠️ Job {job_id} is already in terminal state {job.status}. "
                    f"Skipping processing to avoid infinite retries."
                )
                return {
                    "success": True,
                    "job_id": job_id,
                    "skipped": True,
                    "reason": f"Job already in terminal state: {job.status}",
                }

            # Check if job can be processed
            if not job.can_start_processing():
                raise ProcessingError(
                    f"Job {job_id} cannot be processed in state: {job.status}"
                )

            # Mark job as started
            worker_id = f"worker-{os.getpid()}"
            event = JobStarted.create(job_id=job_id, worker_id=worker_id)
            job.apply_event(event)
            await self.repository.save_events(job_id, [event])
            await self.event_bus.publish(event)

            logger.info(f"🔧 Converting {input_format} → {output_format}")

            # Get input file path
            input_path = await self.storage.get_file(file_id)

            # Perform conversion
            output_path = await self._convert_image(
                input_path, file_id, input_format, output_format, bullmq_job
            )

            result = {
                "format": output_format,
                "size": output_path.stat().st_size,
                "path": str(output_path),
            }

            # Calculate processing time
            end_time = datetime.now(timezone.utc)
            processing_time_seconds = (end_time - start_time).total_seconds()

            # Get output info
            output_size_bytes = result["size"]
            output_file_path = result["path"]

            # Mark job as completed
            event = JobCompleted.create(
                job_id=job_id,
                output_file_path=output_file_path,
                output_size_bytes=output_size_bytes,
                processing_time_seconds=processing_time_seconds,
            )
            job.apply_event(event)
            await self.repository.save_events(job_id, [event])
            await self.event_bus.publish(event)

            logger.info(
                f"✅ Job {job_id} completed in {processing_time_seconds:.2f}s "
                f"(output: {output_size_bytes} bytes)"
            )

            return {
                "success": True,
                "job_id": job_id,
                "result": result,
                "processing_time_seconds": processing_time_seconds,
            }

        except Exception as e:
            logger.error(f"❌ Job {job_id} failed: {e}", exc_info=True)

            # Mark job as failed (only if not already in terminal state)
            try:
                job = await self.repository.get_job(job_id)

                # Don't create failure event if already in terminal state
                if job.status.is_terminal():
                    logger.warning(
                        f"Job {job_id} already in terminal state {job.status}, "
                        f"not creating duplicate failure event"
                    )
                else:
                    event = JobFailed.create(
                        job_id=job_id,
                        error_message=str(e),
                        error_code=type(e).__name__,
                    )
                    job.apply_event(event)
                    await self.repository.save_events(job_id, [event])
                    await self.event_bus.publish(event)
            except Exception as save_error:
                logger.error(f"Failed to save failure event: {save_error}")

            raise ProcessingError(f"Job processing failed: {e}")

    async def _convert_image(
        self,
        input_path: Path,
        file_id: str,
        input_format: str,
        output_format: str,
        bullmq_job: BullMQJob,
    ) -> Path:
        """Convert image using ImageMagick.

        Args:
            input_path: Path to input file
            file_id: File identifier
            input_format: Input format (e.g., 'png')
            output_format: Output format (e.g., 'jpg')
            bullmq_job: BullMQ job for progress updates

        Returns:
            Path to converted output file

        Raises:
            UnsupportedFormatError: If format is not supported
            ProcessingError: If conversion fails
        """
        try:
            # Build output path
            output_path = self.storage._get_output_path(file_id)

            # Use ImageMagick converter utility
            await self.converter.convert(
                input_path=input_path,
                output_path=output_path,
                output_format=output_format,
                strip_metadata=True,  # Privacy: always strip EXIF
                preserve_transparency=True,
            )

            return output_path

        except Exception as e:
            logger.error(f"Conversion failed: {e}", exc_info=True)
            raise ProcessingError(f"Image conversion failed: {e}")


async def start_worker(
    redis_url: str, repository: JobRepository, storage: FileStorage
) -> ConversionWorker:
    """Start a conversion worker instance.

    Args:
        redis_url: Redis connection URL
        repository: Job repository
        storage: File storage

    Returns:
        Running ConversionWorker instance
    """
    worker = ConversionWorker(redis_url, repository, storage)

    # Start worker in background task
    asyncio.create_task(worker.start())

    return worker
