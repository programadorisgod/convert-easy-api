"""BullMQ-based queue adapter implementing QueuePort.

Uses BullMQ for robust job queue management with built-in features:
- Automatic retries with exponential backoff
- Job prioritization
- Rate limiting
- Job events and monitoring
- Graceful failure handling

BullMQ manages Redis internally, providing a higher-level abstraction
than raw Redis commands.
"""

import logging
from typing import Any

from bullmq import Queue

from shared.queue import QueuePort
from shared.config import get_settings


logger = logging.getLogger(__name__)


class BullMQAdapter(QueuePort):
    """BullMQ-based implementation of the queue port.

    This adapter wraps BullMQ's Queue class to implement our QueuePort
    interface, providing a clean abstraction for job queue operations.
    """

    QUEUE_NAME = "easy-convert-jobs"

    def __init__(self, redis_url: str):
        """Initialize BullMQ adapter.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.settings = get_settings()

        # Initialize BullMQ Queue
        # BullMQ handles Redis connection internally
        self.queue = Queue(
            self.QUEUE_NAME,
            {
                "connection": redis_url,
            },
        )

        logger.info(f"BullMQ Queue '{self.QUEUE_NAME}' initialized")

    async def enqueue(
        self, job_id: str, job_data: dict[str, Any], priority: int = 0
    ) -> str:
        """Enqueue a new job for processing.

        Args:
            job_id: Unique job identifier
            job_data: Job payload data
            priority: Job priority (higher = more urgent)

        Returns:
            Queue job ID (BullMQ's internal ID)
        """
        try:
            # Add job to BullMQ queue with configuration
            job = await self.queue.add(
                job_id,  # Job name/type
                job_data,  # Job data payload
                {
                    "jobId": job_id,  # Use our job_id as BullMQ's job ID
                    "priority": priority,
                    "attempts": 3,  # Retry up to 3 times on failure
                    "backoff": {
                        "type": "exponential",
                        "delay": 2000,  # Start with 2 seconds, doubles each retry
                    },
                    "removeOnComplete": {
                        "age": self.settings.job_cleanup_hours
                        * 3600,  # Keep for cleanup period
                        "count": 1000,  # Keep last 1000 completed jobs
                    },
                    "removeOnFail": {
                        "age": self.settings.job_ttl_hours
                        * 3600,  # Keep failed jobs for TTL
                    },
                },
            )

            logger.info(f"Job {job_id} enqueued successfully with BullMQ ID: {job.id}")
            return job.id

        except Exception as e:
            logger.error(f"Failed to enqueue job {job_id}: {e}", exc_info=True)
            raise

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get current status of a job.

        Args:
            job_id: Job identifier

        Returns:
            Job status dict or None if not found
        """
        try:
            # Get job from BullMQ by ID
            job = await self.queue.getJob(job_id)

            if not job:
                logger.debug(f"Job {job_id} not found")
                return None

            # Get job state (waiting, active, completed, failed, delayed)
            state = await job.getState()

            # Map BullMQ state to our status
            status_map = {
                "waiting": "queued",
                "active": "processing",
                "completed": "completed",
                "failed": "failed",
                "delayed": "queued",
            }

            return {
                "job_id": job_id,
                "status": status_map.get(state, state),
                "retry_count": job.attemptsMade if hasattr(job, "attemptsMade") else 0,
                "error_message": job.failedReason
                if hasattr(job, "failedReason")
                else None,
                "created_at": job.timestamp if hasattr(job, "timestamp") else None,
                "updated_at": job.processedOn if hasattr(job, "processedOn") else None,
                "completed_at": job.finishedOn if hasattr(job, "finishedOn") else None,
                "metadata": {
                    "progress": job.progress if hasattr(job, "progress") else 0,
                    "returnvalue": job.returnvalue
                    if hasattr(job, "returnvalue")
                    else None,
                },
            }

        except Exception as e:
            logger.error(f"Failed to get status for job {job_id}: {e}")
            return None

    async def update_job_status(
        self, job_id: str, status: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Update job status and metadata.

        Note: With BullMQ, job status is managed automatically by the worker.
        This method is provided for compatibility but limited functionality.
        Use job.updateProgress() inside the worker processor instead.

        Args:
            job_id: Job identifier
            status: New status (mostly for logging)
            metadata: Additional metadata to store
        """
        try:
            job = await self.queue.getJob(job_id)

            if not job:
                logger.warning(f"Cannot update job {job_id}: not found")
                return

            # Update progress if provided in metadata
            if metadata and "progress" in metadata:
                await job.updateProgress(metadata["progress"])

            logger.info(f"Job {job_id} metadata updated (status: {status})")

        except Exception as e:
            logger.error(
                f"Failed to update status for job {job_id}: {e}", exc_info=True
            )
            raise

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job.

        Args:
            job_id: Job identifier

        Returns:
            True if cancelled, False if not found or already complete
        """
        try:
            job = await self.queue.getJob(job_id)

            if not job:
                logger.warning(f"Cannot cancel job {job_id}: not found")
                return False

            state = await job.getState()

            # Can only cancel if not completed or failed
            if state in ("completed", "failed"):
                logger.warning(f"Cannot cancel job {job_id}: already {state}")
                return False

            # Remove job from queue
            await job.remove()

            logger.info(f"Job {job_id} cancelled successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}", exc_info=True)
            return False

    async def get_queue_size(self) -> int:
        """Get number of jobs waiting in queue.

        Returns:
            Count of pending jobs
        """
        try:
            # Get count of waiting and delayed jobs
            counts = await self.queue.getJobCounts("waiting", "delayed")
            total = counts.get("waiting", 0) + counts.get("delayed", 0)
            return total
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0

    async def get_job_counts(self) -> dict[str, int]:
        """Get counts of jobs by status.

        Returns:
            Dict with counts for each status
        """
        try:
            counts = await self.queue.getJobCounts(
                "waiting", "active", "completed", "failed", "delayed"
            )
            return {
                "queued": counts.get("waiting", 0) + counts.get("delayed", 0),
                "processing": counts.get("active", 0),
                "completed": counts.get("completed", 0),
                "failed": counts.get("failed", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get job counts: {e}")
            return {}

    async def cleanup_old_jobs(self, max_age_hours: int | None = None) -> int:
        """Clean up old completed and failed jobs.

        Args:
            max_age_hours: Delete jobs older than this many hours
                          (defaults to settings.job_cleanup_hours)

        Returns:
            Number of jobs cleaned up
        """
        if max_age_hours is None:
            max_age_hours = self.settings.job_cleanup_hours

        try:
            max_age_ms = max_age_hours * 3600 * 1000

            # Clean completed jobs
            completed = await self.queue.clean(
                max_age_ms,  # Grace period in milliseconds
                1000,  # Limit number of jobs to clean
                "completed",
            )

            # Clean failed jobs
            failed = await self.queue.clean(max_age_ms, 1000, "failed")

            total = len(completed) + len(failed)

            if total > 0:
                logger.info(
                    f"Cleaned up {total} old jobs "
                    f"({len(completed)} completed, {len(failed)} failed)"
                )

            return total

        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}", exc_info=True)
            return 0

    async def pause(self) -> None:
        """Pause the queue (stop processing new jobs)."""
        try:
            await self.queue.pause()
            logger.info(f"Queue '{self.QUEUE_NAME}' paused")
        except Exception as e:
            logger.error(f"Failed to pause queue: {e}")

    async def resume(self) -> None:
        """Resume the queue (continue processing jobs)."""
        try:
            await self.queue.resume()
            logger.info(f"Queue '{self.QUEUE_NAME}' resumed")
        except Exception as e:
            logger.error(f"Failed to resume queue: {e}")

    async def close(self) -> None:
        """Close queue connection gracefully."""
        try:
            await self.queue.close()
            logger.info("BullMQ queue connection closed")
        except Exception as e:
            logger.error(f"Failed to close queue: {e}")
