"""Queue service for job management.

Provides high-level queue operations and coordinates job lifecycle
with the queue infrastructure.
"""

import logging
from typing import Any

from shared.config import get_settings
from shared.exceptions import JobNotFoundError
from src.infrastructure.queue import BullMQAdapter
from src.infrastructure.persistence import JobRepository


logger = logging.getLogger(__name__)


class QueueService:
    """Service for managing job queue operations.

    Coordinates between the queue infrastructure (BullMQ) and
    the application layer to manage job lifecycle.
    """

    def __init__(
        self,
        queue: BullMQAdapter,
        repository: JobRepository,
    ):
        """Initialize queue service.

        Args:
            queue: Queue adapter
            repository: Job repository
        """
        self.queue = queue
        self.repository = repository
        self.settings = get_settings()

    async def enqueue_conversion(
        self,
        job_id: str,
        file_id: str,
        input_format: str,
        output_formats: list[str],
        priority: int = 0,
    ) -> str:
        """Enqueue a conversion job.

        Args:
            job_id: Job identifier
            file_id: File identifier
            input_format: Input format
            output_formats: List of output formats
            priority: Job priority (higher = more urgent)

        Returns:
            Queue job ID

        Raises:
            ValidationError: If validation fails
        """
        # Validate job exists
        if not await self.repository.job_exists(job_id):
            raise JobNotFoundError(job_id)

        # Prepare job data
        job_data = {
            "job_id": job_id,
            "file_id": file_id,
            "input_format": input_format,
            "output_formats": output_formats,
        }

        # Enqueue to BullMQ
        queue_job_id = await self.queue.enqueue(job_id, job_data, priority=priority)

        logger.info(
            f"Enqueued conversion job {job_id} "
            f"({input_format} → {output_formats}) with priority {priority}"
        )

        return queue_job_id

    async def get_queue_stats(self) -> dict[str, Any]:
        """Get queue statistics.

        Returns:
            Queue statistics including counts by status
        """
        queue_size = await self.queue.get_queue_size()
        counts = await self.queue.get_job_counts()

        return {
            "pending": queue_size,
            "processing": counts.get("processing", 0),
            "completed": counts.get("completed", 0),
            "failed": counts.get("failed", 0),
            "total": sum(counts.values()),
        }

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job in the queue.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled successfully
        """
        success = await self.queue.cancel_job(job_id)

        if success:
            logger.info(f"Cancelled job {job_id} in queue")
        else:
            logger.warning(f"Failed to cancel job {job_id} in queue")

        return success

    async def pause_queue(self) -> None:
        """Pause the queue (stop processing new jobs)."""
        await self.queue.pause()
        logger.info("Queue paused")

    async def resume_queue(self) -> None:
        """Resume the queue (continue processing jobs)."""
        await self.queue.resume()
        logger.info("Queue resumed")

    async def cleanup_old_jobs(self) -> int:
        """Clean up old completed/failed jobs.

        Returns:
            Number of jobs cleaned up
        """
        cleaned = await self.queue.cleanup_old_jobs()

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old job(s) from queue")

        return cleaned


def get_queue_service(
    queue: BullMQAdapter,
    repository: JobRepository,
) -> QueueService:
    """Get queue service instance.

    Args:
        queue: Queue adapter
        repository: Job repository

    Returns:
        QueueService instance
    """
    return QueueService(queue, repository)
