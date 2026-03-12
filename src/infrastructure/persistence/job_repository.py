"""Job repository using Redis Streams for event sourcing.

Uses Redis Streams to persist domain events and reconstruct Job aggregates
from their event history. Provides automatic TTL and event replay capabilities.

Redis Keys:
- job:events:{job_id} - Stream of events for a job
- job:snapshot:{job_id} - Optional snapshot for performance (not implemented yet)
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from redis.asyncio import Redis

from shared.config import get_settings
from shared.events import DomainEvent
from shared.exceptions import JobNotFoundError
from src.domain.job import (
    Job,
    JobCreated,
    ChunkUploaded,
    JobStarted,
    JobCompleted,
    JobFailed,
    JobCancelled,
    ImageProcessingConfigured,
    BackgroundRemoved,
    ImageCompressed,
    WatermarkApplied,
)


logger = logging.getLogger(__name__)


class JobRepository:
    """Repository for Job aggregates using event sourcing.

    Stores domain events in Redis Streams and reconstructs Job aggregates
    by replaying their event history.

    Features:
    - Event sourcing with full audit trail
    - Automatic TTL on event streams
    - Type-safe event deserialization
    - Efficient event replay
    """

    # Redis key patterns
    EVENTS_STREAM_KEY = "job:events:{job_id}"

    # Event type mapping for deserialization
    EVENT_TYPE_MAP = {
        "JobCreated": JobCreated,
        "ChunkUploaded": ChunkUploaded,
        "JobStarted": JobStarted,
        "JobCompleted": JobCompleted,
        "JobFailed": JobFailed,
        "JobCancelled": JobCancelled,
        # Image processing events
        "ImageProcessingConfigured": ImageProcessingConfigured,
        "BackgroundRemoved": BackgroundRemoved,
        "ImageCompressed": ImageCompressed,
        "WatermarkApplied": WatermarkApplied,
    }

    def __init__(self, redis_client: Redis):
        """Initialize repository.

        Args:
            redis_client: Redis async client
        """
        self.redis = redis_client
        self.settings = get_settings()

    async def save_events(
        self,
        job_id: str,
        events: list[DomainEvent],
        expected_version: int | None = None,
    ) -> None:
        """Save domain events to the event stream.

        Args:
            job_id: Job identifier
            events: List of domain events to save
            expected_version: Expected version for optimistic concurrency (not implemented)

        Raises:
            ValueError: If events list is empty
        """
        if not events:
            raise ValueError("Events list cannot be empty")

        try:
            stream_key = self.EVENTS_STREAM_KEY.format(job_id=job_id)

            # Add each event to the stream
            for event in events:
                event_data = self._serialize_event(event)

                # Add to Redis Stream (XADD)
                await self.redis.xadd(stream_key, event_data)

            # Set TTL on the stream (job_ttl_hours from settings)
            ttl_seconds = self.settings.job_ttl_hours * 3600
            await self.redis.expire(stream_key, ttl_seconds)

            logger.info(f"Saved {len(events)} event(s) for job {job_id}")

        except Exception as e:
            logger.error(f"Failed to save events for job {job_id}: {e}", exc_info=True)
            raise

    async def get_events(self, job_id: str) -> list[DomainEvent]:
        """Get all events for a job from the event stream.

        Args:
            job_id: Job identifier

        Returns:
            List of domain events in chronological order

        Raises:
            JobNotFoundError: If no events found for job
        """
        try:
            stream_key = self.EVENTS_STREAM_KEY.format(job_id=job_id)

            # Read all events from stream start (XRANGE)
            # '-' means from beginning, '+' means to end
            stream_events = await self.redis.xrange(stream_key, min="-", max="+")

            if not stream_events:
                raise JobNotFoundError(job_id)

            # Deserialize events
            events = []
            for event_id, event_data in stream_events:
                event = self._deserialize_event(event_data)
                if event:
                    events.append(event)

            return events

        except JobNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to get events for job {job_id}: {e}", exc_info=True)
            raise

    async def get_job(self, job_id: str) -> Job:
        """Reconstruct a Job aggregate from its event history.

        Args:
            job_id: Job identifier

        Returns:
            Job aggregate reconstructed from events

        Raises:
            JobNotFoundError: If job doesn't exist
        """
        try:
            events = await self.get_events(job_id)
            job = Job.from_events(job_id, events)

            return job

        except JobNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to reconstruct job {job_id}: {e}", exc_info=True)
            raise

    async def job_exists(self, job_id: str) -> bool:
        """Check if a job exists in the repository.

        Args:
            job_id: Job identifier

        Returns:
            True if job exists
        """
        try:
            stream_key = self.EVENTS_STREAM_KEY.format(job_id=job_id)
            length = await self.redis.xlen(stream_key)
            return length > 0
        except Exception as e:
            logger.error(f"Failed to check job existence for {job_id}: {e}")
            return False

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job's event stream.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            stream_key = self.EVENTS_STREAM_KEY.format(job_id=job_id)
            deleted = await self.redis.delete(stream_key)

            if deleted:
                logger.info(f"Deleted job {job_id} event stream")

            return deleted > 0

        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}", exc_info=True)
            return False

    async def cleanup_old_jobs(self, older_than_hours: int | None = None) -> int:
        """Delete job event streams older than specified age.

        Note: This scans all job:events:* keys and checks their TTL.
        Redis will automatically delete expired keys, but this provides
        manual cleanup if needed.

        Args:
            older_than_hours: Delete jobs older than this (defaults to job_ttl_hours)

        Returns:
            Number of jobs deleted
        """
        if older_than_hours is None:
            older_than_hours = self.settings.job_ttl_hours

        try:
            deleted = 0
            pattern = "job:events:*"

            cursor = 0
            while True:
                # Scan for job event keys
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)

                for key in keys:
                    key = key.decode() if isinstance(key, bytes) else key

                    # Get first event to check timestamp
                    events = await self.redis.xrange(key, min="-", max="+", count=1)

                    if events:
                        _, event_data = events[0]
                        timestamp_str = event_data.get("timestamp")

                        if timestamp_str:
                            timestamp = datetime.fromisoformat(timestamp_str)
                            cutoff = datetime.now(timezone.utc) - timedelta(
                                hours=older_than_hours
                            )

                            if timestamp < cutoff:
                                await self.redis.delete(key)
                                deleted += 1

                if cursor == 0:
                    break

            if deleted > 0:
                logger.info(
                    f"Cleaned up {deleted} old job(s) older than {older_than_hours}h"
                )

            return deleted

        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}", exc_info=True)
            return 0

    async def get_all_job_ids(self, limit: int = 100) -> list[str]:
        """Get list of all job IDs in the repository.

        Args:
            limit: Maximum number of job IDs to return

        Returns:
            List of job IDs
        """
        try:
            job_ids = []
            pattern = "job:events:*"

            cursor = 0
            while len(job_ids) < limit:
                cursor, keys = await self.redis.scan(
                    cursor, match=pattern, count=min(100, limit - len(job_ids))
                )

                for key in keys:
                    key = key.decode() if isinstance(key, bytes) else key
                    # Extract job_id from key pattern "job:events:{job_id}"
                    job_id = key.replace("job:events:", "")
                    job_ids.append(job_id)

                if cursor == 0:
                    break

            return job_ids[:limit]

        except Exception as e:
            logger.error(f"Failed to get job IDs: {e}", exc_info=True)
            return []

    def _serialize_event(self, event: DomainEvent) -> dict[str, str]:
        """Serialize domain event to Redis Stream format.

        Redis Streams store data as field-value pairs (like a hash).

        Args:
            event: Domain event to serialize

        Returns:
            Dict with string keys and values for Redis
        """
        # Get event data as dict with JSON-compatible types
        event_dict = event.model_dump(mode="json")

        # Convert to string format for Redis
        return {
            "event_type": type(event).__name__,
            "event_id": event.event_id,
            "aggregate_id": event.aggregate_id,
            "timestamp": event.timestamp.isoformat(),
            "data": json.dumps(event_dict),
        }

    def _deserialize_event(
        self, event_data: dict[bytes | str, bytes | str]
    ) -> DomainEvent | None:
        """Deserialize event from Redis Stream format.

        Args:
            event_data: Raw event data from Redis Stream

        Returns:
            Domain event instance or None if deserialization fails
        """
        try:
            # Decode all bytes to strings
            decoded_data = {}
            for k, v in event_data.items():
                key = k.decode() if isinstance(k, bytes) else k
                value = v.decode() if isinstance(v, bytes) else v
                decoded_data[key] = value

            event_type_name = decoded_data.get("event_type")

            if not event_type_name:
                logger.warning(f"Unknown event type: {event_type_name}")
                return None

            event_class = self.EVENT_TYPE_MAP.get(event_type_name)

            if not event_class:
                logger.warning(f"Unknown event type: {event_type_name}")
                return None

            # Parse event data JSON
            data = json.loads(decoded_data.get("data", "{}"))

            # Create event instance
            return event_class(**data)

        except Exception as e:
            logger.error(f"Failed to deserialize event: {e}", exc_info=True)
            return None


# Repository instance holder
_job_repository: JobRepository | None = None


def get_job_repository(redis_client: Redis | None = None) -> JobRepository:
    """Get job repository instance.

    Args:
        redis_client: Optional Redis client (for dependency injection)

    Returns:
        JobRepository instance
    """
    global _job_repository

    if redis_client:
        # Create new instance with provided client
        return JobRepository(redis_client)

    if _job_repository is None:
        raise RuntimeError(
            "JobRepository not initialized. "
            "Call with redis_client or initialize via lifespan."
        )

    return _job_repository


def initialize_repository(redis_client: Redis) -> JobRepository:
    """Initialize global repository instance.

    Called during application startup.

    Args:
        redis_client: Redis client instance

    Returns:
        JobRepository instance
    """
    global _job_repository
    _job_repository = JobRepository(redis_client)
    logger.info("JobRepository initialized")
    return _job_repository
